import asyncio
from decimal import Decimal

import httpx
import pytest

from apyro import ApiClient, ApiClientConfig, ApiResponseError, UnexpectedStatus

from _mocks import BASE_URL, CREATE_ITEM, GET_ITEM, GET_ITEMS, ErrorBody, mock_handler


def test_sync_get_list(client: ApiClient) -> None:
    r = client.request(GET_ITEMS)
    assert r.parsed is not None
    assert len(r.parsed) == 2
    assert r.parsed[0].id == 1


def test_sync_get_list_with_query(client: ApiClient) -> None:
    r = client.request(GET_ITEMS, query_params={"limit": 10, "offset": None})
    assert r.parsed is not None
    assert "limit" in r.raw.url.params
    assert "offset" not in r.raw.url.params


def test_sync_get_single(client: ApiClient) -> None:
    r = client.request(GET_ITEM, path_params={"id": 1})
    assert r.parsed is not None
    assert r.parsed.id == 1
    assert isinstance(r.parsed.price, Decimal)


def test_sync_post(client: ApiClient) -> None:
    r = client.request(CREATE_ITEM, body={"name": "Widget", "price": "9.99"})
    assert r.parsed is not None
    assert r.parsed.id == 99


def test_sync_documented_error(client: ApiClient) -> None:
    with pytest.raises(ApiResponseError) as exc:
        client.request(GET_ITEM, path_params={"id": 404})
    assert exc.value.status_code == 404
    assert isinstance(exc.value.error_model, ErrorBody)


def test_sync_undocumented_error(client: ApiClient) -> None:
    with pytest.raises(UnexpectedStatus) as exc:
        client.request(GET_ITEM, path_params={"id": 500})
    assert exc.value.status_code == 500


def test_sync_suppress_unexpected() -> None:
    cfg = ApiClientConfig(
        transport=httpx.MockTransport(mock_handler),
        suppress_unexpected_status=True,
    )
    c = ApiClient(BASE_URL, configuration=cfg)
    try:
        r = c.request(GET_ITEM, path_params={"id": 500})
        assert r.parsed is None
        assert r.status_code == 500
    finally:
        c.close()


def test_async_get_list() -> None:
    async def _run() -> None:
        cfg = ApiClientConfig(transport=httpx.MockTransport(mock_handler))
        async with ApiClient(BASE_URL, configuration=cfg) as c:
            r = await c.arequest(GET_ITEMS)
            assert r.parsed is not None
            assert len(r.parsed) == 2

    asyncio.run(_run())


def test_async_get_single() -> None:
    async def _run() -> None:
        cfg = ApiClientConfig(transport=httpx.MockTransport(mock_handler))
        async with ApiClient(BASE_URL, configuration=cfg) as c:
            r = await c.arequest(GET_ITEM, path_params={"id": 1})
            assert r.parsed is not None
            assert r.parsed.id == 1

    asyncio.run(_run())


def test_async_documented_error() -> None:
    async def _run() -> None:
        cfg = ApiClientConfig(transport=httpx.MockTransport(mock_handler))
        async with ApiClient(BASE_URL, configuration=cfg) as c:
            with pytest.raises(ApiResponseError) as exc:
                await c.arequest(GET_ITEM, path_params={"id": 404})
            assert exc.value.status_code == 404

    asyncio.run(_run())


def test_close() -> None:
    cfg = ApiClientConfig(transport=httpx.MockTransport(mock_handler))
    c = ApiClient(BASE_URL, configuration=cfg)
    c.get_client()
    c.close()
    assert c._client is None


def test_aclose() -> None:
    async def _run() -> None:
        cfg = ApiClientConfig(transport=httpx.MockTransport(mock_handler))
        c = ApiClient(BASE_URL, configuration=cfg)
        c.get_async_client()
        await c.aclose()
        assert c._async_client is None

    asyncio.run(_run())
