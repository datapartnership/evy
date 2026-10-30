.PHONY: help install install-dev test lint format build docs-build package-check check clean

# Compatibility aliases; development commands are defined in justfile.
help:
	@just --list

install:
	uv pip install .

install-dev:
	just setup

test lint format package-check check docs-build:
	just $@

# Preserve the historical documentation-build command.
build:
	just docs-build

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
