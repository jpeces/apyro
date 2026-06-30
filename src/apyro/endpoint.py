from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

from apyro.errors import ApiResponseError, UnexpectedStatus
from apyro.response import ApiResponse

if TYPE_CHECKING:
    import httpx

    _RequestBuilder = httpx.Client | httpx.AsyncClient

T = TypeVar("T")


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@dataclass
class Endpoint(Generic[T]):
    """Declarative, spec-agnostic description of an API operation.

    Generic parameter ``T`` is the parsed success type returned by
    ``ApiResponse.parsed``. Validation of path/query/body parameters is done
    via their pydantic models when provided.

    An endpoint owns the full transform pipeline: rendering its path template,
    serializing query/body against its models, and parsing a response against
    its ``response_model`` / ``response_handler`` / ``errors`` map.
    """

    method: HttpMethod
    path: str
    response_model: type[T]
    path_params_model: type[BaseModel] | None = None
    query_params_model: type[BaseModel] | None = None
    request_body_model: type[BaseModel] | None = None
    response_handler: Callable[[httpx.Response], T] | None = None
    errors: dict[int, type[BaseModel]] = field(default_factory=dict)

    def build_request(
        self,
        client: _RequestBuilder,
        *,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Request:
        """Render this endpoint into an ``httpx.Request`` via ``client``."""
        path_params = path_params or {}
        if self.path_params_model is not None:
            path_params = self.path_params_model(**path_params).model_dump(mode="json")
        rendered_path = self.path.format(**path_params)

        query: dict[str, Any] = {}
        if query_params:
            if self.query_params_model is not None:
                query = self.query_params_model(**query_params).model_dump(
                    mode="json", exclude_none=True, by_alias=True
                )
            else:
                query = {k: v for k, v in query_params.items() if v is not None}

        json_body: Any = None
        if body is not None:
            if self.request_body_model is not None:
                if not isinstance(body, BaseModel):
                    body = self.request_body_model(**body)
                json_body = body.model_dump(mode="json", by_alias=True)
            else:
                json_body = body

        return client.build_request(
            str(self.method),
            rendered_path,
            params=query or None,
            json=json_body,
            headers=headers,
        )

    def parse_response(
        self,
        raw: httpx.Response,
        *,
        suppress_unexpected_status: bool = False,
    ) -> ApiResponse[T]:
        """Parse an ``httpx.Response`` against this endpoint's models.

        Raises :class:`ApiResponseError` for documented error statuses (always),
        and :class:`UnexpectedStatus` for undocumented 4xx/5xx unless
        ``suppress_unexpected_status`` is set, in which case an
        :class:`ApiResponse` with ``parsed=None`` is returned.
        """
        status = raw.status_code

        if status in self.errors:
            error_model = None
            error_cls = self.errors[status]
            try:
                error_model = error_cls(**raw.json())
            except Exception:
                error_model = None
            raise ApiResponseError(status, error_model, raw)

        if status >= 400:
            if suppress_unexpected_status:
                return ApiResponse(
                    status_code=HTTPStatus(status),
                    content=raw.content,
                    headers=raw.headers,
                    parsed=None,
                    raw=raw,
                )
            raise UnexpectedStatus(status, raw.content)

        if self.response_handler is not None:
            data = self.response_handler(raw)
        else:
            adapter = TypeAdapter(self.response_model)
            data = adapter.validate_python(raw.json())

        return ApiResponse(
            status_code=HTTPStatus(status),
            content=raw.content,
            headers=raw.headers,
            parsed=data,
            raw=raw,
        )


__all__ = ["HttpMethod", "Endpoint"]
