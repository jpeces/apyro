from collections.abc import Callable, Iterable
from dataclasses import dataclass
from ssl import SSLContext
from typing import Any


@dataclass(slots=True, frozen=True, kw_only=True)
class ApiClientConfig:
    """Configuration for :class:`ApiClient`.

    Controls timeouts, retries, SSL verification, redirects, authentication,
    and how unexpected (undocumented) error statuses are handled.
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
