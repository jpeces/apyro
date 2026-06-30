"""Example usage of the Frankfurter API client built on apyro.

Run with:  uv run python -m examples.frankfurter.main
"""

from datetime import date

import httpx

from apyro import (
    ApiClient,
    ApiClientConfig,
    ApiResponseError,
    UnexpectedStatus,
)
from examples.frankfurter.api import (
    BASE_URL,
    aget_currencies,
    aget_rate,
    get_currencies,
    get_currency,
    get_providers,
    get_rate,
    get_rates,
)
from examples.frankfurter.models import Currency, GetRateExpand, GetRatesGroup, Rate


MOCK_RATES = [
    {"date": "2024-01-15", "base": "EUR", "quote": "USD", "rate": 1.089},
    {"date": "2024-01-15", "base": "EUR", "quote": "GBP", "rate": 0.8623},
]
MOCK_RATE = {"date": "2026-03-25", "base": "EUR", "quote": "USD", "rate": 1.1568}
MOCK_CURRENCY = {
    "iso_code": "USD",
    "iso_numeric": "840",
    "name": "United States Dollar",
    "symbol": "$",
    "providers": ["ECB", "BOC", "FED"],
}
MOCK_CURRENCIES = [
    {
        "iso_code": "EUR",
        "iso_numeric": "978",
        "name": "Euro",
        "symbol": "€",
        "start_date": "1999-01-04",
        "end_date": "2026-03-17",
        "providers": ["ECB"],
    },
    {
        "iso_code": "USD",
        "iso_numeric": "840",
        "name": "United States Dollar",
        "symbol": "$",
        "start_date": "1999-01-04",
        "end_date": "2026-03-17",
        "providers": ["ECB", "BOC", "FED"],
    },
]
MOCK_PROVIDERS = [
    {
        "key": "ECB",
        "name": "European Central Bank",
        "country_code": "EU",
        "rate_type": "reference",
        "pivot_currency": "EUR",
        "currencies": ["USD", "GBP"],
    }
]
MOCK_NOT_FOUND = {"status": 404, "message": "No data found for the requested resource."}
MOCK_SERVER_ERROR = {"status": 500, "message": "Internal server error"}


def _mock_handler(request: httpx.Request) -> httpx.Response:
    route = (request.method, request.url.path)

    if route == ("GET", "/v2/rates"):
        return httpx.Response(200, json=MOCK_RATES)
    if route == ("GET", "/v2/rate/EUR/USD"):
        return httpx.Response(200, json=MOCK_RATE)
    if route == ("GET", "/v2/currency/USD"):
        return httpx.Response(200, json=MOCK_CURRENCY)
    if route == ("GET", "/v2/currencies"):
        return httpx.Response(200, json=MOCK_CURRENCIES)
    if route == ("GET", "/v2/providers"):
        return httpx.Response(200, json=MOCK_PROVIDERS)
    if route == ("GET", "/v2/currency/XXX"):
        return httpx.Response(404, json=MOCK_NOT_FOUND)
    if route == ("GET", "/v2/providers/error"):
        return httpx.Response(500, json=MOCK_SERVER_ERROR)

    return httpx.Response(404, json={"message": f"Mock: {request.url}"})


def _make_client(suppress: bool = False) -> ApiClient:
    transport = httpx.MockTransport(_mock_handler)
    config = ApiClientConfig(transport=transport, suppress_unexpected_status=suppress)
    return ApiClient(BASE_URL, configuration=config)


