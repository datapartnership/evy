import logging

import geopandas as gpd
import pandas as pd
import plotnine as p9
import rioxarray as rio  # noqa: F401
import xarray as xr
import xvec  # noqa: F401

from evy.phenology import preprocess_series

logger = logging.getLogger(__name__)
xr.set_options(keep_attrs=True)


def aggregate_by(
    data: xr.DataArray,
    dim: str,
    method: str = "mean",
    freq: str | None = None,
    **kwargs,
) -> xr.DataArray:
    """
    Aggregate data along a specified dimension.

    Args:
        data: xarray DataArray with EVI data
        dim: The dimension to aggregate by (e.g., 'time', 'x', 'y')
        method: The aggregation method to use (e.g., 'mean', 'sum', 'max', 'median', 'std')
        freq: For time dimension, frequency string ('ME'=monthly, 'YE'=yearly, 'QE'=quarterly, 'W'=weekly)
              If None and dim='time', performs simple aggregation across all time steps
        **kwargs: Additional arguments for the aggregation method

    Returns:
        DataArray with aggregated data
    """
    if dim == "time" and freq is not None:
        resampled = data.resample(time=freq)
        if method == "mean":
            aggregated = resampled.mean(**kwargs)
        elif method == "median":
            aggregated = resampled.median(**kwargs)
        elif method == "max":
            aggregated = resampled.max(**kwargs)
        elif method == "min":
            aggregated = resampled.min(**kwargs)
        elif method == "std":
            aggregated = resampled.std(**kwargs)
        elif method == "sum":
            aggregated = resampled.sum(**kwargs)
        else:
            raise ValueError(f"Unsupported aggregation method: {method}")
    else:
        if method == "mean":
            aggregated = data.mean(dim=dim, **kwargs)
        elif method == "sum":
            aggregated = data.sum(dim=dim, **kwargs)
        elif method == "max":
            aggregated = data.max(dim=dim, **kwargs)
        elif method == "min":
            aggregated = data.min(dim=dim, **kwargs)
        elif method == "std":
            aggregated = data.std(dim=dim, **kwargs)
        elif method == "median":
            aggregated = data.median(dim=dim, **kwargs)
        else:
            raise ValueError(f"Unsupported aggregation method: {method}")

    return aggregated


def compute_anomalies(
    data: xr.DataArray,
    baseline_years: tuple[int, int] | tuple[str, str],
    target_years: tuple[int, int] | tuple[str, str] | None = None,
    method: str = "zscore",
) -> xr.DataArray:
    """
    Compute vegetation anomalies using z-score or other methods.

    Args:
        data: xarray DataArray with EVI data
        baseline_years: Baseline period as (start, end) - can be years (int) or dates (str)
        target_years: Target period as (start, end). If None, uses all data after baseline
        method: Anomaly calculation method ('zscore', 'difference', 'percentage')

    Returns:
        DataArray with anomaly values
    """
    if isinstance(baseline_years[0], int):
        baseline_start = f"{baseline_years[0]}-01-01"
        baseline_end = f"{baseline_years[1]}-12-31"
    else:
        baseline_start, baseline_end = baseline_years

    if target_years is None:
        target_start = baseline_end
        target_end = str(data.time.max().values)[:10]  # get date part
    elif isinstance(target_years[0], int):
        target_start = f"{target_years[0]}-01-01"
        target_end = f"{target_years[1]}-12-31"
    else:
        target_start, target_end = target_years

    baseline = data.sel(time=slice(baseline_start, baseline_end))
    target = data.sel(time=slice(target_start, target_end))

    if method == "zscore":
        anomalies = (target - baseline.mean()) / baseline.std()
    elif method == "difference":
        anomalies = target - baseline.mean()
    elif method == "percentage":
        anomalies = ((target - baseline.mean()) / baseline.mean()) * 100
    else:
        raise ValueError(f"Unsupported anomaly method: {method}")

    return anomalies


