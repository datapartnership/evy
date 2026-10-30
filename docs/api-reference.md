# API Reference

This page documents evy's public API — the functions and constants exported from the top-level `evy` module. Everything below is reachable as `evy.<name>` without importing submodules.

Symbols beginning with `_` are internal and not part of the public contract. They are intentionally excluded from this reference.

**Default change:** MODIS now uses `backend="local", provider="laads"` when
omitted. Sentinel-2 continues to use GEE. To preserve a previous GEE workflow,
pass `backend="gee"`; to preserve local PC access, pass
`provider="planetary_computer"`. Backend choices use different crop masks as
described below, so changing backends can change masked statistics.

## Backend support

| Backend | Sources | Authentication | Large jobs |
|---|---|---|---|
| `"gee"` | MODIS, Sentinel-2 | Google Earth Engine | `export_to_drive=True` |
| `"local"` | MODIS | None with Planetary Computer; Earthdata Login with `provider="laads"` or `"earthdata"` | Split large regions or date ranges |

The GEE backend uses Dynamic World for cropland masking. The local backend defaults to ESA WorldCover and also supports annual Esri/Impact Observatory maps with `landcover_source="esri"`, so masked results are not expected to match pixel-for-pixel.

For direct NASA MODIS access, configure Earthdata credentials and use the
default LAADS provider on `load_modis`, `load_evi`, `zonal_stats`, or
`cached_zonal_stats`. Install `evy[earthdata]` and select `provider="earthdata"`
for full-HDF downloads instead. Provider selection and resolved backend choices
are included in statistics cache keys. See the [NASA access example](../README.md#default-modis-access-nasa-laads)
for authentication, disk cache behavior, and download size considerations.

Use `provider="laads"` for lazy NASA LAADS OPeNDAP subsets of EVI and pixel
reliability on the native MODIS grid. It supports Terra and Aqua, uses at most
four concurrent transfers, and caches validated subsets under
`EVY_CACHE_DIR/laads`. A rasterio/GDAL build with the NetCDF driver is required.
`provider="earthdata"` remains the full-HDF alternative. No provider is silently
substituted if a request fails. Source-subset caches are separate from the
statistics cache and are not removed by `clear_zonal_cache`.

## Output contract

`zonal_stats` and `cached_zonal_stats` return `date`, the requested `zone_col`, and one column per requested statistic. `date` is the observation date for `"Original"` or the first day of an aggregated calendar period. When `include_geometry=True`, the result is a GeoDataFrame with geometry in the input boundaries' CRS.

## Boundaries

```{autodoc2-object} evy.boundaries.get_boundaries
```

```{autodoc2-object} evy.boundaries.load_boundaries
```

```{autodoc2-object} evy.boundaries.clear_cache
```

## Collections & Authentication

```{autodoc2-object} evy.collections.list_collections
```

```{autodoc2-object} evy._auth.authenticate
```

```{autodoc2-object} evy._auth.is_authenticated
```

```{autodoc2-object} evy._convert.check_task_status
```

## Zonal Statistics

```{autodoc2-object} evy.zonal.zonal_stats
```

```{autodoc2-object} evy.cache.cached_zonal_stats
```

```{autodoc2-object} evy.cache.clear_zonal_cache
```

```{autodoc2-object} evy.load.load_modis
```

```{autodoc2-object} evy.load.load_landcover
```

```{autodoc2-object} evy.load.EmptyStacResultError
```

```{autodoc2-object} evy._zonal_local.compute_zonal_stats
```

(raster-loading-and-geotiff-export)=
## Raster loading and GeoTIFF export

See the [runnable GeoTIFF export recipe](../notebooks/recipes/geotiff-export.ipynb) for EVI, land-cover, and binary crop-mask examples.

Raster output uses the local backend without GEE authentication. The default
LAADS provider requires NASA credentials; PC remains an explicit option. No zonal
aggregation is performed by `load_evi` or `export_geotiff`.

```python
import evy

boundaries = evy.get_boundaries("RWA", admin_level=1)
evi = evy.load_evi(
    boundaries, "2023-01-01", "2023-01-31",
    landcover_source="esri",  # mask_cropland=True by default
)
paths = evy.export_geotiff(evi, "output/evi")
# One quality-filtered, scaled, crop-masked TIFF per MODIS observation.
# Set mask_cropland=False for EVI over all land-cover classes.

# Native 10 m land cover, without resampling it to MODIS resolution:
lc = evy.load_landcover(boundaries, source="esri", year=2025)
evy.export_geotiff(lc.rename("landcover_2025"), "output/landcover")

# Binary cropland: 1=crop, 0=other, 255=nodata.
crops = (lc == 5).where(lc != 0, 255).astype("uint8")
crops = crops.rename("cropland_2025").rio.write_nodata(255)
evy.export_geotiff(crops, "output/cropland")
```

Esri/Impact Observatory v003 maps cover 2017–2025 and use class 5 for crops.
They are read from the public assets linked by the
[Esri Land Cover Explorer](https://livingatlas.arcgis.com/landcoverexplorer/).
Planetary Computer's `io-lulc-annual-v02` collection currently stops at 2023,
so evy uses Esri's tile index and downloads for this source. Unavailable years
raise an error; evy does not substitute a different year's map.

For zonal statistics, use `landcover_source="esri"` with `backend="local"`
in `zonal_stats` or `cached_zonal_stats`. Annual crop masks are matched to
each observation **before** temporal aggregation. WorldCover remains the
default; GEE continues to use Dynamic World. Cache entries distinguish sources.

Exports preserve CRS, grid, and nodata and never overwrite existing files.
Native Esri rasters use 10 m pixels in the first intersecting tile's UTM CRS;
EVI exports retain the MODIS grid. Rasters cover the boundary **bounding box**,
not a polygon-clipped area. Loading is lazy, but exporting reads pixels;
split large regions and date ranges to keep memory and downloads manageable.

```{autodoc2-object} evy.load.load_evi
```

```{autodoc2-object} evy.export.export_geotiff
```

## Phenology

```{autodoc2-object} evy.phenology.calculate_phenology
```

```{autodoc2-object} evy.phenology.extract_phenology
```

```{autodoc2-object} evy.phenology.preprocess_series
```

```{autodoc2-object} evy.phenology.get_growing_season
```

```{autodoc2-object} evy.phenology.filter_growing_season
```

## Visualization

```{autodoc2-object} evy.viz.plot_seasonality
```

```{autodoc2-object} evy.viz.plot_seasonality_by_region
```

```{autodoc2-object} evy.viz.plot_time_series
```

```{autodoc2-object} evy.viz.plot_time_series_by_region
```

```{autodoc2-object} evy.viz.plot_choropleth
```

## Constants

These module-level constants are convenience aliases for common values. They are documented inline here rather than via autodoc2, which does not render string constants cleanly.

| Name | Value | Meaning |
|---|---|---|
| `evy.ORIGINAL` | `"Original"` | No aggregation; one row per source composite |
| `evy.MONTHLY` | `"ME"` | Calendar months (default for `zonal_stats`); `date` is the first day of the month |
| `evy.QUARTERLY` | `"QE"` | Calendar quarters; `date` is the first day of the quarter |
| `evy.YEARLY` | `"YE"` | Calendar years; `date` is 1 January |
| `evy.ANNUAL` | `"YE"` | Alias for `evy.YEARLY` |
| `evy.CRS` | `"EPSG:4326"` | Default coordinate reference system for inputs and outputs |
