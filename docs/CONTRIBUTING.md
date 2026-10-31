# Contributing

Contributions follow the [Code of Conduct](code-of-conduct.md) and are licensed
under the [Mozilla Public License 2.0](../LICENSE).

## Development environment

Install [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/), clone
`https://github.com/datapartnership/evy`, and create a focused branch. Then run:

```shell
just setup
```

This installs the locked development environment and documentation tools, then
installs the pre-commit hooks. `.python-version` selects Python 3.11 for local
development; the package requires Python 3.11 or newer. Other Python versions
are not covered by an automated compatibility matrix yet.

Runtime requirements and user-installable extras live in `project` metadata.
Contributor tools live in dependency groups: `test`, `lint`, `release`, and
`notebooks`. The default `dev` group includes tests, linting, release tools, and
pre-commit. The `docs` extra is retained for existing documentation installations;
`earthdata` adds the optional HDF reader. The former `test` extra has been replaced
by the `test` dependency group. Unused pytest-mock and papermill dependencies have
been removed.

Use `uv add --group <group> <tool>` for development tools and commit both
`pyproject.toml` and `uv.lock` when dependencies change. `--locked` checks that
the committed lockfile is current. Runtime dependency ranges remain in package
metadata so downstream users can resolve compatible environments.

## Everyday commands

| Command | Purpose |
|---|---|
| `just test` | Offline unit and contract tests |
| `just lint` | Ruff checks and formatting checks for source, tests, and scripts |
| `just format` | Apply safe Ruff fixes and formatting |
| `just build` | Build source archive, then wheel from that archive |
| `just package-check` | Check distribution metadata and test clean installs |
| `just check` | Lint, offline tests, and package checks |
| `just docs` | Build and serve documentation on port 8000 |
| `just docs 8080` | Use a different documentation port |
| `just docs-build` | Build documentation without starting a server |

Stop the documentation server with Ctrl+C; rerun to rebuild after edits. Existing
`make` commands delegate to `just`. `make build` retains its historical meaning
of building documentation; `just build` builds Python distributions.

To run notebooks, install the optional contributor tools:

```shell
uv sync --locked --group notebooks --extra docs
uv run --locked jupyter lab
```

## Testing changes

Add tests for behavior changes, especially CRS and grid alignment, quality masks,
scale factors, date boundaries, cache invalidation, and output schemas. Use small
synthetic rasters or the documented fixtures under `tests/fixtures`. Mock service
boundaries for offline tests. Avoid requiring real credentials in routine tests.

`just test` excludes the `live` marker even if live-test environment variables
are set. Live provider parity tests are a separate, explicit check:

```shell
EVY_TEST_LAADS=1 uv run --locked pytest -m live tests/test_laads_live.py
uv sync --locked --extra earthdata
EVY_TEST_EARTHDATA=1 uv run --locked pytest -m live tests/test_earthdata_live.py
```

These require configured Earthdata credentials and network access; never commit
credentials or attach unredacted authentication tracebacks. Live comparisons
must use identical observations, grids, QA, and masks. Different providers can
have different coverage, and different backends use different crop masks.

Before opening a PR, run `just check` and `just docs-build` if documentation
changed. Package checks need network access to install dependencies. They create
temporary environments, install each distribution without editable mode, and
run the offline tests outside the checkout, then install the `earthdata` extra
and run the HDF fixture tests. This verifies the actual artifacts
and resolves runtime dependencies afresh rather than relying on `uv.lock`.
If `dist/` contains artifacts from multiple versions, remove those generated
artifacts before rebuilding; the checker deliberately rejects ambiguous inputs.

## Public API and compatibility

The supported surface is the names exported in `evy.__all__`, documented in the
[API reference](api-reference.md). Underscore-prefixed modules and helpers are
internal even when tests import them.

Preserve documented keyword arguments, defaults, result columns, CRS, date
semantics, and exception behavior. Document behavioral changes in
[the changelog](../CHANGELOG.md). For a rename, keep an alias and issue a
`DeprecationWarning` with migration instructions before removal in a later
release. Provider changes must remain explicit; do not silently fall back to a
different provider or observation year.

Add annotations and NumPy-style docstrings when changing public functions.
Do not publish a `py.typed` marker until the declared typing surface is checked.

## Releases

1. Run `just check` and review the generated wheel and source archive.
2. Move the relevant changelog entries into a dated version section and commit.
3. Tag the intended commit `vX.Y.Z` (or `vX.Y.ZrcN`, `vX.Y.ZaN`, `vX.Y.ZbN` for
   prereleases). Version metadata is derived from Git tags; do not edit a second
   version constant. Use a minor version for new behavior and a patch version
   for compatible fixes; announce breaking changes and migration steps explicitly.
4. Push the release tag when ready to publish. The tag workflow checks formatting,
   offline tests, metadata, tag/version agreement, and clean installs of both
   artifacts before uploading them to the publishing job.
5. Publish GitHub release notes from the changelog after the workflow succeeds.

Publishing uses the `pypi` GitHub environment and PyPI Trusted Publishing for
`evy`. Repository/PyPI owners must configure that trusted publisher and any
required environment reviewers in those services; configuration is not created
by the workflow. No release tag should be pushed just to test this setup.

Pull-request CI is intentionally deferred. These local checks and the tag-only
release checks are the current validation process.