def compute_aggregated_anomalies(
    data: xr.DataArray,
    geometries: gpd.GeoDataFrame,
    baseline_years: tuple[int, int] | tuple[str, str],
    target_years: tuple[int, int] | tuple[str, str] | None = None,
    method: str = "zscore",
    stats_funcs: str | list[str] = "mean",
    temporal_freq: str | None = None,
) -> gpd.GeoDataFrame:
    """
    Chain anomaly calculation with zonal statistics for aggregated results.

    Args:
        data: xarray DataArray with EVI data
        geometries: GeoDataFrame with geometries for zonal stats
        baseline_years: Baseline period for anomaly calculation
        target_years: Target period for anomaly calculation
        method: Anomaly calculation method ('zscore', 'difference', 'percentage')
        stats_funcs: Statistics to compute ('mean', 'median', etc.)
        temporal_freq: Optional temporal aggregation before anomaly calculation

    Returns:
        GeoDataFrame with aggregated anomaly statistics
    """
    if temporal_freq is not None:
        data = data.pipe(aggregate_by, dim="time", freq=temporal_freq, method="mean")

    anomalies = data.pipe(
        compute_anomalies,
        baseline_years=baseline_years,
        target_years=target_years,
        method=method,
    )

    aggregated_anomalies = anomalies.pipe(
        zonal_stats, geometries=geometries, stats_funcs=stats_funcs
    )

    return aggregated_anomalies


def compute_difference(
    data: xr.DataArray,
    baseline_years: tuple[int, int] | tuple[str, str],
    target_years: tuple[int, int] | tuple[str, str],
    annual: bool = True,
):
    """
    Compute the difference between target EVI and baseline, for each year.

    Args:
        data: xarray DataArray with EVI data
        baseline_years: Baseline period as (start_year, end_year) or (start_date, end_date)
        target_years: Target period as (start_year, end_year) or (start_date, end_date)
        annual: If True, calculate yearly differences; if False, overall difference

    Returns:
        DataArray with difference values
    """
    if isinstance(baseline_years[0], int):
        baseline_start = f"{baseline_years[0]}-01-01"
        baseline_end = f"{baseline_years[1]}-12-31"
    else:
        baseline_start, baseline_end = baseline_years

    if isinstance(target_years[0], int):
        target_start = f"{target_years[0]}-01-01"
        target_end = f"{target_years[1]}-12-31"
    else:
        target_start, target_end = target_years

    baseline = data.sel(time=slice(baseline_start, baseline_end))
    target = data.sel(time=slice(target_start, target_end))

    if annual:
        baseline_yearly = baseline.pipe(aggregate_by, dim="time", freq="YE")
        target_yearly = target.pipe(aggregate_by, dim="time", freq="YE")
        differences = target_yearly - baseline_yearly.mean()
    else:
        differences = target.mean() - baseline.mean()
    return differences


def zonal_stats(
    data: xr.DataArray,
    geometries: gpd.GeoDataFrame,
    stats_funcs: str | list[str] | dict = "mean",
    temporal_agg: str | None = None,
) -> gpd.GeoDataFrame:
    """
    Compute zonal statistics for the given geometries.

    Args:
        data: EVI data
        geometries: GeoDataFrame with geometries for zonal statistics
        stats_funcs: Statistics to compute. Supported: 'mean', 'max', 'min', 'sum', 'std', 'var', 'count'
        temporal_agg: Optional temporal aggregation frequency ('ME', 'YE', 'QE') before zonal stats

    Returns:
        GeoDataFrame with zonal statistics
    """
    SUPPORTED_STATS = ["mean", "max", "min", "sum", "std", "var", "count"]

    if isinstance(stats_funcs, str):
        stats_funcs = [stats_funcs]

    if isinstance(stats_funcs, list):
        unsupported = [stat for stat in stats_funcs if stat not in SUPPORTED_STATS]
        if unsupported:
            logger.warning(
                f"Unsupported stats functions: {unsupported}. "
                f"Supported functions: {SUPPORTED_STATS}"
            )

            stats_funcs = [stat for stat in stats_funcs if stat in SUPPORTED_STATS]
            if not stats_funcs:
                logger.warning("No valid stats functions remaining, using 'mean'")
                stats_funcs = ["mean"]

    if temporal_agg is not None:
        data = data.pipe(aggregate_by, dim="time", freq=temporal_agg)

    if data.rio.crs is None:
        logger.warning("Data missing CRS information, setting default CRS (EPSG:4326)")
        data = data.rio.write_crs("EPSG:4326")

    if "zone_id" not in geometries.columns:
        geometries = geometries.reset_index().rename(columns={"index": "zone_id"})

    zonal_data = data.xvec.zonal_stats(
        geometries.geometry, x_coords="x", y_coords="y", stats=stats_funcs
    )

    zonal_gdf = (
        zonal_data.xvec.to_geodataframe()
        .reset_index()
        .filter(["geometry", "time", "zonal_statistics", "evi"])
        .drop_duplicates()
        .merge(geometries, on="geometry")
    )
    return zonal_gdf


