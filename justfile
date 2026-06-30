set dotenv-load

ARGS_TEST := env("_UV_RUN_ARGS_TEST", "")
# ARGS_SERVE := env("_UV_RUN_ARGS_SERVE", "")
# PORT := env("PORT", "8000")


[default]
@_help:
    just --list

# Run tests
[group('qa')]
test *args:
    uv run {{ ARGS_TEST }} -m pytest {{ args }}

_cov *args:
    uv run -m coverage {{ args }}

# Run tests and measure coverage
[group('qa')]
@cov:
    just _cov erase
    just _cov run -m pytest
    just _cov report
    just _cov html

# Run linters
[group('qa')]
format:
    uvx ruff format

[group('qa')]
lint:
    uvx ruff check --fix
    just format

# Check types
[group('qa')]
typing:
    uvx ty check --python .venv

# Perform all checks
[group('qa')]
check-all: lint cov typing


[group('profiling')]
profile module:
    mkdir -p .profiling
    uv run python -X importtime -c "import {{module}}" 2> .profiling/{{module}}_import_time.log

[group('profiling')]
profile-view module:
    uvx tuna .profiling/{{module}}_import_time.log

# Update dependencies
[group('lifecycle')]
update:
    uv sync --upgrade

# Ensure project virtualenv is up to date
[group('lifecycle')]
sync:
    uv sync

# Remove temporary files
[group('lifecycle')]
clean:
    rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
    find . -type d -name "__pycache__" -exec rm -r {} +

# Recreate project virtualenv from nothing
[group('lifecycle')]
fresh: clean sync