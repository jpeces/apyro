# AGENTS.md

## Project

`apyro` — a declarative, pydantic-driven HTTP API client library built on httpx.
Endpoints are dataclass values (not methods on a client class), passed to an
`ApiClient` that owns httpx lifecycle, retries, and auth. Sync + async symmetric.

## Stack

- Python >=3.14
- httpx (sync + async), httpx-retries, pydantic v2
- uv for env/lock/install
- just for task runner (QA, lifecycle recipes)

## Commands

```bash
just sync          # install deps into .venv
just test          # run tests
just lint          # ruff check + format
just typing        # ty type check
just cov           # tests with coverage report + html
just check-all     # lint + cov + typing
just fresh         # wipe .venv and caches, recreate from scratch
uv lock            # regenerate lockfile after dependency changes
uv run python -m examples.frankfurter.main   # full example (prints "All demos passed.")
uv run python -c "import apyro; print(apyro.__version__)"
```

## Architecture

```
src/apyro/
  __init__.py       public API surface (__all__)
  client.py         ApiClient — owns httpx sync+async clients, retries, auth, event_hooks
                    delegates request rendering + response parsing to Endpoint
  config.py         ApiClientConfig (frozen dataclass) — timeout, retries, SSL, auth, event_hooks
  endpoint.py       Endpoint[T] (generic dataclass) — method/path/response_model/
                    path/query/body pydantic models, response_handler, errors map
  errors.py         ApiError, ApiResponseError, ApiTransportError, UnexpectedStatus
  response.py       ApiResponse[T] — wraps httpx.Response + parsed model
examples/frankfurter/  working example: models, endpoints, client usage (MockTransport, no network)
tests/              pytest suite — standalone models/endpoints, no dependency on examples/
```

## Key design decisions

- **Endpoint-as-data**: `Endpoint` is a standalone dataclass, decoupled from any
  client. Two consumers can share `Endpoint` definitions without sharing a client class.
- **Typed error map**: `Endpoint.errors: dict[int, type[BaseModel]]` →
  `ApiResponseError(status, parsed_error_model, raw)`. This is the primary
  differentiator vs uplink/pydantic-client — neither has per-status typed errors.
- **httpx-only**: no multi-backend abstraction. Position as httpx-native, not a limitation.
- **event_hooks fan-out**: `ApiClientConfig.event_hooks` accepts sync hooks;
  `_build_event_hooks` wraps them as coroutines for `AsyncClient` so one config
  works on both paths
  
## Conventions

- `ponytail:` comments mark deliberate simplifications and deferrals. Read them
  before "fixing" something — it may be intentionally lazy. Each names the
  ceiling and the upgrade path.
- Shortest working diff wins. No speculative abstractions (no interface with one
  implementation, no factory for one product, no config for a value that never changes).
- Stdlib/native before deps. httpx event_hooks over a custom hook system;
  `TypeAdapter` over a custom parser; `httpx.MockTransport` over a mock library.
- No comments unless they're `ponytail:` markers or genuinely non-obvious.
- Naming: package/distribution = `apyro`, module = `apyro`, classes = descriptive
  (`ApiClient`, `ApiClientConfig`, `Endpoint`, `HttpMethod`, ...).
