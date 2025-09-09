import pandas as pd
from scipy.signal import savgol_filter


def preprocess_series(series: pd.Series) -> pd.Series:
    """TIMESAT-style preprocessing."""
    series = series.interpolate(limit_direction="both")  # Step 2: Interpolate
    median = series.rolling(window=5, center=True).median()
    std_dev = series.std()
    series = series.mask(
        (series - median).abs() > 2 * std_dev
    )  # Step 1: Remove outliers
    series = series.interpolate(limit_direction="both")
    smoothed = savgol_filter(series, window_length=5, polyorder=2)  # Step 3: Smooth
    return pd.Series(smoothed, index=series.index)


def extract_sos_mos_eos(
    smoothed: pd.Series, dates: pd.Index, threshold: float = 0.2
) -> tuple[pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None]:
    max_val = smoothed.max()
    min_val = smoothed.min()
    amp = max_val - min_val
    sos = mos = eos = None
    for i in range(1, len(smoothed)):
        if sos is None and smoothed[i] > min_val + threshold * amp:
            sos = dates[i]
        if smoothed[i] == max_val:
            mos = dates[i]
        if sos is not None and smoothed[i] < min_val + threshold * amp:
            eos = dates[i]
            break
    return sos, mos, eos
