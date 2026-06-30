"""Declarative, pydantic-driven HTTP API client built on httpx."""

from importlib.metadata import version as _version

from apyro.client import ApiClient
from apyro.config import ApiClientConfig
from apyro.endpoint import Endpoint, HttpMethod
from apyro.errors import (
    ApiError,
    ApiResponseError,
    ApiTransportError,
    UnexpectedStatus,
)
from apyro.response import ApiResponse

__version__ = _version("apyro")

__all__ = [
    "ApiClient",
    "ApiClientConfig",
    "ApiResponse",
    "ApiResponseError",
    "ApiError",
    "ApiTransportError",
    "Endpoint",
    "HttpMethod",
    "UnexpectedStatus",
    "__version__",
]
