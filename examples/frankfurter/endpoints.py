from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field

from apyro import Endpoint, HttpMethod

from examples.frankfurter.models import (
    Currency,
    GetCurrenciesScope,
    GetRateExpand,
    GetRatesGroup,
    Provider,
    Rate,
    ResponseError,
)


class GetRatesParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: Date | None = None
    from_: Date | None = Field(None, alias="from")
    to: Date | None = None
    base: str | None = None
    quotes: str | None = None
    providers: str | None = None
    group: GetRatesGroup | None = None
    expand: GetRateExpand | None = None


class GetRateParams(BaseModel):
    date: Date | None = None
    providers: str | None = None
    expand: GetRateExpand | None = None


class GetCurrenciesParams(BaseModel):
    scope: GetCurrenciesScope | None = None
    providers: str | None = None


GET_RATES = Endpoint[list[Rate]](
    method=HttpMethod.GET,
    path="/rates",
    response_model=list[Rate],
    query_params_model=GetRatesParams,
    errors={404: ResponseError, 422: ResponseError},
)

GET_RATE = Endpoint[Rate](
    method=HttpMethod.GET,
    path="/rate/{base}/{quote}",
    response_model=Rate,
    query_params_model=GetRateParams,
    errors={404: ResponseError, 422: ResponseError},
)

GET_CURRENCY = Endpoint[Currency](
    method=HttpMethod.GET,
    path="/currency/{code}",
    response_model=Currency,
    errors={404: ResponseError},
)

GET_CURRENCIES = Endpoint[list[Currency]](
    method=HttpMethod.GET,
    path="/currencies",
    response_model=list[Currency],
    query_params_model=GetCurrenciesParams,
)

GET_PROVIDERS = Endpoint[list[Provider]](
    method=HttpMethod.GET,
    path="/providers",
    response_model=list[Provider],
)
