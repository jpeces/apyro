from decimal import Decimal

import httpx
from pydantic import BaseModel

from apyro import Endpoint, HttpMethod

BASE_URL = "https://api.example.com"


class ErrorBody(BaseModel):
    status: int
    message: str


class Item(BaseModel):
    id: int
    name: str


class ItemDetail(BaseModel):
    id: int
    name: str
    price: Decimal


class ListItemsParams(BaseModel):
    limit: int | None = None
    offset: int | None = None


class CreateItemBody(BaseModel):
    name: str
    price: Decimal


GET_ITEMS = Endpoint[list[Item]](
    method=HttpMethod.GET,
    path="/items",
    response_model=list[Item],
    query_params_model=ListItemsParams,
)

GET_ITEM = Endpoint[ItemDetail](
    method=HttpMethod.GET,
    path="/items/{id}",
    response_model=ItemDetail,
    errors={404: ErrorBody},
)

CREATE_ITEM = Endpoint[Item](
    method=HttpMethod.POST,
    path="/items",
    response_model=Item,
    request_body_model=CreateItemBody,
    errors={422: ErrorBody},
)

_ITEMS = [
    {"id": 1, "name": "Widget"},
    {"id": 2, "name": "Gadget"},
]
_ITEM_DETAIL = {"id": 1, "name": "Widget", "price": "9.99"}
_ERROR_404 = {"status": 404, "message": "Not found"}
_ERROR_500 = {"status": 500, "message": "Internal server error"}


def mock_handler(request: httpx.Request) -> httpx.Response:
    route = (request.method, request.url.path)
    if route == ("GET", "/items"):
        return httpx.Response(200, json=_ITEMS)
    if route == ("GET", "/items/1"):
        return httpx.Response(200, json=_ITEM_DETAIL)
    if route == ("GET", "/items/404"):
        return httpx.Response(404, json=_ERROR_404)
    if route == ("GET", "/items/500"):
        return httpx.Response(500, json=_ERROR_500)
    if route == ("POST", "/items"):
        return httpx.Response(201, json={"id": 99, "name": "Created"})
    return httpx.Response(404, json=_ERROR_404)
