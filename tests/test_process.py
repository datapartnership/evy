"""Tests for the pure raster steps of the local backend."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from evy._process import aggregate_temporal, scale_evi


def test_scale_evi_masks_out_of_range_instead_of_clipping():
    raw = xr.DataArray([-3000.0, -2000.0, 5000.0, 10000.0, 12000.0])
    out = scale_evi(raw).values
    assert np.isnan(out[0]) and np.isnan(out[4])
    assert np.allclose(out[1:4], [-0.2, 0.5, 1.0])


def test_aggregate_temporal_labels_period_start():
    time = pd.to_datetime(["2023-01-05", "2023-01-20", "2023-04-10"])
    da = xr.DataArray([1.0, 3.0, 5.0], dims="time", coords={"time": time})
    monthly = aggregate_temporal(da, "ME")
    assert monthly["time"].values[0] == np.datetime64("2023-01-01")
    assert monthly.values[0] == 2.0
    quarterly = aggregate_temporal(da, "QE")
    assert list(quarterly["time"].values) == list(
        pd.to_datetime(["2023-01-01", "2023-04-01"])
    )


def test_aggregate_temporal_rejects_unknown_freq():
    da = xr.DataArray(
        [1.0], dims="time", coords={"time": pd.to_datetime(["2023-01-01"])}
    )
    with pytest.raises(ValueError, match="freq"):
        aggregate_temporal(da, "D")
