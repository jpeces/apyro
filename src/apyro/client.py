from typing import TYPE_CHECKING, Any, Self, TypeVar

from apyro.config import ApiClientConfig
from apyro.endpoint import Endpoint
from apyro.errors import ApiTransportError
from apyro.response import ApiResponse

if TYPE_CHECKING:
    import httpx

T = TypeVar("T")


class ApiClient:
    """A resilient HTTP client built on httpx, driven by :class:`Endpoint` descriptors.

    Owns httpx client lifecycle, config, retries, and auth. Request rendering
    and response parsing are delegated to :meth:`Endpoint.build_request` and
    :meth:`Endpoint.parse_response`. The underlying httpx client is constructed
    lazily on first use and shared for the lifetime of this instance.
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        configuration: ApiClientConfig | None = None,
    ) -> None:
        self.base_url = base_url
        self.headers = headers or {}
        self.configuration = configuration or ApiClientConfig()
        self._client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    def _resolve_auth(self) -> Any:
        cfg = self.configuration
        if cfg.username is not None and cfg.password is not None:
            return (cfg.username, cfg.password)
        if cfg.auth_flow is not None:
            return cfg.auth_flow
        return None

    def _build_transport(self) -> Any:
        from httpx_retries import Retry, RetryTransport

        cfg = self.configuration
        if cfg.retries > 0:
            retry_strategy = Retry(
                total=cfg.retries,
                backoff_factor=cfg.backoff_factor,
                status_forcelist=list(cfg.retry_status_list or []),
            )
            return RetryTransport(transport=cfg.transport, retry=retry_strategy)
        return cfg.transport

    def _build_event_hooks(self, *, async_: bool) -> dict[str, list[Any]] | None:
        raw = self.configuration.event_hooks
        if raw is None:
            return None
        if not async_:
            return raw
        # ponytail: httpx AsyncClient awaits hooks (wants coroutines) while
        # Client calls them directly. Wrap sync hooks so one config works on
        # both paths; async hooks pass through unchanged. Key names are
        # identical across both clients — no fan-out needed.
        import inspect

        def _wrap(hook: Any) -> Any:
            if inspect.iscoroutinefunction(hook):
                return hook

            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return hook(*args, **kwargs)

            return _async_wrapper

        return {k: [_wrap(h) for h in v] for k, v in raw.items()}

    def get_client(self) -> httpx.Client:
        """Get the underlying httpx.Client, constructing a new one if not set."""
        import httpx

        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=20)
            timeout_config = httpx.Timeout(self.configuration.timeout)
            transport = self._build_transport()
            auth = self._resolve_auth()

            self._client = httpx.Client(
                auth=auth,
                base_url=self.base_url,
                headers=self.headers,
                timeout=timeout_config,
                limits=limits,
                verify=self.configuration.verify_ssl,
                follow_redirects=self.configuration.follow_redirects,
                transport=transport,
                event_hooks=self._build_event_hooks(async_=False),
            )
        return self._client

    def get_async_client(self) -> httpx.AsyncClient:
        """Get the underlying httpx.AsyncClient, constructing a new one if not set."""
        import httpx

        if self._async_client is None:
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=20)
            timeout_config = httpx.Timeout(self.configuration.timeout)
            transport = self._build_transport()
            auth = self._resolve_auth()

            self._async_client = httpx.AsyncClient(
                auth=auth,
                base_url=self.base_url,
                headers=self.headers,
                timeout=timeout_config,
                limits=limits,
                verify=self.configuration.verify_ssl,
                follow_redirects=self.configuration.follow_redirects,
                transport=transport,
                event_hooks=self._build_event_hooks(async_=True),
            )
        return self._async_client

    def request(
        self,
        endpoint: Endpoint[T],
        *,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> ApiResponse[T]:
        """Send a request for the given endpoint synchronously."""
        import httpx

        client = self.get_client()
        req = endpoint.build_request(
            client,
            path_params=path_params,
            query_params=query_params,
            body=body,
            headers=headers,
        )
        try:
            raw = client.send(req)
        except httpx.TransportError as exc:
            # ponytail: httpx event_hooks don't fire on TransportError (no
            # response exists). Add on_error_hooks: list[Callable[[httpx
            # .TransportError], None]] to ApiClientConfig and invoke here when
            # a user needs circuit-breaking or transport-error metrics.
            raise ApiTransportError(str(exc)) from exc
        return endpoint.parse_response(
            raw,
            suppress_unexpected_status=self.configuration.suppress_unexpected_status,
        )

    async def arequest(
        self,
        endpoint: Endpoint[T],
        *,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> ApiResponse[T]:
        """Send a request for the given endpoint asynchronously."""
        import httpx

        client = self.get_async_client()
        req = endpoint.build_request(
            client,
            path_params=path_params,
            query_params=query_params,
            body=body,
            headers=headers,
        )
        try:
            raw = await client.send(req)
        except httpx.TransportError as exc:
            # ponytail: see sync request() above — same deferral applies here.
            raise ApiTransportError(str(exc)) from exc
        return endpoint.parse_response(
            raw,
            suppress_unexpected_status=self.configuration.suppress_unexpected_status,
        )

    def close(self) -> None:
        """Close the underlying synchronous httpx client if it was created."""
        if self._client is not None:
            self._client.close()
            self._client = None

    async def aclose(self) -> None:
        """Close the underlying asynchronous httpx client if it was created."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def __enter__(self) -> Self:
        self.get_client().__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        self.get_client().__exit__(*args, **kwargs)

    async def __aenter__(self) -> Self:
        await self.get_async_client().__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.get_async_client().__aexit__(*args, **kwargs)


__all__ = ["ApiClient"]
