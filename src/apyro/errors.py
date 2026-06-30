from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    import httpx


class ApiError(Exception):
    """Base exception for all API client errors."""


class ApiTransportError(ApiError):
    """Raised when a network/transport request fails (timeout, connect, etc.)."""


class ApiResponseError(ApiError):
    """Raised when the response has a documented error status code.

    Carries the parsed error model (when the endpoint registers one for the
    status code) and the raw httpx response.
    """

    def __init__(
        self, status_code: int, error_model: BaseModel | None, raw: httpx.Response
    ) -> None:
        self.status_code = status_code
        self.error_model = error_model
        self.raw = raw
        super().__init__(f"HTTP {status_code}")


class UnexpectedStatus(ApiError):
    """Raised when the response status is not implemented/documented.

    Only raised if ``ApiClientConfig.suppress_unexpected_status`` is ``False``;
    otherwise the client returns an :class:`ApiResponse` with ``parsed=None``.
    """

    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content
        super().__init__(
            f"Unexpected status code: {status_code}\n\n"
            f"Response content:\n{content.decode(errors='ignore')}"
        )


__all__ = [
    "ApiError",
    "ApiTransportError",
    "ApiResponseError",
    "UnexpectedStatus",
]
