from collections.abc import Callable, Iterable
from dataclasses import dataclass
from ssl import SSLContext
from typing import Any


@dataclass(slots=True, frozen=True, kw_only=True)
class ApiClientConfig:
    """Configuration for `ApiClient`.

    Controls timeouts, retries, SSL verification, redirects, authentication,
    and how unexpected (undocumented) error statuses are handled.

    Parameters:
        timeout: Request timeout in seconds, applied to every httpx call.
        retries: Number of automatic retries on transport failures and
            statuses in `retry_status_list`. Set to `0` to disable.
        backoff_factor: Multiplier applied to the exponential backoff between
            retries (httpx-retries semantics).
        retry_status_list: HTTP status codes that trigger a retry. Ignored
            when `retries` is `0`.
        verify_ssl: SSL verification mode passed to httpx: `True` for default
            CA verification, `False` to skip, a path string or `SSLContext`
            for custom verification.
        follow_redirects: Whether httpx should follow 3xx redirects.
        username: Username for HTTP basic auth. Pairs with `password`.
        password: Password for HTTP basic auth. Pairs with `username`.
        auth_flow: Custom httpx auth callable, used when `username`/`password`
            are not set. Receives the request and returns the auth tuple.
        suppress_unexpected_status: When `True`, undocumented status error
            responses are returned as `ApiResponse` with `parsed=None`
            instead of raising `UnexpectedStatus`.
        transport: Custom httpx transport to use as the base transport
            (e.g. `httpx.MockTransport` in tests). Wrapped by `RetryTransport`
            when `retries` is enabled.
        event_hooks: httpx event_hooks map. Sync hooks are auto-wrapped to
            coroutines for the async client, so one config works for both.
    """

    timeout: float = 30.0
    retries: int = 3
    backoff_factor: float = 1.0
    retry_status_list: Iterable[int] | None = None
    verify_ssl: bool | str | SSLContext = True
    follow_redirects: bool = False
    username: str | bytes | None = None
    password: str | bytes | None = None
    auth_flow: Callable[[Any], Any] | None = None
    suppress_unexpected_status: bool = False
    transport: Any | None = None
    event_hooks: dict[str, list[Callable[[Any], Any]]] | None = None


__all__ = ["ApiClientConfig"]
