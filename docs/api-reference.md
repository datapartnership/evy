# API Reference

This page documents evy's public API — the functions and constants exported from the top-level `evy` module. Everything below is reachable as `evy.<name>` without importing submodules.

Symbols beginning with `_` are internal and not part of the public contract. They are intentionally excluded from this reference.

## Boundaries

```{autodoc2-object} evy.get_boundaries
```

```{autodoc2-object} evy.load_boundaries
```

```{autodoc2-object} evy.clear_cache
```

## Collections & Authentication

```{autodoc2-object} evy.list_collections
```

```{autodoc2-object} evy.authenticate
```

```{autodoc2-object} evy.is_authenticated
```

```{autodoc2-object} evy.check_task_status
```

## Zonal Statistics

```{autodoc2-object} evy.zonal_stats
```

```{autodoc2-object} evy.load_modis
```

```{autodoc2-object} evy.load_landcover
```

```{autodoc2-object} evy.compute_zonal_stats
```

## Phenology

```{autodoc2-object} evy.calculate_phenology
```

```{autodoc2-object} evy.extract_phenology
```

```{autodoc2-object} evy.preprocess_series
```

```{autodoc2-object} evy.get_growing_season
```

```{autodoc2-object} evy.filter_growing_season
```

## Visualization

```{autodoc2-object} evy.plot_seasonality
```

```{autodoc2-object} evy.plot_seasonality_by_region
```

```{autodoc2-object} evy.plot_time_series
```

```{autodoc2-object} evy.plot_time_series_by_region
```

```{autodoc2-object} evy.plot_choropleth
```

## Constants

These module-level constants are convenience aliases for common values. They are documented inline here rather than via autodoc2, which does not render string constants cleanly.

| Name | Value | Meaning |
|---|---|---|
| `evy.DAILY` | `"D"` | Daily frequency (pandas offset alias) |
| `evy.WEEKLY` | `"W"` | Weekly frequency |
| `evy.MONTHLY` | `"ME"` | Month-end frequency (default for `zonal_stats`) |
| `evy.QUARTERLY` | `"QE"` | Quarter-end frequency |
| `evy.YEARLY` | `"YE"` | Year-end frequency |
| `evy.CRS` | `"EPSG:4326"` | Default coordinate reference system for inputs and outputs |
