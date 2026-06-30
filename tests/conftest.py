from collections.abc import Iterator

import httpx
import pytest

from apyro import ApiClient, ApiClientConfig

from _mocks import BASE_URL, mock_handler


@pytest.fixture
def client() -> Iterator[ApiClient]:
    config = ApiClientConfig(transport=httpx.MockTransport(mock_handler))
    c = ApiClient(BASE_URL, configuration=config)
    try:
        yield c
    finally:
        c.close()