def compute_phenology(
    data: xr.DataArray,
    geometries: gpd.GeoDataFrame,
    stats_funcs: str | list[str] = "mean",
    aggregate_years: bool = False,
) -> pd.DataFrame:
    """
    Compute comprehensive phenological analysis for given geometries.

    Args:
        data: xarray DataArray with EVI data
        geometries: GeoDataFrame with geometries for analysis
        stats_funcs: Statistics to compute for zonal analysis
        aggregate_years: If True, compute phenology across all years combined (climatology)
                        If False, compute phenology for each year separately

    Returns:
        DataFrame with phenological metrics
    """
    logger.info("Computing zonal statistics for phenological analysis...")

    zonal_data = data.pipe(
        zonal_stats, geometries, stats_funcs=stats_funcs, temporal_agg="ME"
    )

    if aggregate_years:
        monthly_evi = (
            zonal_data.assign(month=lambda df: df.time.dt.month)
            .groupby(["zone_id", "month"], as_index=False)
            .agg({"evi": "mean"})
        )

        logger.info("Preprocessing and smoothing time series...")
        monthly_data = []

        # TO DO: extract phenological parameters
        for _, group in monthly_evi.groupby("zone_id"):
            group = group.sort_values("month")
            smoothed_values = preprocess_series(group["evi"])
            group = group.assign(evi_smoothed=smoothed_values)
            monthly_data.append(group)

    else:
        monthly_evi = (
            zonal_data.assign(
                month=lambda df: df.time.dt.month, year=lambda df: df.time.dt.year
            )
            .groupby(["zone_id", "year", "month"], as_index=False)
            .agg({"evi": "mean"})
        )

        logger.info("Preprocessing and smoothing time series...")
        monthly_data = []

        # TO DO: extract phenological parameters
        for (_, _), group in monthly_evi.groupby(["zone_id", "year"]):
            group = group.sort_values("month")
            smoothed_values = preprocess_series(group["evi"])
            group = group.assign(evi_smoothed=smoothed_values)
            monthly_data.append(group)

    monthly_data = (
        pd.concat(monthly_data, ignore_index=True) if monthly_data else pd.DataFrame()
    )

    return monthly_data


def plot_phenology(
    data: xr.DataArray, geometries: gpd.GeoDataFrame, aggregate_years: bool = False
):
    """
    Plot the growing season for each region.

    Args:
        data: xarray DataArray with EVI data
        geometries: GeoDataFrame with geometries for analysis
        aggregate_years: If True, plot based on all years; if False, plot by year
    """
    logger.info("Computing phenology for plotting...")
    phenology = data.pipe(
        compute_phenology, geometries, aggregate_years=aggregate_years
    )

    MONTH_LABELS = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    if aggregate_years:
        plot = (
            p9.ggplot(phenology)
            + p9.geom_line(
                p9.aes(x="month", y="evi_smoothed", group="zone_id"),
                color="steelblue",
                size=1,
            )
            + p9.geom_point(p9.aes(x="month", y="evi", group="zone_id"), size=0.5)
            + p9.scale_x_continuous(breaks=range(1, 13), labels=MONTH_LABELS)
            + p9.theme_minimal()
            + p9.labs(title="Climatological Phenology", x="Month", y="EVI")
        )
    else:
        plot = (
            p9.ggplot(phenology)
            + p9.geom_line(
                p9.aes(
                    x="month",
                    y="evi_smoothed",
                    color="factor(year)",
                ),
                size=1,
                alpha=0.7,
            )
            + p9.geom_point(
                p9.aes(
                    x="month",
                    y="evi",
                    color="factor(year)",
                ),
                size=0.5,
                alpha=0.6,
            )
            + p9.scale_x_continuous(breaks=range(1, 13), labels=MONTH_LABELS)
            + p9.theme_minimal()
            + p9.facet_wrap("zone_id", ncol=2)
            + p9.labs(title="Annual Phenology", x="Month", y="EVI")
        )

    return plot