def demo_sync() -> None:
    print("=" * 60)
    print("SYNC CLIENT (MockTransport)")
    print("=" * 60)

    with _make_client() as client:
        # 1. Latest rates — typed list response
        r = get_rates(client)
        print(f"\n1. GET /rates → {r.status_code}")
        if r.parsed is not None:
            print(
                f"   parsed: {r.parsed[0].base}/{r.parsed[0].quote} = {r.parsed[0].rate}"
            )
        print(f"   raw:    {r.raw.text[:80]}...")

        # 1b. Rates with query params — from_ alias, dates, enums
        r = get_rates(
            client,
            from_=date(2024, 1, 1),
            to=date(2024, 1, 31),
            base="USD",
            quotes="EUR,GBP",
            group=GetRatesGroup.MONTH,
            expand=GetRateExpand.PROVIDERS,
        )
        print(f"\n1b. GET /rates?from=...&group=month → {r.status_code}")
        print(f"   rendered URL: {str(r.raw.url).replace(BASE_URL, '')}")
        print(f"   query keys: {sorted(r.raw.url.params.keys())}")

        # 2. Single rate pair — path params
        r = get_rate(client, "EUR", "USD")
        print(f"\n2. GET /rate/EUR/USD → {r.status_code}")
        print(f"   parsed: {r.parsed}")
        if r.parsed is not None:
            print(
                f"   rate is Decimal: {r.parsed.rate} (type={type(r.parsed.rate).__name__})"
            )

        # 3. Currency detail
        r = get_currency(client, "USD")
        print(f"\n3. GET /currency/USD → {r.status_code}")
        if r.parsed is not None:
            print(f"   parsed: {r.parsed.name}, providers={r.parsed.providers}")

        # 4. Currencies list
        r = get_currencies(client)
        print(f"\n4. GET /currencies → {r.status_code}")
        if r.parsed is not None:
            print(
                f"   parsed: {len(r.parsed)} currencies, first={r.parsed[0].iso_code}"
            )

        # 5. Providers
        r = get_providers(client)
        print(f"\n5. GET /providers → {r.status_code}")
        if r.parsed is not None:
            print(f"   parsed: {r.parsed[0].name}")

        # 6. Documented error — 404 with parsed error model
        print("\n6. GET /currency/XXX → expecting documented 404...")
        try:
            get_currency(client, "XXX")
        except ApiResponseError as e:
            print(f"   caught ApiResponseError: status={e.status_code}")
            print(f"   error_model: {e.error_model}")
            print(f"   raw status: {e.raw.status_code}")

    # 7. Undocumented error — 500 raises UnexpectedStatus
    print("\n7. GET /providers (500) → expecting UnexpectedStatus...")
    bad_client = ApiClient(
        BASE_URL,
        configuration=ApiClientConfig(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(500, json=MOCK_SERVER_ERROR)
            ),
        ),
    )
    try:
        get_providers(bad_client)
    except UnexpectedStatus as e:
        print(f"   caught UnexpectedStatus: status={e.status_code}")
        print(f"   content: {e.content.decode()[:60]}...")

    # 8. Suppressed unexpected status — returns parsed=None
    print("\n8. GET /providers (500) with suppress_unexpected_status=True...")
    suppressed = ApiClient(
        BASE_URL,
        configuration=ApiClientConfig(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(500, json=MOCK_SERVER_ERROR)
            ),
            suppress_unexpected_status=True,
        ),
    )
    r = get_providers(suppressed)
    print(f"   status: {r.status_code}, parsed: {r.parsed}")
    suppressed.close()


async def demo_async() -> None:
    print("\n" + "=" * 60)
    print("ASYNC CLIENT (MockTransport)")
    print("=" * 60)

    transport = httpx.MockTransport(_mock_handler)
    config = ApiClientConfig(transport=transport)
    async with ApiClient(BASE_URL, configuration=config) as client:
        r = await aget_rate(client, "EUR", "USD")
        print(f"\n  GET /rate/EUR/USD → {r.status_code}")
        print(f"   parsed: {r.parsed}")
        print(f"   is Rate: {isinstance(r.parsed, Rate)}")

        r = await aget_currencies(client)
        print(f"\n  GET /currencies → {r.status_code}")
        if r.parsed is not None:
            print(f"   parsed: {len(r.parsed)} currencies")
            print(
                f"   is list[Currency]: "
                f"{isinstance(r.parsed, list) and all(isinstance(c, Currency) for c in r.parsed)}"
            )


def main() -> None:
    demo_sync()

    import asyncio

    asyncio.run(demo_async())

    print("\n" + "=" * 60)
    print("All demos passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
