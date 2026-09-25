"""Extraction, normalization, and orchestration for local EVI zonal statistics."""

import logging

import dask
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

# evy stat name -> exactextract stat name (only where they differ).
_EXACTEXTRACT_STATS = {"std": "stdev"}
# Memory for one block of time steps computed together. Larger blocks let
# Dask download more files in parallel.
# ponytail: fixed 1 GB budget; derive from available RAM if users hit limits.
_BLOCK_BYTES = 1_000_000_000
# Threads for computing blocks. The work is mostly waiting on downloads, but
# too many requests trigger server throttling (Rwanda ADM2, 1 year: 8 threads
# finished in 40 s; 32 threads had not finished after 4 min).
# A num_workers value set by the user in the Dask config takes precedence.
_IO_THREADS = 8


def _normalize_output(
    df: pd.DataFrame,
    zone_col: str,
    stats: list[str],
    include_geometry: bool,
    crs,
) -> pd.DataFrame | gpd.GeoDataFrame:
    """Shape raw extraction output into the evy output contract.

    Parameters
    ----------
    df : pd.DataFrame
        Raw output from :func:`_extract_zonal`, with exactextract stat names,
        ``date`` values as :class:`datetime.date` objects, and a
        ``geometry`` column in the raster CRS.
    zone_col : str
        Zone identifier column.
    stats : list of str
        evy stat names that were requested.
    include_geometry : bool
        When ``True``, keep the geometry column and return a
        :class:`~geopandas.GeoDataFrame`.  When ``False``, return a plain
        :class:`~pandas.DataFrame`.
    crs
        CRS of the input boundaries. Geometry is reprojected back to it.

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame
        Columns ``date``, ``zone_col``, one column per stat, and optionally
        ``geometry``, matching the GEE backend.
    """
    df = df.rename(columns={v: k for k, v in _EXACTEXTRACT_STATS.items()})
    df["date"] = pd.to_datetime(df["date"])
    cols = ["date", zone_col, *stats]

    if include_geometry:
        return gpd.GeoDataFrame(df, geometry="geometry").to_crs(crs)[
            cols + ["geometry"]
        ]
    return pd.DataFrame(df[cols])


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
    stats : list of str
        evy statistic names; translated to exactextract names here.
    zone_col : str
        Name of the column in ``boundaries`` that identifies each zone. The
        column is passed through to the output unchanged.

    Returns
    -------
    pd.DataFrame
        Concatenated results with columns from ``exact_extract`` plus a ``date``
        column (:class:`datetime.date` objects). ``geometry`` is in the
        raster CRS.
    """
    import rioxarray  # noqa: F401 — activates .rio accessor

    boundaries = boundaries.to_crs(evi.rio.crs)
    ee_stats = [_EXACTEXTRACT_STATS.get(s, s) for s in stats]

    # Compute time steps in memory before extraction. exactextract reads one
    # window per zone, and on a lazy (Dask) array each read would repeat the
    # downloads and the median, so cost would grow with zones x time steps.
    # Steps are computed in blocks so their files download in parallel.
    n_steps = evi.sizes["time"]
    step_bytes = evi.nbytes // max(n_steps, 1)
    block = max(1, _BLOCK_BYTES // max(step_bytes, 1))

    threads = dask.config.get("num_workers", None) or _IO_THREADS

    all_results = []
    for start in range(0, n_steps, block):
        with dask.config.set(num_workers=threads):
            evi_block = evi.isel(time=slice(start, start + block)).compute()
        for time_val in evi_block["time"].values:
            result = exact_extract(
                evi_block.sel(time=time_val),
                boundaries,
                ee_stats,
                include_cols=[zone_col],
                include_geom=True,
                output="pandas",
            )
            result["date"] = pd.to_datetime(time_val).date()
            all_results.append(result)

    result = pd.concat(all_results, ignore_index=True)
    return gpd.GeoDataFrame(result, geometry="geometry", crs=evi.rio.crs)


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
        ``"ME"``, ``"QE"``, ``"YE"``, or ``"Original"``. Periods are
        labelled by their start date.
    stats : str or list of str
        Statistics to compute (e.g. ``"mean"``, ``["mean", "std"]``).
    include_geometry : bool
        When ``True``, return a :class:`~geopandas.GeoDataFrame` with zone
        geometries attached, in the CRS of ``boundaries``.

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame
        Columns ``date``, ``zone_col``, one column per stat (``mean``,
        ``std``, ...), and optionally ``geometry``.
    """
    stats = [stats] if isinstance(stats, str) else list(stats)
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
    return _normalize_output(df, zone_col, stats, include_geometry, boundaries.crs)


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
        Zonal statistics in the evy output contract (see :func:`evy.zonal_stats`).
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
