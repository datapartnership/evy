"""Phenology extraction functions for vegetation time series."""

import logging

import numpy as np
import pandas as pd
import geopandas as gpd

try:
    from scipy.signal import savgol_filter

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

logger = logging.getLogger(__name__)


def preprocess_series(
    series: pd.Series,
    window_length: int = 5,
    polyorder: int = 2,
    outlier_std_multiplier: float = 2.0,
) -> np.ndarray:
    """
    TIMESAT-style preprocessing for vegetation index time series.

    Applies the following steps:
    1. Remove outliers using median filter (values > std * multiplier from rolling median)
    2. Interpolate missing values linearly
    3. Smooth using Savitzky-Golay filter

    Parameters
    ----------
    series:
        Time series of vegetation index values
    window_length:
        Window length for Savitzky-Golay filter (must be odd)
    polyorder:
        Polynomial order for Savitzky-Golay filter
    outlier_std_multiplier:
        Multiplier for standard deviation to identify outliers

    Returns
    -------
    np.ndarray
        Smoothed time series values
    """
    if not HAS_SCIPY:
        raise ImportError(
            "scipy is required for phenology preprocessing. "
            "Install it with: pip install scipy"
        )

    series = series.copy()

    # Step 1
    series = series.interpolate(limit_direction="both")
    median = series.rolling(window=window_length, center=True).median()
    std_dev = series.std()
    series = series.mask((series - median).abs() > outlier_std_multiplier * std_dev)

    # Step 2
    series = series.interpolate(limit_direction="both")

    # Step 3
    wl = min(window_length, len(series))
    if wl % 2 == 0:
        wl -= 1
    if wl < 3:
        wl = 3

    smoothed = savgol_filter(series.values, window_length=wl, polyorder=polyorder)

    return smoothed


def extract_phenology(
    smoothed: np.ndarray,
    dates: np.ndarray | pd.Index,
    threshold: float = 0.2,
) -> dict:
    """
    Extract phenology metrics (SOS, MOS, EOS) from smoothed time series.

    Uses the seasonal amplitude method to identify phenological stages.
    The threshold determines the proportion of amplitude above minimum
    that marks the start and end of the growing season.

    Parameters
    ----------
    smoothed:
        Smoothed vegetation index values
    dates:
        Corresponding dates or indices
    threshold:
        Proportion of amplitude (0-1) above minimum to mark SOS/EOS.
        Lower values detect season earlier/later.

    Returns
    -------
    dict
        Dictionary with keys:
        - 'sos': Start of season date/index (or None)
        - 'mos': Middle/max of season date/index (or None)
        - 'eos': End of season date/index (or None)
        - 'max_value': Maximum vegetation index value
        - 'min_value': Minimum vegetation index value
        - 'amplitude': Seasonal amplitude (max - min)
    """
    max_val = smoothed.max()
    min_val = smoothed.min()
    amplitude = max_val - min_val

    sos = None
    mos = None
    eos = None

    threshold_value = min_val + threshold * amplitude

    # SOS
    for i in range(1, len(smoothed)):
        if sos is None and smoothed[i] > threshold_value:
            sos = dates[i]

        # MOS
        if smoothed[i] == max_val:
            mos = dates[i]

        # EOS
        if sos is not None and smoothed[i] < threshold_value:
            eos = dates[i]
            break

    return {
        "sos": sos,
        "mos": mos,
        "eos": eos,
        "max_value": float(max_val),
        "min_value": float(min_val),
        "amplitude": float(amplitude),
    }


