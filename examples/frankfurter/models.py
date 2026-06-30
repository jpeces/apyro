from datetime import date as date_aliased
from decimal import Decimal
from enum import StrEnum

from pydantic import AnyUrl, BaseModel, Field

# ---- Parameters ---------------------------------------------------------------------


class GetRateExpand(StrEnum):
    """
    Comma-separated list of optional fields to include per record.
    Currently supports `providers`, which adds an array of `{ key, rate }` objects
    per record showing each provider's individual rate. Outliers excluded from the
    blend (and providers whose rate was overridden by a currency peg) are flagged
    with `excluded: true`.

    The field is omitted on synthesized peg rows where no provider published the quote.
    In CSV output, the `providers` column is encoded as `KEY:RATE` pairs joined by
     `|`, with a trailing `*` on excluded entries (e.g. `ECB:0.92|FED:1.50*`).",
    """

    PROVIDERS = "providers"


class GetRatesGroup(StrEnum):
    """Downsample rates by time period. Only applies to date ranges."""

    MONTH = "month"
    WEEK = "week"


class GetCurrenciesScope(StrEnum):
    """Set to 'all' to include legacy currencies"""

    ALL = "all"


class PublishCadence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ---- Responses ----------------------------------------------------------------------


class ResponseError(BaseModel):
    """
    Attributes:
        status (int): Status code
        message (str): Error message
    """

    status: int
    message: str


class Currency(BaseModel):
    iso_code: str = Field(description="ISO 4217 currency code")
    iso_numeric: str | None = Field(default=None, description="ISO 4217 numeric code")
    name: str = Field(description="Full currency name")
    symbol: str | None = Field(default=None, description="Currency symbol")
    start_date: date_aliased | None = Field(
        default=None, description="Earliest available date"
    )
    end_date: date_aliased | None = Field(
        default=None, description="Latest available date"
    )
    providers: list[str] = Field(description="Provider keys that publish this currency")


class Provider(BaseModel):
    key: str = Field(description="Provider identifier")
    name: str = Field(description="Full provider name")
    country_code: str | None = Field(
        default=None, description="ISO 3166-1 alpha-2 country code"
    )
    rate_type: str | None = Field(
        default=None, description="Official rate type as used by the source"
    )
    pivot_currency: str | None = Field(
        default=None, description="Base currency for published rates"
    )
    data_url: AnyUrl | None = Field(default=None, description="Link to the data source")
    terms_url: AnyUrl | None = Field(default=None, description="Link to terms of use")
    start_date: date_aliased | None = Field(
        default=None, description="Earliest available date"
    )
    end_date: date_aliased | None = Field(
        default=None, description="Latest available date"
    )
    publish_cadence: PublishCadence | None = Field(
        default=None,
        description=(
            "How often the provider publishes rates. Determines the unit of "
            "publishes_missed: a count of days, ISO weeks, or calendar months. "
            "Null for historical-only providers with no scheduled cadence."
        ),
    )
    publishes_missed: int | None = Field(
        default=None,
        description=(
            "Number of expected publishes missed since end_date, in units of "
            "publish_cadence. For daily providers, counts scheduled publish days "
            "strictly between end_date and today. For weekly and monthly providers, "
            "counts ISO weeks or calendar months between the latest imported bucket "
            "and the bucket whose publish window has already started. Null when the "
            "provider has no scheduled cadence or no imported data."
        ),
    )
    currencies: list[str] = Field(
        default=..., description="Currency codes covered by this provider"
    )


class RateProvider(BaseModel):
    key: str = Field(description="Provider key")
    rate: Decimal = Field(description="Provider's rate, rebased to the row's base")
    excluded: bool | None = Field(
        default=None,
        description=(
            "Present and true when this entry did not contribute to the blended rate"
        ),
    )


class Rate(BaseModel):
    date: date_aliased = Field(description="The date of the rate")
    base: str = Field(description="Base currency code")
    quote: str = Field(description="Quote currency code")
    rate: Decimal = Field(description="Exchange rate value")
    providers: list[RateProvider] | None = Field(
        default=None,
        description=(
            "Per-provider rates for this pair. Present only when `expand=providers` "
            "is set. Each entry has the provider's published rate "
            "(rebased to the row's base). Entries with `excluded: true` did not "
            "contribute to the blended `rate` — either flagged as outliers by the "
            "consensus filter, or overridden by a currency peg. Omitted on synthesized "
            "peg rows where no provider published the quote."
        ),
    )
