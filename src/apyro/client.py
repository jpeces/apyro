from typing import TYPE_CHECKING, Any, Self, TypeVar

from apyro.config import ApiClientConfig
from apyro.endpoint import Endpoint
from apyro.errors import ApiTransportError
from apyro.response import ApiResponse

if TYPE_CHECKING:
    import httpx

T = TypeVar("T")


class ApiClient:
    """An HTTP client built on httpx, driven by `Endpoint` descriptors.

    Owns httpx client lifecycle, config, retries, and auth. Request rendering
    and response parsing are delegated to `Endpoint.build_request` and
    `Endpoint.parse_response`. The underlying httpx client is constructed
    lazily on first use and shared for the lifetime of this instance.
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        configuration: ApiClientConfig | None = None,
    ) -> None:
        """Initialize the `ApiClient`.

        Args:
            base_url: Base URL prepended to every endpoint path.
            headers: Default headers applied to every request.
            configuration: Client-level configuration (timeouts, retries, auth, ...).
                Defaults to `ApiClientConfig()`.
        """
        self.base_url = base_url
        self.headers = headers or {}
        self.configuration = configuration or ApiClientConfig()
        self._client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    def _resolve_auth(self) -> Any:
        """Resolve the auth callable/tuple from `ApiClientConfig`."""
        cfg = self.configuration
        if cfg.username is not None and cfg.password is not None:
            return (cfg.username, cfg.password)
        if cfg.auth_flow is not None:
            return cfg.auth_flow
        return None

    def _build_transport(self) -> Any:
        """Wrap `ApiClientConfig.transport` with a `RetryTransport` when retries are enabled."""
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
        """Adapt `ApiClientConfig.event_hooks` for the target httpx client (sync or async)."""
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
        """Get the underlying `httpx.Client`, constructing a new one if not set."""
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
        """Get the underlying `httpx.AsyncClient`, constructing a new one if not set."""
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
        """Send a request for the given endpoint synchronously.

        Args:
            endpoint: The endpoint descriptor to invoke.
            path_params: Values for the endpoint's path template placeholders.
                Validated against `Endpoint.path_params_model` when set.
            query_params: Query string values. Validated against
                `Endpoint.query_params_model` when set.
            body: Request body. Coerced via `Endpoint.request_body_model` when set.
            headers: Per-request headers; merged on top of the client defaults.

        Returns:
            An `ApiResponse[T]` containing the parsed body.

        Raises:
            ApiTransportError: When the underlying httpx transport fails
                (timeout, connection error, etc.).
            ApiResponseError: A documented error status was returned and
                the body parsed against the registered model.
            ApiResponseErrorParse: The body failed to parse against the
                declared model (success or error path).
            UnexpectedStatus: An `Enpoint`'s undocumented status error was returned and
                `ApiClientConfig.suppress_unexpected_status` is `False`.
        """
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
        """Send a request for the given endpoint asynchronously.

        Args:
            endpoint: The endpoint descriptor to invoke.
            path_params: Values for the endpoint's path template placeholders.
                Validated against `Endpoint.path_params_model` when set.
            query_params: Query string values. Validated against
                `Endpoint.query_params_model` when set.
            body: Request body. Coerced via `Endpoint.request_body_model` when set.
            headers: Per-request headers; merged on top of the client defaults.

        Returns:
            An `ApiResponse[T]` containing the parsed body.

        Raises:
            ApiTransportError: When the underlying httpx transport fails
                (timeout, connection error, etc.).
            ApiResponseError: A documented error status was returned and
                the body parsed against the registered model.
            ApiResponseErrorParse: The body failed to parse against the
                declared model (success or error path).
            UnexpectedStatus: An `Enpoint`'s undocumented status error was returned and
                `ApiClientConfig.suppress_unexpected_status` is `False`.
        """
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
