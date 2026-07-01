from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

from apyro.errors import ApiResponseError, ApiResponseErrorParse, UnexpectedStatus
from apyro.response import ApiResponse

if TYPE_CHECKING:
    import httpx

    _RequestBuilder = httpx.Client | httpx.AsyncClient

T = TypeVar("T")


class HttpMethod(StrEnum):
    """HTTP verbs supported by `Endpoint`."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@dataclass
class Endpoint(Generic[T]):
    """Declarative description of an API operation.

    Generic parameter `T` is the parsed success type returned by
    `ApiResponse.parsed`. Validation of path/query/body parameters is done
    via their pydantic models when provided.

    An endpoint owns the full transform pipeline: rendering its path template,
    serializing query/body against its models, and parsing a response against
    its `response_model` / `response_handler` / `errors` map.

    Parameters:
        method: The HTTP method for this operation.
        path: The URL path template, with `{placeholder}` segments for path
            parameters.
        response_model: The pydantic model to parse the success response body
            into. Generic parameter `T` is inferred from this.
        path_params_model: Optional pydantic model that validates path
            parameters before rendering the URL. Defaults to `None`.
        query_params_model: Optional pydantic model that validates query
            parameters, dropping `None` values and applying aliases.
            Defaults to `None`.
        request_body_model: Optional pydantic model that validates and
            serializes the request body. Defaults to `None`.
        response_handler: Optional callable that overrides the default
            `TypeAdapter`-based parsing of the success response. Defaults
            to `None`.
        errors: Maps documented error status codes to their pydantic models.
            Each status in this dictionary is parsed and raised as
            `ApiResponseError`. Defaults to an empty dict.
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
        """Render this endpoint into an `httpx.Request` via `client`.

        Args:
            client: The `httpx.Client` or `httpx.AsyncClient` used to build
                the request (provides `base_url` and shared state).
            path_params: Values for `path` placeholders. Validated against
                `path_params_model` when set.
            query_params: Query string values. Validated against
                `query_params_model` when set; `None` values are dropped.
            body: Request body. Coerced via `request_body_model` when set,
                otherwise forwarded as-is.
            headers: Per-request headers, merged on top of the client defaults.

        Returns:
            The fully rendered `httpx.Request` ready to be sent.
        """
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
        """Parse an `httpx.Response` against this endpoint's models.

        Args:
            raw: The `httpx.Response` to parse.
            suppress_unexpected_status: When `True`, undocumented status error
                responses are returned as `ApiResponse` with `parsed=None`
                instead of raising `UnexpectedStatus`. Defaults to `False`.

        Returns:
            An `ApiResponse[T]` with the parsed body, or `parsed=None` when
            `suppress_unexpected_status` returned a status error without a
            registered error model.

        Raises:
            ApiResponseError: An `Endpoint`'s documented error status was returned.
            ApiResponseErrorParse: The body failed to parse against either
                the registered error model (error path) or `response_model`
                (success path).
            UnexpectedStatus: An `Endpoint`'s undocumented status error was returned.
            This error only is raised if `suppress_unexpected_status` is `False`.
        """
        status = raw.status_code

        if status in self.errors:
            error_cls = self.errors[status]
            try:
                error_model = error_cls(**raw.json())
            except Exception as exc:
                raise ApiResponseErrorParse(status, raw.content, raw) from exc
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
            try:
                adapter = TypeAdapter(self.response_model)
                data = adapter.validate_python(raw.json())
            except Exception as exc:
                raise ApiResponseErrorParse(status, raw.content, raw) from exc

        return ApiResponse(
            status_code=HTTPStatus(status),
            content=raw.content,
            headers=raw.headers,
            parsed=data,
            raw=raw,
        )


__all__ = ["HttpMethod", "Endpoint"]
