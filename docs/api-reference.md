# API Reference

This page documents evy's public API — the functions and constants exported from the top-level `evy` module. Everything below is reachable as `evy.<name>` without importing submodules.

Symbols beginning with `_` are internal and not part of the public contract. They are intentionally excluded from this reference.

## Backend support

| Backend | Sources | Authentication | Large jobs |
|---|---|---|---|
| `"gee"` | MODIS, Sentinel-2 | Google Earth Engine | `export_to_drive=True` |
| `"local"` | MODIS | None with Planetary Computer | Split large regions or date ranges |

The GEE backend uses Dynamic World for cropland masking. The local backend uses ESA WorldCover, so masked results are not expected to match pixel-for-pixel.

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
