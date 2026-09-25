"""Core zonal statistics functionality."""

from datetime import datetime, timedelta
from functools import reduce
import logging
from typing import Literal

import ee
import geopandas as gpd
import pandas as pd

from evy._auth import _ensure_initialized
from evy._convert import fc_to_dataframe
from evy.boundaries import _gdf_to_ee_feature_collection
from evy.collections import (
    _load_modis_collection,
    _load_sentinel2_collection,
    apply_cropland_mask,
)

logger = logging.getLogger(__name__)

# Output contract shared by both backends: ``date`` (period start), the
# ``zone_col`` column, one column per stat below, and optionally ``geometry``.
STATS = ("mean", "median", "min", "max", "std", "sum", "count")
FREQS = ("Original", "ME", "QE", "YE")
_GEE_KWARGS = {"scale", "export_to_drive", "drive_folder", "project"}
# pandas period alias and length in months, for calendar-aligned GEE composites.
_GEE_PERIODS = {"ME": ("M", 1), "QE": ("Q", 3), "YE": ("Y", 12)}


def _default_dates(start_date: str | None, end_date: str | None) -> tuple[str, str]:
    """Fill missing dates: end defaults to today, start to one year earlier."""
    now = datetime.now()
    end_date = now.strftime("%Y-%m-%d") if end_date is None else end_date
    if start_date is None:
        start_date = (now - timedelta(days=365)).strftime("%Y-%m-%d")
    return start_date, end_date


def _validate_args(backend, source, freq, stats, kwargs) -> list[str]:
    """Check arguments before any download. Returns ``stats`` as a list."""
    if backend not in ("gee", "local"):
        raise ValueError(f"Unknown backend: {backend!r}. Available: 'gee', 'local'")
    if source not in ("modis", "sentinel2"):
        raise ValueError(f"Unknown source: {source!r}. Available: 'modis', 'sentinel2'")
    if freq not in FREQS:
        raise ValueError(f"Unknown freq: {freq!r}. Available: {list(FREQS)}")
    stats = [stats] if isinstance(stats, str) else list(stats)
    unknown_stats = [s for s in stats if s not in STATS]
    if unknown_stats:
        raise ValueError(f"Unknown stats: {unknown_stats}. Available: {list(STATS)}")
    unknown_kwargs = set(kwargs) - _GEE_KWARGS
    if unknown_kwargs:
        raise TypeError(f"Unexpected keyword arguments: {sorted(unknown_kwargs)}")
    if backend == "local":
        if kwargs:
            raise ValueError(
                f"Parameters {sorted(kwargs)} are only supported with backend='gee'"
            )
        if source == "sentinel2":
            raise ValueError(
                "Local backend currently only supports MODIS. "
                "Use source='modis' or backend='gee'."
            )
    return stats


