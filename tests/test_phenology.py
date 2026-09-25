"""Tests for season detection, including seasons that cross the new year."""

import numpy as np
import pandas as pd
import pytest

from evy.phenology import calculate_phenology, filter_growing_season, get_growing_season


def _seasonal(peak_month: int) -> pd.DataFrame:
    dates = pd.date_range("2021-01-01", "2023-12-31", freq="MS")
    evi = 0.25 + 0.2 * np.cos(2 * np.pi * (dates.month - peak_month) / 12)
    return pd.DataFrame({"date": dates, "mean": evi})


def test_season_within_one_year():
    sos, eos = get_growing_season(_seasonal(peak_month=5))
    assert sos < 5 < eos
    assert calculate_phenology(_seasonal(peak_month=5))["mos"].iloc[0] == 5


def test_season_crossing_new_year():
    ph = calculate_phenology(_seasonal(peak_month=1))
    sos, mos, eos = ph[["sos", "mos", "eos"]].iloc[0]
    # A pure cosine stays above the 20% threshold for +/-4 months around the
    # peak, so the season is Sep..May and EOS is the first month below: Jun.
    assert (sos, mos, eos) == (9, 1, 6)
    assert list(ph["month"]) == list(range(1, 13))  # output back in month order


def test_get_growing_season_raises_on_flat_series():
    dates = pd.date_range("2021-01-01", "2021-12-31", freq="MS")
    flat = pd.DataFrame({"date": dates, "mean": 0.3})
    with pytest.raises(ValueError, match="growing season"):
        get_growing_season(flat)


def test_filter_growing_season_wraps_and_labels_start_year():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2022-09-15", "2022-11-01", "2023-02-01", "2023-05-01"]
            )
        }
    )
    out = filter_growing_season(df, start_month=10, end_month=3)
    assert list(out["date"].dt.month) == [11, 2]
    assert list(out["year"]) == [2022, 2022]


def test_filter_growing_season_empty_when_no_match():
    df = pd.DataFrame({"date": pd.to_datetime(["2022-07-01"])})
    assert filter_growing_season(df, start_month=1, end_month=3).empty
