import asyncio
from collections import Counter
from typing import Any

import httpx
import pytest

from apyro import (
    ApiClient,
    ApiClientConfig,
    ApiTransportError,
    Endpoint,
    HttpMethod,
)


def test_event_hooks_sync() -> None:
    fired = Counter()

    def resp_hook(_response: Any) -> None:
        fired["response"] += 1

    cfg = ApiClientConfig(
        retries=0,
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"ok": True})
        ),
        event_hooks={"response": [resp_hook]},
    )
    ep = Endpoint(method=HttpMethod.GET, path="/", response_model=dict)
    ApiClient("https://x", configuration=cfg).request(ep)
    assert fired["response"] == 1


def test_event_hooks_async() -> None:
    fired = Counter()

    def resp_hook(_response: Any) -> None:
        fired["response"] += 1

    cfg = ApiClientConfig(
        retries=0,
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"ok": True})
        ),
        event_hooks={"response": [resp_hook]},
    )
    ep = Endpoint(method=HttpMethod.GET, path="/", response_model=dict)

    async def _run() -> None:
        async with ApiClient("https://x", configuration=cfg) as c:
            await c.arequest(ep)

    asyncio.run(_run())
    assert fired["response"] == 1


def test_event_hooks_async_pass_through() -> None:
    fired = Counter()

    async def async_hook(_response: Any) -> None:
        fired["async"] += 1

    cfg = ApiClientConfig(
        retries=0,
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"ok": True})
        ),
        event_hooks={"response": [async_hook]},
    )
    ep = Endpoint(method=HttpMethod.GET, path="/", response_model=dict)

    async def _run() -> None:
        async with ApiClient("https://x", configuration=cfg) as c:
            await c.arequest(ep)

    asyncio.run(_run())
    assert fired["async"] == 1


def test_transport_error_raises_api_transport_error() -> None:
    def failing(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    cfg = ApiClientConfig(retries=0, transport=httpx.MockTransport(failing))
    ep = Endpoint(method=HttpMethod.GET, path="/", response_model=dict)
    client = ApiClient("https://x", configuration=cfg)
    try:
        with pytest.raises(ApiTransportError):
            client.request(ep)
    finally:
        client.close()


def test_resolve_auth_basic() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"ok": True})

    cfg = ApiClientConfig(
        retries=0,
        username="u",
        password="p",
        transport=httpx.MockTransport(handler),
    )
    ep = Endpoint(method=HttpMethod.GET, path="/", response_model=dict)
    ApiClient("https://x", configuration=cfg).request(ep)
    assert "authorization" in seen[0].headers


def test_resolve_auth_flow() -> None:
    seen: list[httpx.Request] = []

    def flow(req: httpx.Request) -> httpx.Request:
        req.headers["X-Custom-Auth"] = "tok"
        return req

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"ok": True})

    cfg = ApiClientConfig(
        retries=0,
        auth_flow=flow,
        transport=httpx.MockTransport(handler),
    )
    ep = Endpoint(method=HttpMethod.GET, path="/", response_model=dict)
    ApiClient("https://x", configuration=cfg).request(ep)
    assert seen[0].headers["x-custom-auth"] == "tok"


def test_retries_triggered() -> None:
    calls = {"n": 0}

    def flaky(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("transient")
        return httpx.Response(200, json={"ok": True})

    cfg = ApiClientConfig(
        retries=2,
        backoff_factor=0.0,
        transport=httpx.MockTransport(flaky),
    )
    ep = Endpoint(method=HttpMethod.GET, path="/", response_model=dict)
    client = ApiClient("https://x", configuration=cfg)
    try:
        r = client.request(ep)
        assert r.parsed == {"ok": True}
        assert calls["n"] == 3
    finally:
        client.close()
