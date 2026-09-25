"""Tests for GEE FeatureCollection -> DataFrame conversion."""

from unittest.mock import patch

import pandas as pd

from evy._convert import fc_to_dataframe


def test_fc_to_dataframe_uses_paged_fetch_and_drops_geo():
    # computeFeatures pages through all results; 6,000 rows is over getInfo()'s limit.
    fetched = pd.DataFrame(
        {"geo": [None] * 6000, "date": ["2023-01-01"] * 6000, "mean": [0.4] * 6000}
    )
    with patch("evy._convert.ee.data.computeFeatures", return_value=fetched) as mock_cf:
        df = fc_to_dataframe("fake-fc")

    assert mock_cf.call_args[0][0]["fileFormat"] == "PANDAS_DATAFRAME"
    assert len(df) == 6000
    assert list(df.columns) == ["date", "mean"]
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_fc_to_dataframe_empty_result_keeps_date_column():
    with patch("evy._convert.ee.data.computeFeatures", return_value=pd.DataFrame()):
        df = fc_to_dataframe("fake-fc")
    assert list(df.columns) == ["date"]
