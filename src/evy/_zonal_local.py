"""Extraction, normalization, and orchestration for local EVI zonal statistics."""

import logging

import geopandas as gpd
import pandas as pd
import xarray as xr
from exactextract import exact_extract

from evy._process import (
    apply_cropland_mask,
    apply_quality_mask,
    aggregate_temporal,
    scale_evi,
)
from evy.load import load_landcover, load_modis

logger = logging.getLogger(__name__)

_KNOWN_STATS = {"mean", "median", "min", "max", "std", "sum", "count"}


def _normalize_output(
    df: pd.DataFrame, include_geometry: bool
) -> pd.DataFrame | gpd.GeoDataFrame:
    """Rename stat columns to evi_* prefix, convert dates, and handle geometry.

    Parameters
    ----------
    df : pd.DataFrame
        Raw output from :func:`_extract_zonal` with un-prefixed stat columns,
        ``date`` values as :class:`datetime.date` objects, and optionally a
        ``geometry`` column.
    include_geometry : bool
        When ``True``, keep the geometry column and return a
        :class:`~geopandas.GeoDataFrame`.  When ``False``, drop geometry and
        return a plain :class:`~pandas.DataFrame`.

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame
        Normalized DataFrame with ``evi_<stat>`` columns and
        :class:`~pandas.Timestamp` dates.
    """
    rename_map = {col: f"evi_{col}" for col in df.columns if col in _KNOWN_STATS}
    df = df.rename(columns=rename_map)

    df["date"] = pd.to_datetime(df["date"])

    if include_geometry and "geometry" in df.columns:
        return gpd.GeoDataFrame(df, geometry="geometry")

    if "geometry" in df.columns:
        df = df.drop(columns=["geometry"])

    return pd.DataFrame(df)


def _extract_zonal(
    evi: xr.DataArray,
    boundaries: gpd.GeoDataFrame,
    stats: str | list[str],
    zone_col: str,
) -> pd.DataFrame:
    """Extract zonal statistics for each timestep.

    Parameters
    ----------
    evi : xr.DataArray
        Scaled and quality-masked EVI DataArray with ``time``, ``y``, ``x``
        dimensions and a CRS set via ``rioxarray``.
    boundaries : gpd.GeoDataFrame
        Zone boundaries.
    stats : str or list of str
        One or more statistic names accepted by :func:`exactextract.exact_extract`.
    zone_col : str
        Name of the column in ``boundaries`` that identifies each zone. The
        column is passed through to the output unchanged.

    Returns
    -------
    pd.DataFrame
        Concatenated results with columns from ``exact_extract`` plus a ``date``
        column (:class:`datetime.date` objects).
    """
    import rioxarray  # noqa: F401 — activates .rio accessor

    boundaries = boundaries.to_crs(evi.rio.crs)

    all_results = []
    for time_val in evi["time"].values:
        date = pd.to_datetime(time_val).date()
        evi_slice = evi.sel(time=time_val)
        result = exact_extract(
            evi_slice,
            boundaries,
            stats,
            include_cols=[zone_col],
            include_geom=True,
            output="pandas",
        )
        result["date"] = date
        all_results.append(result)

    return pd.concat(all_results, ignore_index=True)


def compute_zonal_stats(
    ds_evi: xr.Dataset,
    boundaries: gpd.GeoDataFrame,
    *,
    zone_col: str,
    land_cover: xr.DataArray | None = None,
    freq: str = "ME",
    stats: str | list[str] = "mean",
    include_geometry: bool = False,
) -> pd.DataFrame | gpd.GeoDataFrame:
    """Compute EVI zonal statistics from a local dataset.

    This is the public entry point for local zonal statistics.  It runs the
    full processing pipeline: quality masking → scaling → temporal aggregation
    → optional cropland masking → zonal extraction → output normalization.

    Parameters
    ----------
    ds_evi : xr.Dataset
        Dataset with ``evi_raw`` and ``qa`` variables (dims ``time``, ``y``,
        ``x``).
    boundaries : gpd.GeoDataFrame
        Zone boundaries.
    zone_col : str
        Name of the column in ``boundaries`` that identifies each zone. The
        column is passed through to the output unchanged.
    land_cover : xr.DataArray, optional
        Land cover raster for cropland masking.  When provided, non-cropland
        pixels are masked before computing statistics.
    freq : str
        Pandas-compatible resample frequency string (e.g. ``"ME"``,
        ``"QE"``, ``"YE"``, ``"Original"``).
    stats : str or list of str
        Statistics to compute (e.g. ``"mean"``, ``["mean", "std"]``).
    include_geometry : bool
        When ``True``, return a :class:`~geopandas.GeoDataFrame` with zone
        geometries attached.

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame
        Zonal statistics with ``evi_<stat>`` columns.
    """
    logger.info("Applying quality mask and scaling to EVI data...")
    evi = apply_quality_mask(ds_evi)
    evi = scale_evi(evi)

    logger.info(f"Aggregating EVI to {freq} frequency using median...")
    evi = aggregate_temporal(evi, freq)

    if land_cover is not None:
        logger.info("Applying cropland mask...")
        evi = apply_cropland_mask(evi, land_cover)

    logger.info("Extracting zonal statistics...")
    df = _extract_zonal(evi, boundaries, stats, zone_col)
    return _normalize_output(df, include_geometry)


def _zonal_stats_local(
    boundaries: gpd.GeoDataFrame,
    *,
    zone_col: str,
    start_date: str,
    end_date: str,
    freq: str = "ME",
    stats: "str | list[str]" = "mean",
    include_geometry: bool = False,
    mask_cropland: bool = True,
) -> "pd.DataFrame | gpd.GeoDataFrame":
    """Internal orchestrator for local-backend zonal statistics.

    Called by :func:`evy.zonal.zonal_stats` when ``backend="local"``.

    Parameters
    ----------
    boundaries : gpd.GeoDataFrame
        Zone boundaries.
    zone_col : str
        Name of the column in ``boundaries`` that identifies each zone.
    start_date : str
        Start date as ISO string (e.g. ``"2020-01-01"``).
    end_date : str
        End date as ISO string (e.g. ``"2020-12-31"``).
    freq : str
        Temporal aggregation frequency (pandas-style resample string).
    stats : str or list of str
        Statistics to compute.
    include_geometry : bool
        When ``True``, attach zone geometries to the output.
    mask_cropland : bool
        When ``True``, load ESA WorldCover land cover and restrict statistics
        to cropland pixels only.

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame
        Zonal statistics with ``evi_<stat>`` columns.
    """
    logger.info("Loading MODIS EVI data from Planetary Computer...")
    ds_evi = load_modis(boundaries, start_date, end_date)

    land_cover = None
    if mask_cropland:
        logger.info("Loading land cover data for cropland masking...")
        land_cover = load_landcover(boundaries, ds_evi)

    logger.info("Computing zonal statistics...")
    return compute_zonal_stats(
        ds_evi,
        boundaries,
        zone_col=zone_col,
        land_cover=land_cover,
        freq=freq,
        stats=stats,
        include_geometry=include_geometry,
    )
