from datetime import date

from apyro import ApiClient, ApiResponse

from examples.frankfurter import endpoints
from examples.frankfurter.models import (
    Currency,
    GetCurrenciesScope,
    GetRateExpand,
    GetRatesGroup,
    Provider,
    Rate,
)

BASE_URL = "https://api.frankfurter.dev/v2"


def get_rates(
    client: ApiClient,
    *,
    date: date | None = None,
    from_: date | None = None,
    to: date | None = None,
    base: str | None = None,
    quotes: str | None = None,
    providers: str | None = None,
    group: GetRatesGroup | None = None,
    expand: GetRateExpand | None = None,
) -> ApiResponse[list[Rate]]:
    return client.request(
        endpoints.GET_RATES,
        query_params={
            "date": date,
            "from": from_,
            "to": to,
            "base": base,
            "quotes": quotes,
            "providers": providers,
            "group": group,
            "expand": expand,
        },
    )


async def aget_rates(
    client: ApiClient,
    *,
    date: date | None = None,
    from_: date | None = None,
    to: date | None = None,
    base: str | None = None,
    quotes: str | None = None,
    providers: str | None = None,
    group: GetRatesGroup | None = None,
    expand: GetRateExpand | None = None,
) -> ApiResponse[list[Rate]]:
    return await client.arequest(
        endpoints.GET_RATES,
        query_params={
            "date": date,
            "from": from_,
            "to": to,
            "base": base,
            "quotes": quotes,
            "providers": providers,
            "group": group,
            "expand": expand,
        },
    )


def get_rate(
    client: ApiClient,
    base: str,
    quote: str,
    *,
    date: date | None = None,
    providers: str | None = None,
    expand: GetRateExpand | None = None,
) -> ApiResponse[Rate]:
    return client.request(
        endpoints.GET_RATE,
        path_params={"base": base, "quote": quote},
        query_params={"date": date, "providers": providers, "expand": expand},
    )


async def aget_rate(
    client: ApiClient,
    base: str,
    quote: str,
    *,
    date: date | None = None,
    providers: str | None = None,
    expand: GetRateExpand | None = None,
) -> ApiResponse[Rate]:
    return await client.arequest(
        endpoints.GET_RATE,
        path_params={"base": base, "quote": quote},
        query_params={"date": date, "providers": providers, "expand": expand},
    )


def get_currency(client: ApiClient, code: str) -> ApiResponse[Currency]:
    return client.request(
        endpoints.GET_CURRENCY,
        path_params={"code": code},
    )


async def aget_currency(client: ApiClient, code: str) -> ApiResponse[Currency]:
    return await client.arequest(
        endpoints.GET_CURRENCY,
        path_params={"code": code},
    )


def get_currencies(
    client: ApiClient,
    *,
    scope: GetCurrenciesScope | None = None,
    providers: str | None = None,
) -> ApiResponse[list[Currency]]:
    return client.request(
        endpoints.GET_CURRENCIES,
        query_params={"scope": scope, "providers": providers},
    )


async def aget_currencies(
    client: ApiClient,
    *,
    scope: GetCurrenciesScope | None = None,
    providers: str | None = None,
) -> ApiResponse[list[Currency]]:
    return await client.arequest(
        endpoints.GET_CURRENCIES,
        query_params={"scope": scope, "providers": providers},
    )


def get_providers(client: ApiClient) -> ApiResponse[list[Provider]]:
    return client.request(endpoints.GET_PROVIDERS)


async def aget_providers(client: ApiClient) -> ApiResponse[list[Provider]]:
    return await client.arequest(endpoints.GET_PROVIDERS)