def calculate_phenology(
    df: pd.DataFrame | gpd.GeoDataFrame,
    value_col: str = "mean",
    date_col: str = "date",
    group_col: str | None = None,
    threshold: float = 0.2,
    window_length: int = 5,
    polyorder: int = 2,
) -> pd.DataFrame:
    """
    Calculate phenology metrics from zonal statistics DataFrame.

    Aggregates data by month, applies preprocessing, and extracts
    SOS, MOS, and EOS for each group (if specified).

    Parameters
    ----------
    df:
        DataFrame with zonal statistics output from evy.zonal_stats()
    value_col:
        Column name containing vegetation index values
    date_col:
        Column name containing dates
    group_col:
        Column name to group by (e.g., 'zone_name' for regional analysis).
        If None, calculates phenology for entire dataset.
    threshold:
        Amplitude threshold for SOS/EOS detection
    window_length:
        Savitzky-Golay filter window length
    polyorder:
        Savitzky-Golay filter polynomial order

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - 'month': Month number (1-12)
        - 'value': Mean vegetation index for that month
        - 'smoothed': Smoothed value
        - 'sos': Start of season month
        - 'mos': Middle of season month
        - 'eos': End of season month
        - Plus group_col if specified
    """
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col])

    def _calculate_for_group(group_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate phenology for a single group."""
        monthly = (
            group_df.assign(month=group_df[date_col].dt.month)
            .groupby("month", as_index=False)
            .agg(value=(value_col, "mean"))
        )

        smoothed = preprocess_series(
            monthly["value"],
            window_length=window_length,
            polyorder=polyorder,
        )

        phenology = extract_phenology(
            smoothed,
            monthly["month"].values,
            threshold=threshold,
        )

        result = monthly.assign(
            smoothed=np.round(smoothed, 4),
            sos=phenology["sos"],
            mos=phenology["mos"],
            eos=phenology["eos"],
        )

        return result

    if group_col is None:
        return _calculate_for_group(df)
    else:
        results = []
        for group_name, group_df in df.groupby(group_col):
            group_result = _calculate_for_group(group_df)
            group_result[group_col] = group_name
            results.append(group_result)

        return pd.concat(results, ignore_index=True)


def get_growing_season(
    df: pd.DataFrame,
    value_col: str = "mean",
    date_col: str = "date",
    threshold: float = 0.2,
) -> tuple[int, int]:
    """
    Determine the growing season months from time series data.

    A convenience function that returns the start and end months
    of the primary growing season.

    Parameters
    ----------
    df:
        DataFrame with vegetation index time series
    value_col:
        Column with vegetation index values
    date_col:
        Column with dates
    threshold:
        Amplitude threshold for season detection

    Returns
    -------
    tuple[int, int]
        (start_month, end_month) as integers 1-12
    """
    phenology = calculate_phenology(
        df,
        value_col=value_col,
        date_col=date_col,
        threshold=threshold,
    )

    sos = phenology["sos"].iloc[0]
    eos = phenology["eos"].iloc[0]

    if sos is None or eos is None:
        logger.warning("Could not determine growing season, using defaults (2-6)")
        return (2, 6)

    return (int(sos), int(eos))


def filter_growing_season(
    df: pd.DataFrame,
    date_col: str = "date",
    start_month: int | None = None,
    end_month: int | None = None,
) -> pd.DataFrame:
    """
    Filter DataFrame to include only growing season data.

    Parameters
    ----------
    df:
        DataFrame with time series data
    date_col:
        Column name containing dates
    start_month:
        Start month of growing season (1-12). Default: 2 (February)
    end_month:
        End month of growing season (1-12). Default: 6 (June)

    Returns
    -------
    pd.DataFrame
        Filtered DataFrame with 'year' column added
    """
    if start_month is None:
        start_month = 2
    if end_month is None:
        end_month = 6

    df = df.copy()

    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col])

    start_year = df[date_col].dt.year.min()
    end_year = df[date_col].dt.year.max()

    seasons = []
    for year in range(start_year, end_year + 1):
        season_start = pd.Timestamp(f"{year}-{start_month:02d}-01")
        season_end = pd.Timestamp(f"{year}-{end_month:02d}-28") + pd.offsets.MonthEnd(0)

        season_data = df[
            (df[date_col] >= season_start) & (df[date_col] <= season_end)
        ].assign(year=year)

        if len(season_data) > 0:
            seasons.append(season_data)

    if not seasons:
        logger.warning("No data found in growing season range")
        return df.assign(year=df[date_col].dt.year)

    return pd.concat(seasons, ignore_index=True)
