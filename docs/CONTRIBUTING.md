# Contributing

Thank you for contributing to evy. All contributors must follow the [Code of Conduct](code-of-conduct.md).

## Ways to contribute

- Report bugs or request features in the [issue tracker](https://github.com/datapartnership/evy/issues).
- Correct or clarify documentation.
- Open a pull request with a focused code or documentation change.

## Development workflow

1. Fork and clone `https://github.com/datapartnership/evy`.
2. Create a focused branch.
3. Install the development environment with `uv sync --all-extras --dev`.
4. Make the change and add or update tests when behavior changes.
5. Run `uv run ruff check .` and `uv run pytest`.
6. Open a pull request against `main` describing the change and verification.

## Running notebooks locally

Run `uv run jupyter lab`, then open a notebook under `notebooks/`.

## Building documentation locally

```shell
uv run --extra docs jupyter-book build . --config docs/_config.yml --toc docs/_toc.yml
```

The generated site is written to `_build/html`.

## Licensing

Contributions are licensed under the project's [Mozilla Public License 2.0](../LICENSE).
