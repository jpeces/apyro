# apyro

> Declarative, endpoint-as-data HTTP client for Python: typed responses, per-status typed errors, httpx-powered.

An HTTP client for Python. Each API call is a standalone `Endpoint` dataclass, not a method on a client class, so you can share, reuse, and test endpoint definitions independently of the client that sends them. You declare the verb, path, response model, optional pydantic models for path/query/body, and a per-status error map; an `ApiClient` renders the request, sends it through httpx, and parses the response back into your model. httpx gives you a transport; apyro gives you a typed contract on top of it: the response shape is declared upfront, and the library enforces it. The same endpoint and configuration drive both sync and async.

> **Status:** pre-release; not yet on PyPI. Python 3.14+.

## Installation

Install from source (recommended while pre-release):

```bash
git clone https://github.com/jpeces/apyro.git
cd apyro
uv sync
```

Or with pip:

```bash
pip install -e .
```

`uv` is the project manager of record; `pip install -e .` works for users who don't use `uv`.

## Table of contents

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Why apyro?](#why-apyro)
- [Concepts](#concepts)
- [Configuration](#configuration)
- [Error handling](#error-handling)
- [Recipes](#recipes)
- [Full example](#full-example)
- [Development](#development)
- [License](#license)

## Quick start

```python
from datetime import datetime
from pydantic import BaseModel
from apyro import ApiClient, Endpoint, HttpMethod


class Ping(BaseModel):
    ok: bool
    ts: datetime


PING = Endpoint[Ping](
    method=HttpMethod.GET,
    path="/ping",
    response_model=Ping,
)


with ApiClient("https://api.example.com") as client:
    resp = client.request(PING)
    print(resp.parsed.ok, resp.parsed.ts)
```

You describe the response as a pydantic model, declare the call as an `Endpoint` dataclass, and hand it to an `ApiClient`. The client renders the request, sends it through httpx, then parses the response back into your model. Both the typed `resp.parsed` and the raw `resp.raw` are available on the same `ApiResponse`. Authentication, retries, timeouts, and event hooks live on `ApiClientConfig` and apply to every endpoint.

The same shape covers a POST with a typed body and per-status error handling. The `errors` dict maps HTTP status codes to pydantic models. When the server returns a documented error status, apyro parses the body into the registered model and raises `ApiResponseError`:

```python
from pydantic import BaseModel
from apyro import ApiClient, Endpoint, HttpMethod, ApiResponseError, ApiResponseErrorParse


class CreateUser(BaseModel):
    name: str
    email: str


class User(BaseModel):
    id: int
    name: str
    email: str


class UserConflict(BaseModel):
    reason: str
    existing_id: int


CREATE_USER = Endpoint[User](
    method=HttpMethod.POST,
    path="/users",
    request_body_model=CreateUser,
    response_model=User,
    errors={409: UserConflict},
)


with ApiClient("https://api.example.com") as client:
    try:
        user = client.request(
            CREATE_USER,
            body={"name": "Ada", "email": "[email protected]"},
        ).parsed
        print(user.id)
    except ApiResponseError as exc:
        if exc.status_code == 409:
            print(f"Email taken: {exc.error_model.reason}")
    except ApiResponseErrorParse as exc:
        # The endpoint declared 409 → UserConflict, but the body didn't match.
        log(f"409 body was unparseable: {exc.__cause__}")
```

The body dict is validated against `CreateUser`, the 409 response is parsed into `UserConflict`, and `exc.error_model` is statically typed; no `None` check needed. If the body shape ever drifts from the declared model, `ApiResponseErrorParse` is raised instead, with the parse error accessible via `exc.__cause__`.

## How it works

`Endpoint` is the spec: a generic dataclass that names the verb, path, success response model, optional pydantic models for path/query/body inputs, and a `dict[int, type[BaseModel]]` mapping documented error statuses to their parsed shapes. `ApiClient` is the runtime: it owns the underlying httpx client(s), applies configuration, and delegates request rendering and response parsing back to the endpoint. `ApiResponse` is the result: a wrapper over `httpx.Response` that also carries the typed `parsed` value.

When you call `client.request(endpoint)`, the client asks the endpoint to render an `httpx.Request` (via `Endpoint.build_request`), sends it through the underlying httpx client, then asks the endpoint to parse the `httpx.Response` (via `Endpoint.parse_response`) into an `ApiResponse[T]`. The same flow drives `await client.arequest(endpoint)` on the async path.

## Why apyro?

- **Endpoints as data.** An endpoint is a `@dataclass` value. Two consumers can share endpoint definitions without sharing a client class, and the same definition works across sync and async code paths.
- **Typed per-status errors.** Every documented error status gets a pydantic model in `Endpoint.errors`. A 429 response with a `{retry_after: int}` body surfaces as an `ApiResponseError` carrying the parsed model. Instead of catching a generic `HTTPError` and introspecting the body yourself, you catch `ApiResponseError` and `exc.error_model` is the typed error body.
- **httpx-native.** `ApiClient` constructs a real `httpx.Client` / `httpx.AsyncClient` under the hood, so every httpx feature (connection pooling, HTTP/2, proxies, custom transports) is available.
- **Sync + async from one config.** The same `Endpoint` and the same `ApiClientConfig` drive `client.request(...)` and `await client.arequest(...)`. Sync event hooks are auto-wrapped to coroutines, so one config works on both paths.

## Concepts

### `Endpoint[T]`

A generic dataclass describing one operation. Carries the HTTP method, path template, success response model, optional pydantic models that validate path/query/body inputs, and a `dict[int, type[BaseModel]]` mapping documented error statuses to their parsed shapes. Each `Endpoint` instance describes one operation. To call the same path with different parameters, pass different `path_params` to `client.request()`; the endpoint is reused, not redefined. `build_request()` and `parse_response()` are the two halves of the transform pipeline; both are public so you can also drive an endpoint from a test transport.

```python
GET_USER = Endpoint[User](
    method=HttpMethod.GET,
    path="/users/{user_id}",
    path_params_model=UserPath,         # validates {"user_id": "..."} before render
    response_model=User,
    errors={404: UserNotFound},
)
```

### `ApiClient`

The runtime that holds the underlying httpx client(s) and configuration. Constructs the httpx client lazily on first use, so the same `ApiClient` instance can serve `request()` and `arequest()`. Closes cleanly via context managers (`with` / `async with`) or explicit `close()` / `aclose()`. Delegates request rendering and response parsing to the `Endpoint`, so a single `ApiClient` can be reused across many endpoint definitions.

```python
client = ApiClient("https://api.example.com")

resp = client.request(GET_USER, path_params={"user_id": 42})   # sync
resp = await client.arequest(GET_USER, path_params={...})     # async, same endpoint
```

### `ApiClientConfig`

The knobs. Frozen dataclass, kw-only fields. Defaults are 30s timeout and 3 retries with exponential backoff. Anything you don't set inherits the default; anything you set is applied across both clients. Configuration is shared by reference, so passing one `ApiClientConfig` to many `ApiClient` instances gives them the same auth, timeouts, and event hooks.

```python
cfg = ApiClientConfig(
    timeout=10.0,
    retries=5,
    retry_status_list=(429, 503),
    username="svc",
    password=os.environ["API_TOKEN"],
)
prod = ApiClient("https://api.example.com", configuration=cfg)
staging = ApiClient("https://staging.example.com", configuration=cfg)
```

### `ApiResponse[T]`

A frozen wrapper over `httpx.Response` plus the parsed value. `status_code`, `content`, and `headers` mirror the underlying `httpx.Response`; `parsed` is the typed value (or `None` when the server returns an undocumented error status and `suppress_unexpected_status` is `True`). Generic over `T`, the success response model declared on the `Endpoint` that produced it.

```python
resp = client.request(GET_USER, path_params={"user_id": 42})
user: User = resp.parsed              # typed value
resp.status_code                      # HTTPStatus(200)
resp.headers["x-rate-limit-remaining"] # also at resp.raw.headers
resp.raw                              # the underlying httpx.Response
```

## Configuration

`ApiClientConfig` is a frozen, kw-only dataclass. All fields have defaults.

| Field | Type | Default | Description |
|---|---|---|---|
| `timeout` | `float` | `30.0` | Request timeout in seconds, applied to every httpx call. |
| `retries` | `int` | `3` | Number of automatic retries on transport failures and statuses in `retry_status_list`. Set to `0` to disable. |
| `backoff_factor` | `float` | `1.0` | Multiplier for the exponential backoff between retries (httpx-retries semantics). |
| `retry_status_list` | `Iterable[int] \| None` | `None` | HTTP status codes that trigger a retry. Ignored when `retries` is `0`. |
| `verify_ssl` | `bool \| str \| SSLContext` | `True` | SSL verification: `True` for default CA verification, `False` to skip, a path or `SSLContext` for custom. |
| `follow_redirects` | `bool` | `False` | Whether httpx should follow 3xx redirects. |
| `username` | `str \| bytes \| None` | `None` | Username for HTTP basic auth. Pairs with `password`. |
| `password` | `str \| bytes \| None` | `None` | Password for HTTP basic auth. Pairs with `username`. |
| `auth_flow` | `Callable[[Any], Any] \| None` | `None` | Custom httpx auth callable, used when `username`/`password` are not set. See [Share a custom auth flow](#share-a-custom-auth-flow). |
| `suppress_unexpected_status` | `bool` | `False` | When `True`, undocumented 4xx/5xx responses are returned as `ApiResponse(..., parsed=None)` instead of raising `UnexpectedStatus`. |
| `transport` | `Any \| None` | `None` | Custom httpx transport (e.g. `httpx.MockTransport` in tests). Wrapped by `RetryTransport` when `retries` is enabled. |
| `event_hooks` | `dict[str, list[Callable]] \| None` | `None` | httpx event_hooks. Sync hooks are auto-wrapped to coroutines for the async client. |

### Common patterns

A few configurations that come up often enough to copy:

```python
# Tight timeout for an internal service
ApiClientConfig(timeout=5.0, retries=2)

# Retry aggressively on rate-limit and transient server errors
ApiClientConfig(retries=5, retry_status_list=(429, 502, 503, 504))

# Opt in to "return the response, don't raise" for new or unknown APIs
ApiClientConfig(suppress_unexpected_status=True)
```

For tests, swap in a mock transport so the example never opens a socket:

```python
import httpx
from apyro import ApiClient, ApiClientConfig


def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "ts": "2026-01-01T00:00:00Z"})


cfg = ApiClientConfig(transport=httpx.MockTransport(handler))
client = ApiClient("https://api.example.com", configuration=cfg)
```

## Error handling

`apyro` distinguishes documented errors (the server returned a status declared in `Endpoint.errors`) from undocumented ones (anything else in the 4xx/5xx range). Documented errors always raise `ApiResponseError` carrying the parsed error model; undocumented ones raise `UnexpectedStatus` by default, or fold into the response if you opt in via `suppress_unexpected_status`. A success response can also fail to parse if the server returns a body that doesn't match `Endpoint.response_model`: apyro raises `ApiResponseErrorParse` in that case, on both the success and error paths. Network-level failures are wrapped in `ApiTransportError`.

```text
ApiError
├── ApiTransportError          # network failure (timeout, connect, etc.)
├── ApiResponseError           # documented error, body parsed successfully
├── ApiResponseErrorParse      # body did not match the declared model (success or error path)
└── UnexpectedStatus           # undocumented 4xx/5xx (opt-in suppressable)
```

| Exception | Raised when |
|---|---|
| `ApiTransportError` | An httpx transport failure occurs (timeout, connection error, etc.). |
| `ApiResponseError` | The response status is in `Endpoint.errors` and the body parses against the registered model. |
| `ApiResponseErrorParse` (error path) | The response status is in `Endpoint.errors` but the body didn't match the registered model. |
| `ApiResponseErrorParse` (success path) | The response status is 2xx but the body didn't match `Endpoint.response_model`. |
| `UnexpectedStatus` | The response status is a 4xx/5xx not declared in `Endpoint.errors` and `suppress_unexpected_status` is `False`. |

Catching the hierarchy:

```python
from apyro import (
    ApiError,                # catch-all for anything apyro raised
    ApiTransportError,       # network failure, usually retry / reconnect / fail
    ApiResponseError,        # documented error, branch on exc.status_code
    ApiResponseErrorParse,   # body didn't match the declared model, log + diagnose
    UnexpectedStatus,        # undocumented, log + maybe report a bug
)

try:
    resp = client.request(GET_USER, path_params={"user_id": 42})
except ApiResponseError as exc:
    match exc.status_code:
        case 404: ...
        case 429: ...
except ApiResponseErrorParse as exc:
    ...   # server returned a status the endpoint declared, but the body didn't match
except ApiTransportError:
    ...   # connection / timeout handling
except UnexpectedStatus as exc:
    ...   # server returned a status the endpoint didn't declare
except ApiError:
    ...   # anything else apyro surfaced
```

## Recipes

Patterns for common tasks.

### Reuse one endpoint across two clients

```python
cfg = ApiClientConfig(timeout=10.0)

prod = ApiClient("https://api.example.com", configuration=cfg)
staging = ApiClient("https://staging.example.com", configuration=cfg)

prod_resp = prod.request(GET_USER, path_params={"user_id": 42})
staging_resp = staging.request(GET_USER, path_params={"user_id": 42})
```

Same `Endpoint`, same `ApiClientConfig`, different `base_url`. The error map and response model are defined on the endpoint.

### Share a custom auth flow

```python
import httpx


def bearer_auth(request: httpx.Request) -> httpx.Request:
    request.headers["Authorization"] = f"Bearer {token_for(request.url)}"
    return request


cfg = ApiClientConfig(auth_flow=bearer_auth)
```

`auth_flow` is called once per request, on the way out, by both the sync and async client. `token_for` is your own function that returns a bearer token for the request.

### Disable retries for an idempotency-sensitive endpoint

`retries=0` removes the `RetryTransport` wrapper entirely:

```python
no_retry = ApiClientConfig(retries=0)
```

Useful for non-idempotent operations where a retry could double-charge a user.

## Full example

See [`examples/frankfurter/`](examples/frankfurter/) for a working, runnable example that uses `httpx.MockTransport` (no network required). It defines pydantic models for the free [Frankfurter](https://www.frankfurter.app) currency-rates API, registers typed error models, and exercises both sync and async paths against a mock transport. Run it with `uv run python -m examples.frankfurter.main`. It prints `All demos passed.` when done.

## Development

The project uses [`just`](https://github.com/casey/just) as a task runner and [`uv`](https://docs.astral.sh/uv/) for environment management.

| Recipe | What it does |
|---|---|
| `just sync` | Install deps into `.venv` |
| `just test` | Run the pytest suite |
| `just lint` | `ruff check` + format |
| `just typing` | `ty` type check |
| `just cov` | Tests with coverage report + html |
| `just check-all` | lint + cov + typing |
| `just fresh` | Wipe `.venv` and caches, recreate from scratch |

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Javier Peces.
