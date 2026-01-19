.PHONY: install install-dev clean test lint format help

# Default target
help:
	@echo "evy - GEE-first zonal statistics library"
	@echo ""
	@echo "Usage:"
	@echo "  make install      Install package"
	@echo "  make install-dev  Install package in development mode"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linter (ruff)"
	@echo "  make format       Format code (ruff)"
	@echo "  make clean        Remove build artifacts"
	@echo ""

# Install package
install:
	uv pip install .

# Install in development mode with dev dependencies
install-dev:
	uv pip install -e ".[docs]"

# Run tests
test:
	uv run pytest tests/ -v

# Run linter
lint:
	uv run ruff check src/

# Format code
format:
	uv run ruff format src/
	uv run ruff check --fix src/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Build documentation
build:
	uvx --from "jupyter-book>1,<2" jupyter-book build . --config docs/_config.yml --toc docs/_toc.yml
