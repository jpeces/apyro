from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    import httpx

T = TypeVar("T")


@dataclass(slots=True, frozen=True, kw_only=True)
class ApiResponse(Generic[T]):
    """A response from an endpoint.

    Callers can go typed via `response.parsed` or raw via `response.raw`
    without two different code paths. The flat `status_code`, `content`,
    and `headers` fields are convenience mirrors of `raw`.

    Parameters:
        status_code: The HTTP status code returned by the server.
        content: The raw response body as bytes.
        headers: The response headers.
        parsed: The response body parsed against the endpoint's
            `response_model` or `response_handler`, or `None` if not parsed
            (e.g. when `suppress_unexpected_status` returned this response).
        raw: The original `httpx.Response` for full access.
    """

    status_code: HTTPStatus
    content: bytes
    headers: Mapping[str, str]
    parsed: T | None
    raw: httpx.Response


__all__ = ["ApiResponse"]
