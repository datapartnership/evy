# Changelog

## Unreleased

### Added

- NASA LAADS OPeNDAP access for Terra and Aqua MODIS, with lazy spatial subsets
  and a validated disk cache.
- Local distribution checks that install the wheel and source archive into
  separate temporary environments and run the offline test suite.
- `just` commands for setup, linting, formatting, testing, package validation,
  and documentation development.
- Release validation of artifacts, clean installations, and Git tag/version
  agreement before PyPI publication.

### Changed

- MODIS defaults to local LAADS processing and requires Earthdata Login.
  Pass `backend="gee"` for the previous GEE workflow or
  `provider="planetary_computer"` for public STAC access. Sentinel-2 still uses GEE.
- Contributor dependencies now use dependency groups. Replace `evy[test]` in a
  checkout with `uv sync --group test`. Notebook tools are in `--group notebooks`;
  the `docs` and `earthdata` installation extras remain available.
- Releases require version tags such as `v1.2.3` or `v1.2.3rc1`.

### Fixed

- GEE date batches use the next calendar period boundary directly, preventing
  a day from being dropped with newer pandas timestamp precision behavior.

Historical changes remain available in Git history and GitHub releases.
