"""Core zonal statistics functionality."""

from datetime import datetime, timedelta
from functools import reduce
import logging
from pathlib import Path
from typing import Literal

import ee
import geopandas as gpd
import pandas as pd

from evy._auth import _ensure_initialized
from evy._convert import fc_to_dataframe
from evy.boundaries import (
    _gdf_to_ee_feature_collection,
    get_boundaries,
    load_boundaries,
)
from evy.collections import (
    _load_modis_collection,
    _load_sentinel2_collection,
    apply_cropland_mask,
)

logger = logging.getLogger(__name__)


def zonal_stats(
    boundaries: str | gpd.GeoDataFrame | Path,
    *,
    source: Literal["modis", "sentinel2"] = "modis",
    start_date: str | None = None,
    end_date: str | None = None,
    freq: str = "ME",
    stats: str | list[str] = "mean",
    admin_level: int = 1,
    include_geometry: bool = False,
    mask_cropland: bool = True,
    scale: int | None = None,
    export_to_drive: bool = False,
    drive_folder: str = "evy_exports",
    project: str | None = None,
) -> pd.DataFrame | gpd.GeoDataFrame | str:
    """
    Compute zonal statistics for EVI using Google Earth Engine.

    Parameters
    ----------
    boundaries:
        Zone boundaries for aggregation. Can be:
        - ISO3 country code (e.g., 'SYR', 'KEN') - fetches from GeoBoundaries
        - GeoDataFrame with polygon geometries
        - Path to shapefile or GeoJSON file
    source:
        Satellite data source:
        - 'modis': MODIS Terra + Aqua (250m, 16-day, from 2000)
        - 'sentinel2': Sentinel-2 MSI (10m, 5-day, from 2017)
    start_date:
        Start date as ISO string (e.g., '2020-01-01').
        Default: 1 year before today
    end_date:
        End date as ISO string (e.g., '2024-12-31').
        Default: today
    freq:
        Temporal aggregation frequency (pandas-style):
        - 'Original': Original data (composites from source satellites)
        - 'ME': Monthly (end of month)
        - 'QE': Quarterly
        - 'YE': Yearly
    stats:
        Statistics to compute. Options:
        - 'mean': Mean value (default)
        - 'median': Median value
        - 'min': Minimum value
        - 'max': Maximum value
        - 'std': Standard deviation
        - 'sum': Sum of values
        - 'count': Pixel count
    admin_level:
        Administrative level when boundaries is ISO3 code:
        - 0: Country
        - 1: Province/State (default)
        - 2: District/County
        - 3-5: Lower levels (availability varies)
    include_geometry:
        If True, return GeoDataFrame with geometry column.
        If False, return pandas DataFrame (smaller, faster).
    mask_cropland:
        If False, do not mask non-cropland areas using Dynamic World
        land cover classification.
    scale:
        Resolution in meters. Default depends on source:
        - MODIS: 250m (native resolution)
        - Sentinel-2: 10m (native resolution)
    export_to_drive:
        If True, export results to Google Drive instead of returning directly.
        Useful for large queries that might timeout.
    drive_folder:
        Google Drive folder name for exports.
    project:
        Google Earth Engine project ID.
        If None, uses default or environment variable GEE_PROJECT.

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame or str
        If export_to_drive=False: Zonal statistics with columns:
        - 'date': Date of observation
        - 'zone_name': Zone name (if available)
        - 'evi_mean', 'evi_std', etc.: Computed statistics
        - 'geometry': (only if include_geometry=True)

        If export_to_drive=True: Task ID string for the export task
    """
    _ensure_initialized(project)

    if source not in ("modis", "sentinel2"):
        raise ValueError(f"Unknown source: {source}. Available: 'modis', 'sentinel2'")

    if scale is None:
        scale = 250 if source == "modis" else 10

    end_date = datetime.now().strftime("%Y-%m-%d") if end_date is None else end_date
    start_date = (
        (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if start_date is None
        else start_date
    )

    logger.info(
        f"Computing zonal stats for EVI from {source.upper()} "
        f"({start_date} to {end_date})"
    )

    gdf = _resolve_boundaries(boundaries, admin_level)
    features = _gdf_to_ee_feature_collection(gdf)
    region = features.geometry()

    ic = (
        _load_modis_collection(start_date, end_date, region)
        if source == "modis"
        else _load_sentinel2_collection(start_date, end_date, region)
    )

    if mask_cropland:
        logger.info("Applying cropland mask (Dynamic World)")
        ic = apply_cropland_mask(ic, region)

    if freq != "Original":
        ic = _aggregate_temporal(ic, start_date, end_date, freq)

    reducer = _build_reducer(stats)
    fc = _compute_zonal_stats(ic, features, reducer, scale)

    if export_to_drive:
        filename = _generate_export_filename(boundaries, source, start_date, end_date)
        from evy._convert import export_to_drive as _export

        return _export(fc, filename, drive_folder)
    else:
        # Fetch without geometry and join in client-side if needed
        df = fc_to_dataframe(fc, include_geometry=False)
        if include_geometry:
            return _join_geometries(df, gdf)
        return df


def _resolve_boundaries(
    boundaries: str | gpd.GeoDataFrame | Path,
    admin_level: int,
) -> gpd.GeoDataFrame:
    """Resolve boundaries parameter to GeoDataFrame."""
    if isinstance(boundaries, gpd.GeoDataFrame):
        return boundaries
    elif isinstance(boundaries, Path) or (
        isinstance(boundaries, str)
        and ("/" in boundaries or "\\" in boundaries or "." in boundaries)
    ):
        # File path
        return load_boundaries(boundaries)
    elif isinstance(boundaries, str) and len(boundaries) == 3:
        # ISO3 code
        return get_boundaries(boundaries, admin_level)
    else:
        raise ValueError(
            f"Invalid boundaries: {boundaries}. "
            "Expected ISO3 code (e.g., 'SYR'), GeoDataFrame, or file path."
        )


def _join_geometries(df: pd.DataFrame, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Join geometries back from original boundaries after server-side computation.

    Since geometries are stripped server-side to avoid payload limits,
    we use the _evy_boundary_id to join them back client-side when needed.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with zonal statistics (no geometry)
    gdf : gpd.GeoDataFrame
        Original boundaries with geometry

    Returns
    -------
    gpd.GeoDataFrame
        DataFrame with geometry column joined from original boundaries
    """
    join_key = "_evy_boundary_id"

    # Ensure the join key exists in both dataframes
    if join_key not in df.columns:
        logger.warning(
            f"Join key '{join_key}' not found in results. "
            "Cannot join geometries. Returning DataFrame without geometry."
        )
        return gpd.GeoDataFrame(df, geometry=None, crs=gdf.crs)

    if join_key not in gdf.columns:
        # Add boundary ID to the original GeoDataFrame
        gdf = gdf.copy()
        gdf[join_key] = range(len(gdf))

    # Create geometry lookup from original boundaries
    geom_lookup = gdf.set_index(join_key)["geometry"]

    # Join geometries using the boundary ID
    return gpd.GeoDataFrame(
        df,
        geometry=df[join_key].map(geom_lookup),
        crs=gdf.crs,
    )


def _build_reducer(stats: str | list[str]):
    """Build combined reducer for multiple statistics."""

    if isinstance(stats, str):
        stats = [stats]

    reducer_map = {
        "mean": ee.Reducer.mean(),
        "median": ee.Reducer.median(),
        "min": ee.Reducer.min(),
        "max": ee.Reducer.max(),
        "std": ee.Reducer.stdDev(),
        "sum": ee.Reducer.sum(),
        "count": ee.Reducer.count(),
    }

    try:
        selected_reducers = [reducer_map[s] for s in stats]
    except KeyError as e:
        raise ValueError(
            f"Unknown statistic: {e.args[0]}. Available: {list(reducer_map.keys())}"
        )

    return reduce(lambda a, b: a.combine(b, sharedInputs=True), selected_reducers)


def _compute_zonal_stats(ic, features, reducer, scale: int):
    """
    Compute zonal statistics for each image in the collection.

    Maps over images, reduces per zone, flattens results.
    Geometries are stripped server-side to avoid exceeding GEE's 10MB payload limit.
    """

    def reduce_image(image):
        date = image.date().format("YYYY-MM-dd")

        stats = image.reduceRegions(
            collection=features,
            reducer=reducer,
            scale=scale,
        )

        # Strip geometries server-side to reduce payload size
        # Geometries are only needed for reduction, not in the output
        # They can be joined back client-side using _evy_boundary_id
        def strip_geometry(feature):
            return ee.Feature(None, feature.toDictionary()).set("date", date)

        return stats.map(strip_geometry)

    all_stats = ic.map(reduce_image)
    return all_stats.flatten()


def _aggregate_temporal(ic, start_date: str, end_date: str, freq: str):
    """
    Aggregate ImageCollection temporally.

    Groups images by time period and computes median.
    """
    import ee

    start = ee.Date(start_date)
    end = ee.Date(end_date)

    if freq == "ME":
        return _aggregate_monthly(ic, start, end)
    elif freq == "QE":
        return _aggregate_quarterly(ic, start, end)
    elif freq == "YE":
        return _aggregate_yearly(ic, start, end)
    else:
        logger.warning(f"Unknown frequency {freq}, returning original collection")
        return ic


def _aggregate_monthly(ic, start, end):
    """Aggregate to monthly composites."""
    import ee

    # Generate list of months
    n_months = end.difference(start, "month").round()
    months = ee.List.sequence(0, n_months.subtract(1))

    def monthly_composite(month_offset):
        month_start = start.advance(month_offset, "month")
        month_end = month_start.advance(1, "month")

        filtered = ic.filterDate(month_start, month_end)
        composite = filtered.median().set("system:time_start", month_start.millis())
        return composite

    return ee.ImageCollection.fromImages(months.map(monthly_composite))


def _aggregate_quarterly(ic, start, end):
    """Aggregate to quarterly composites."""
    import ee

    # Generate list of quarters
    n_quarters = end.difference(start, "month").divide(3).round()
    quarters = ee.List.sequence(0, n_quarters.subtract(1))

    def quarterly_composite(quarter_offset):
        quarter_start = start.advance(ee.Number(quarter_offset).multiply(3), "month")
        quarter_end = quarter_start.advance(3, "month")

        filtered = ic.filterDate(quarter_start, quarter_end)
        composite = filtered.median().set("system:time_start", quarter_start.millis())
        return composite

    return ee.ImageCollection.fromImages(quarters.map(quarterly_composite))


def _aggregate_yearly(ic, start, end):
    """Aggregate to yearly composites."""
    import ee

    start_year = start.get("year")
    end_year = end.get("year")
    years = ee.List.sequence(start_year, end_year)

    def yearly_composite(year):
        year_start = ee.Date.fromYMD(year, 1, 1)
        year_end = ee.Date.fromYMD(year, 12, 31)

        filtered = ic.filterDate(year_start, year_end)
        composite = filtered.median().set("system:time_start", year_start.millis())
        return composite

    return ee.ImageCollection.fromImages(years.map(yearly_composite))


def _generate_export_filename(
    boundaries, source: str, start_date: str, end_date: str
) -> str:
    """Generate a descriptive filename for exports."""
    if isinstance(boundaries, str) and len(boundaries) == 3:
        region = boundaries.lower()
    else:
        region = "custom"

    start_short = start_date.replace("-", "")[:6]
    end_short = end_date.replace("-", "")[:6]

    return f"{region}_evi_{source}_zonal_stats_{start_short}_{end_short}"