def zonal_stats(
    boundaries: gpd.GeoDataFrame,
    *,
    zone_col: str,
    backend: Literal["gee", "local"] = "gee",
    source: Literal["modis", "sentinel2"] = "modis",
    start_date: str | None = None,
    end_date: str | None = None,
    freq: str = "ME",
    stats: str | list[str] = "mean",
    include_geometry: bool = False,
    mask_cropland: bool = True,
    **kwargs,
) -> pd.DataFrame | gpd.GeoDataFrame | str:
    """
    Compute EVI zonal statistics over administrative boundaries.

    Parameters
    ----------
    boundaries:
        Zone boundaries for aggregation as a :class:`~geopandas.GeoDataFrame`.
        Use :func:`evy.get_boundaries` to fetch from GeoBoundaries, or
        :func:`evy.load_boundaries` to read a local file.
    zone_col:
        Name of the column in ``boundaries`` that identifies each zone. This
        column is passed through to the output unchanged. For GeoBoundaries
        data the conventional value is ``"shapeName"``.
    backend:
        Computation backend:
        - 'gee': Google Earth Engine (server-side, requires authentication)
        - 'local': Local computation via Planetary Computer STAC (no auth needed)
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
        Temporal aggregation frequency. Each period is a calendar period,
        labelled by its start date in the output ``date`` column:
        - 'Original': Original data (composites from source satellites)
        - 'ME': Monthly
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
    include_geometry:
        If True, return GeoDataFrame with geometry column.
        If False, return pandas DataFrame.
    mask_cropland:
        If False, do not mask non-cropland areas using Dynamic World
        land cover classification.
    **kwargs:
        Additional keyword arguments. The following are GEE-only and only
        supported with ``backend='gee'``:

        scale : int or None
            Resolution in meters. Default depends on source:
            - MODIS: 250m (native resolution)
            - Sentinel-2: 10m (native resolution)
        export_to_drive : bool
            If True, export results to Google Drive instead of returning directly.
            Useful for large queries that might timeout.
        drive_folder : str
            Google Drive folder name for exports. Default: 'evy_exports'.
        project : str or None
            Google Earth Engine project ID.
            If None, uses default or environment variable GEE_PROJECT.

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame or str
        If export_to_drive=False: Zonal statistics with columns (identical
        for both backends):
        - 'date': Start of the period (or observation date for 'Original')
        - ``zone_col``: Zone identifier (the user's original column name)
        - 'mean', 'std', etc.: One column per requested statistic
        - 'geometry': Only if include_geometry=True, in the CRS of
          ``boundaries``

        If export_to_drive=True: Task ID string for the export task
    """
    if not isinstance(boundaries, gpd.GeoDataFrame):
        raise TypeError(
            "boundaries must be a GeoDataFrame. "
            "Use evy.get_boundaries('ISO3') to fetch from GeoBoundaries, "
            "or evy.load_boundaries('path.shp') to read a local file."
        )
    if zone_col not in boundaries.columns:
        raise ValueError(
            f"zone_col='{zone_col}' not found in boundaries. "
            f"Available columns: {list(boundaries.columns)}"
        )

    stats = _validate_args(backend, source, freq, stats, kwargs)
    start_date, end_date = _default_dates(start_date, end_date)

    if backend == "local":
        from evy._zonal_local import _zonal_stats_local

        return _zonal_stats_local(
            boundaries=boundaries,
            zone_col=zone_col,
            start_date=start_date,
            end_date=end_date,
            freq=freq,
            stats=stats,
            include_geometry=include_geometry,
            mask_cropland=mask_cropland,
        )

    scale = kwargs.get("scale", None)
    export_to_drive = kwargs.get("export_to_drive", False)
    drive_folder = kwargs.get("drive_folder", "evy_exports")
    project = kwargs.get("project", None)

    _ensure_initialized(project)

    if scale is None:
        scale = 250 if source == "modis" else 10

    logger.info(
        f"Computing zonal stats for EVI from {source.upper()} "
        f"({start_date} to {end_date})"
    )

    features = _gdf_to_ee_feature_collection(boundaries)
    region = features.geometry()

    # GEE end dates are exclusive; add one day so end_date is included,
    # matching the local backend's inclusive STAC search.
    ee_end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    ic = (
        _load_modis_collection(start_date, ee_end, region)
        if source == "modis"
        else _load_sentinel2_collection(start_date, ee_end, region)
    )

    if mask_cropland:
        logger.info("Applying cropland mask (Dynamic World)")
        ic = apply_cropland_mask(ic, region)

    if freq != "Original":
        ic = _aggregate_temporal(ic, start_date, ee_end, freq)

    reducer = _build_reducer(stats)
    fc = _compute_zonal_stats(ic, features, reducer, scale)

    if export_to_drive:
        filename = _generate_export_filename(source, start_date, end_date)
        from evy._convert import export_to_drive as _export

        return _export(fc, filename, drive_folder)
    else:
        # Fetch without geometry and join in client-side if needed
        df = fc_to_dataframe(fc)
        if include_geometry:
            df = _join_geometries(df, boundaries)
        return _to_output_contract(df, zone_col, stats, include_geometry)


def _to_output_contract(
    df: pd.DataFrame, zone_col: str, stats: list[str], include_geometry: bool
) -> pd.DataFrame | gpd.GeoDataFrame:
    """Keep only contract columns from GEE output, in a fixed order.

    GEE names the standard deviation ``stdDev`` and passes every boundary
    attribute through; both are normalized here to match the local backend.
    """
    df = df.rename(columns={"stdDev": "std"})
    cols = ["date", zone_col, *stats] + (["geometry"] if include_geometry else [])
    return df.reindex(columns=cols)


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


def _build_reducer(stats: list[str]):
    """Build combined reducer for multiple statistics."""
    reducer_map = {
        "mean": ee.Reducer.mean(),
        "median": ee.Reducer.median(),
        "min": ee.Reducer.min(),
        "max": ee.Reducer.max(),
        "std": ee.Reducer.stdDev(),
        "sum": ee.Reducer.sum(),
        "count": ee.Reducer.count(),
    }

    selected_reducers = [reducer_map[s] for s in stats]
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
    Aggregate ImageCollection into calendar-period median composites.

    Periods are calendar months, quarters, or years (not offsets from
    ``start_date``), and each composite is stamped with its period start.
    This matches the local backend's ``MS``/``QS``/``YS`` resampling.
    """
    period, months = _GEE_PERIODS[freq]
    # end_date is exclusive here (caller already added one day).
    last_day = pd.Timestamp(end_date) - pd.Timedelta(days=1)
    period_starts = [
        p.start_time.strftime("%Y-%m-%d")
        for p in pd.period_range(start_date, last_day, freq=period)
    ]

    def composite(period_start):
        start = ee.Date(period_start)
        filtered = ic.filterDate(start, start.advance(months, "month"))
        return filtered.median().set("system:time_start", start.millis())

    return ee.ImageCollection.fromImages(ee.List(period_starts).map(composite))


def _generate_export_filename(source: str, start_date: str, end_date: str) -> str:
    """Generate a descriptive filename for exports."""
    start_short = start_date.replace("-", "")[:6]
    end_short = end_date.replace("-", "")[:6]

    return f"evi_{source}_zonal_stats_{start_short}_{end_short}"
