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

    Carries the parsed error model (the model registered in
    `Endpoint.errors` for the status) and the raw httpx response.
    """

    def __init__(
        self, status_code: int, error_model: BaseModel, raw: httpx.Response
    ) -> None:
        """Initialize the `ApiResponseError`.

        Args:
            status_code: The HTTP status code that triggered the error.
            error_model: The parsed error body, validated against the model
                registered in `Endpoint.errors` for the status.
            raw: The original `httpx.Response` for further inspection.
        """
        self.status_code = status_code
        self.error_model = error_model
        self.raw = raw
        super().__init__(f"HTTP {status_code}")


class ApiResponseErrorParse(ApiError):
    """Raised when a response body did not parse against the declared model.

    Covers both paths: a documented error status whose body didn't match the
    model registered in `Endpoint.errors`, and a success status whose body
    didn't match `Endpoint.response_model`. The underlying parse error is
    chained via `__cause__` (raise the new exception with `from exc`).
    `ApiResponseErrorParse` is *not* a subclass of `ApiResponseError`:
    the typed model's invariant (`error_model` is non-`None`) only holds
    in the parsed case.
    """

    def __init__(
        self,
        status_code: int,
        body: bytes,
        raw: httpx.Response,
    ) -> None:
        """Initialize the `ApiResponseErrorParse`.

        Args:
            status_code: The HTTP status code of the response that failed to parse.
            body: The raw response body that failed to parse.
            raw: The original `httpx.Response` for further inspection.
        """
        self.status_code = status_code
        self.body = body
        self.raw = raw
        super().__init__(f"HTTP {status_code} (body did not match the declared model)")


class UnexpectedStatus(ApiError):
    """Raised when the response status is not implemented/documented.

    Only raised if ``ApiClientConfig.suppress_unexpected_status`` is ``False``;
    otherwise the client returns an :class:`ApiResponse` with ``parsed=None``.
    """

    def __init__(self, status_code: int, content: bytes) -> None:
        """Initialize the `UnexpectedStatus`.

        Args:
            status_code: The undocumented HTTP status code returned by the server.
            content: The raw response body for diagnostic purposes.
        """
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
    "ApiResponseErrorParse",
    "UnexpectedStatus",
]
