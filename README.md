# evy

[![GitHub Release](https://img.shields.io/github/v/release/datapartnership/evy)](https://github.com/datapartnership/evy/releases)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**evy** is a Python package for fetching, processing, and analyzing Enhanced Vegetation Index (EVI) data from MODIS satellite imagery. It provides a high-level interface to work with vegetation data, enabling researchers and practitioners to monitor vegetation health, compute phenological metrics, and perform zonal statistics with ease.

> **Note:** This package is a work in progress. Features and APIs may change as development continues.

## Features

- **Easy Data Access**: Fetch MODIS EVI subsets from NASA LAADS, with Planetary Computer and GEE alternatives
- **Zonal Statistics**: Compute statistics (mean, median, max, etc.) for specific geometries
- **Temporal Aggregation**: Aggregate data at various temporal frequencies (monthly, yearly, quarterly)
- **Phenology Analysis**: Extract and visualize vegetation growing seasons and phenological patterns
- **Land Cover Masking**: Filter EVI data by land cover classification (e.g., cropland-only analysis)
- **Visualization**: Built-in plotting functions for time series and phenology

## Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv pip install git+https://github.com/datapartnership/evy.git
```

Or using pip:

```bash
pip install git+https://github.com/datapartnership/evy.git
```

## Documentation

- [Installation](docs/installation.md)
- [Quickstart](notebooks/quickstart.ipynb)
- [How-to recipes](notebooks/recipes/monthly-aggregation.ipynb)
- [Concepts and methodology](docs/design-decisions.md)
- [API reference](docs/api-reference.md)
- [Troubleshooting](docs/troubleshooting.md)

To build and serve the docs locally, run `just docs` (requires `just`, `uv`,
and Python 3). Use `just docs 8080` for another port. Stop with Ctrl+C;
rerun the command after editing the docs to rebuild them. Local development uses
Python 3.11 through `uv`. See the [contributor guide](docs/CONTRIBUTING.md) for
`just setup`, `just check`, and the release process.

## Citation

If you use this package in your research or work, please cite it using the information in [CITATION.cff](CITATION.cff).

## License

This project is licensed under the Mozilla Public License 2.0 - see the [LICENSE](LICENSE) file for details.

### Export rasters instead of zonal statistics

```python
import evy

boundaries = evy.get_boundaries("RWA", admin_level=1)
evi = evy.load_evi(
    boundaries, "2023-01-01", "2023-01-31", landcover_source="esri"
)
evy.export_geotiff(evi, "output/evi")
```

This exports one GeoTIFF per observation, with quality filtering, EVI scaling,
and annual cropland masking. Esri/Impact Observatory land cover supports
2017–2025; WorldCover remains the default. Use `mask_cropland=False` for
unmasked EVI. Exports cover the boundary bounding box and preserve the MODIS
grid. Native 10 m land-cover exports are described in the
[API reference](docs/api-reference.md).

For a complete runnable example, see the [GeoTIFF export recipe](notebooks/recipes/geotiff-export.ipynb).

### Default MODIS access: NASA LAADS

MODIS now uses local computation with NASA LAADS OPeNDAP by default. It reads
only EVI and QA pixel windows from Terra and Aqua v061. Sentinel-2 continues
to use GEE. Existing GEE workflows should specify `backend="gee"`; local
cropland masking uses WorldCover rather than GEE's Dynamic World, so a backend
change can change masked results.

Configure your free [Earthdata Login](https://urs.earthdata.nasa.gov/) once:

```python
import earthaccess
earthaccess.login(persist=True)
```

Then use the default, or select it explicitly with `provider="laads"`:

```python
import evy

boundaries = evy.get_boundaries("RWA", admin_level=1)
df = evy.zonal_stats(
    boundaries, zone_col="shapeName",
    start_date="2023-01-01", end_date="2023-12-31",
)
evi = evy.load_evi(
    boundaries, "2026-10-01", "2026-10-30",
    provider="laads", mask_cropland=False,
)
```

LAADS needs rasterio/GDAL's NetCDF driver and Earthdata Login; it does not need
an HDF4 driver. `earthaccess` is installed with evy. Library calls use configured
credentials without prompting. Environment credentials (`EARTHDATA_TOKEN`, or
`EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`) take precedence over `.netrc`.

Subset reads happen on computation, use up to four concurrent transfers, and
reuse validated windows under `$EVY_CACHE_DIR/laads` (or the platform evy cache).
Failures raise an error; no provider is silently substituted. `clear_zonal_cache`
clears statistics, not pixel subsets. Cropland masking still fetches land cover
from Planetary Computer or the selected Esri source.

### Planetary Computer and GEE alternatives

Use `provider="planetary_computer"` on `load_modis`, `load_evi`, `zonal_stats`, or
`cached_zonal_stats` for local MODIS access without NASA credentials. Recent
observations may not yet be mirrored there. Use `backend="gee"` on zonal-statistics
calls for server-side processing, GEE cropland masking, or Drive exports.

### Full NASA HDF downloads (optional)

Install the HDF4 reader with `pip install 'evy[earthdata]'`, or
`uv sync --extra earthdata` in a checkout. Select `provider="earthdata"` to download
full MOD13Q1/MYD13Q1 v061 HDF files and read cropped pixels with pyhdf. This path
shares the same quality masking and scaling as LAADS, but transfers whole tiles.
Missing tiles download in batches of up to four transfers. Allow several hundred
MB per tile and observation.

Use the same Earthdata Login setup shown above, then select the full-HDF provider:

```python
import evy

boundaries = evy.get_boundaries("RWA", admin_level=1)
df = evy.cached_zonal_stats(
    boundaries,
    zone_col="shapeName",
    backend="local",
    provider="earthdata",
    start_date="2023-01-01",
    end_date="2023-01-01",  # One composite-start date to limit the first download.
    mask_cropland=False,
)
```

The same provider works with `load_modis` for raw EVI/QA pixels and `load_evi`
for scaled, quality-filtered pixels. `mask_cropland=False` avoids land-cover
downloads; omit it to retain the default cropland mask. Repeated identical
`cached_zonal_stats` calls reuse the statistics cache. Changing the study area
can still reuse completed HDF tiles that intersect the new area.

Completed HDFs are reused under `$EVY_CACHE_DIR/earthdata` (or the platform evy
cache). Delete source-cache directories only after finishing lazy computations.
Provider selection is included in statistics cache keys. `clear_zonal_cache`
does not remove the HDF files. Calls that need to compute results still perform
NASA authentication and discovery even when HDFs are cached; this is not a
fully offline provider.
