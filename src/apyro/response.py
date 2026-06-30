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

    Callers can go typed via ``response.parsed`` or raw via ``response.raw``
    without two different code paths. The flat ``status_code``, ``content``,
    and ``headers`` fields are convenience mirrors of ``raw``.
    """

    status_code: HTTPStatus
    content: bytes
    headers: Mapping[str, str]
    parsed: T | None
    raw: httpx.Response


__all__ = ["ApiResponse"]
