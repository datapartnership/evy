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

    Applies three sequential steps in the TIMESAT tradition:

    1. Outlier removal — values that deviate from the rolling median by
       more than ``outlier_std_multiplier`` times the series standard
       deviation are masked and then interpolated.
    2. Linear interpolation to fill remaining gaps in both directions.
    3. Savitzky-Golay smoothing of the filled series.

    The implementation is a lightweight Python port of the preprocessing
    stage of the original TIMESAT software (Jönsson & Eklundh 2004), not
    a bit-exact reproduction.

    Parameters
    ----------
    series : pd.Series
        Time series of vegetation index values. Missing values (NaN) are
        allowed and will be interpolated.
    window_length : int, default 5
        Window length for the Savitzky-Golay filter. Must be odd; if an
        even value is passed, it is decremented internally to the next odd
        number. Clamped to at least 3.
    polyorder : int, default 2
        Polynomial order for the Savitzky-Golay filter. Must be less than
        ``window_length``.
    outlier_std_multiplier : float, default 2.0
        Threshold (in standard deviations) above which a value is treated
        as an outlier and masked.

    Returns
    -------
    np.ndarray
        Smoothed values as a float array, same length as the input series.

    Raises
    ------
    ImportError
        If ``scipy`` is not installed. ``scipy`` is a core dependency of
        evy, so this error should not arise in normal installations, but
        the check is retained for users who have installed evy into an
        environment with stripped dependencies.
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
    eos = None
    mos = dates[int(np.argmax(smoothed))]

    threshold_value = min_val + threshold * amplitude

    # A flat series has no season; skip detection so float noise from the
    # smoothing step cannot create a fake SOS.
    if not np.isclose(amplitude, 0.0):
        for i in range(1, len(smoothed)):
            if sos is None and smoothed[i] > threshold_value:
                sos = dates[i]
            elif sos is not None and smoothed[i] < threshold_value:
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

    Aggregates data by calendar month (averaging across years), applies
    preprocessing, and extracts SOS, MOS, and EOS for each group (if
    specified).

    The 12-month cycle is treated as circular: detection starts from the
    lowest month, so a season that crosses the new year (e.g. October to
    March) is found as one season. In that case ``sos`` is greater than
    ``eos`` (e.g. ``sos=10``, ``eos=4``). With two seasons per year, the
    first season after the lowest month is returned.

    Parameters
    ----------
    df:
        DataFrame with zonal statistics output from evy.zonal_stats()
    value_col:
        Column name containing vegetation index values
    date_col:
        Column name containing dates
    group_col:
        Column name to group by (e.g., 'shapeName' for regional analysis).
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
        - 'mos': Middle of season month (month of peak smoothed value)
        - 'eos': End of season month (may be less than 'sos' if the
          season crosses the new year)
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

        # Rotate the cycle to start at the lowest month, so a season that
        # crosses the new year is one contiguous run instead of two pieces.
        start = monthly["value"].idxmin()
        rotated = pd.concat([monthly.iloc[start:], monthly.iloc[:start]])

        smoothed = preprocess_series(
            rotated["value"].reset_index(drop=True),
            window_length=window_length,
            polyorder=polyorder,
        )

        phenology = extract_phenology(
            smoothed,
            rotated["month"].values,
            threshold=threshold,
        )

        result = rotated.assign(
            smoothed=np.round(smoothed, 4),
            sos=phenology["sos"],
            mos=phenology["mos"],
            eos=phenology["eos"],
        )

        return result.sort_values("month").reset_index(drop=True)

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
        (start_month, end_month) as integers 1-12. If the season crosses
        the new year, start_month is greater than end_month (e.g. (10, 4)).

    Raises
    ------
    ValueError
        If no season can be detected (no clear rise above and fall below
        the threshold).
    """
    phenology = calculate_phenology(
        df,
        value_col=value_col,
        date_col=date_col,
        threshold=threshold,
    )

    sos = phenology["sos"].iloc[0]
    eos = phenology["eos"].iloc[0]

    if pd.isna(sos) or pd.isna(eos):
        raise ValueError(
            "Could not detect a growing season: the series has no clear rise "
            "above and fall below the threshold. Choose the months yourself "
            "and pass them to filter_growing_season()."
        )

    return (int(sos), int(eos))


def filter_growing_season(
    df: pd.DataFrame,
    *,
    start_month: int,
    end_month: int,
    date_col: str = "date",
) -> pd.DataFrame:
    """
    Filter DataFrame to include only growing season data.

    Parameters
    ----------
    df:
        DataFrame with time series data
    start_month:
        First month of the growing season (1-12)
    end_month:
        Last month of the growing season (1-12), inclusive. If less than
        ``start_month``, the season crosses the new year (e.g. 10 to 3 is
        October to March).
    date_col:
        Column name containing dates

    Returns
    -------
    pd.DataFrame
        Rows inside the season, with a ``year`` column. ``year`` is the
        year in which the season *starts*, so October 2022 to March 2023
        is labelled 2022. Empty if no rows fall inside the season.
    """
    for name, month in (("start_month", start_month), ("end_month", end_month)):
        if month not in range(1, 13):
            raise ValueError(f"{name} must be 1-12, got {month}")

    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col])

    month = df[date_col].dt.month
    year = df[date_col].dt.year
    if start_month <= end_month:
        in_season = month.between(start_month, end_month)
    else:
        in_season = (month >= start_month) | (month <= end_month)
        # Jan..end_month belong to the season that started the year before.
        year = year - (month <= end_month)

    result = df[in_season].assign(year=year[in_season]).reset_index(drop=True)
    if result.empty:
        logger.warning("No data found in growing season range")
    return result
