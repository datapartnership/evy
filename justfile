# List the available development commands.
default:
    @just --list

# Install the locked development and documentation environment.
setup:
    uv sync --locked --extra docs
    uv run --locked pre-commit install

# Run offline tests; live service tests are always excluded.
test:
    uv run --locked pytest -m "not live" tests/

# Check Python source, tests, and scripts, including formatting.
lint:
    uv run --locked ruff check src tests scripts
    uv run --locked ruff format --check src tests scripts

# Apply safe lint fixes and formatting.
format:
    uv run --locked ruff check --fix src tests scripts
    uv run --locked ruff format src tests scripts

# Build the source archive, then the wheel from that archive.
build:
    uv run --locked --group release python -m build --installer uv

# Check metadata and run offline tests against clean installs of both artifacts.
package-check: build
    uv run --locked --group release python -m twine check --strict dist/*
    uv run --locked --group release python scripts/check_distribution.py dist

# Run the local checks required before a release.
check: lint test package-check

# Build the documentation without starting a server.
docs-build:
    uv run --locked --extra docs jupyter-book build . --config docs/_config.yml --toc docs/_toc.yml

# Build and serve docs. Stop with Ctrl+C; rerun after edits.
docs port="8000": docs-build
    uv run --locked python -m http.server {{port}} --bind 0.0.0.0 --directory _build/html
