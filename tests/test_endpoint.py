import json
from decimal import Decimal

import httpx
import pytest

from apyro import ApiResponseError, Endpoint, HttpMethod, UnexpectedStatus

from _mocks import CREATE_ITEM, ErrorBody, GET_ITEM, GET_ITEMS


def test_build_request_renders_path() -> None:
    client = httpx.Client(base_url="https://api.example.com")
    req = GET_ITEM.build_request(client, path_params={"id": 1})
    assert req.url.path == "/items/1"
    client.close()


def test_build_request_query_params_none_excluded() -> None:
    client = httpx.Client(base_url="https://api.example.com")
    req = GET_ITEMS.build_request(client, query_params={"limit": 10, "offset": None})
    assert req.url.params["limit"] == "10"
    assert "offset" not in req.url.params
    client.close()


def test_build_request_body_model_serialized() -> None:
    client = httpx.Client(base_url="https://api.example.com")
    req = CREATE_ITEM.build_request(client, body={"name": "Widget", "price": "9.99"})
    data = json.loads(req.content)
    assert data["name"] == "Widget"
    assert data["price"] == "9.99"
    client.close()


def test_parse_response_success() -> None:
    raw = httpx.Response(200, json={"id": 1, "name": "Widget", "price": "9.99"})
    r = GET_ITEM.parse_response(raw)
    assert r.parsed is not None
    assert r.parsed.id == 1
    assert isinstance(r.parsed.price, Decimal)


def test_parse_response_documented_error() -> None:
    raw = httpx.Response(404, json={"status": 404, "message": "Not found"})
    with pytest.raises(ApiResponseError) as exc:
        GET_ITEM.parse_response(raw)
    assert exc.value.status_code == 404
    assert isinstance(exc.value.error_model, ErrorBody)
    assert exc.value.error_model.message == "Not found"


def test_parse_response_undocumented_error() -> None:
    raw = httpx.Response(500, json={"status": 500, "message": "Internal"})
    with pytest.raises(UnexpectedStatus) as exc:
        GET_ITEM.parse_response(raw)
    assert exc.value.status_code == 500


def test_parse_response_suppress_unexpected() -> None:
    raw = httpx.Response(500, json={"status": 500, "message": "Internal"})
    r = GET_ITEM.parse_response(raw, suppress_unexpected_status=True)
    assert r.parsed is None
    assert r.status_code == 500


def test_parse_response_custom_handler() -> None:
    ep = Endpoint(
        method=HttpMethod.GET,
        path="/raw",
        response_model=str,
        response_handler=lambda resp: resp.text,
    )
    raw = httpx.Response(200, text="hello")
    r = ep.parse_response(raw)
    assert r.parsed == "hello"


def test_parse_response_documented_error_malformed_body() -> None:
    ep = Endpoint(
        method=HttpMethod.GET,
        path="/things",
        response_model=dict,
        errors={500: ErrorBody},
    )
    raw = httpx.Response(500, json={"unexpected": "shape"})
    with pytest.raises(ApiResponseError) as exc:
        ep.parse_response(raw)
    assert exc.value.status_code == 500
    assert exc.value.error_model is None
    assert exc.value.raw is raw
