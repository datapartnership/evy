"""Opt-in LAADS/PC parity across a MODIS tile boundary, including exports.

Run with EVY_TEST_LAADS=1 and configured Earthdata credentials. Set
EVY_TEST_LAADS_CACHE to reuse validated subsets between live checks.
"""

import os

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from shapely.geometry import box

import evy


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("EVY_TEST_LAADS") != "1", reason="requires NASA login and network"
)
def test_live_laads_pixels_masked_stats_and_export(tmp_path, monkeypatch):
    pytest.importorskip("earthaccess")
    if cache := os.getenv("EVY_TEST_LAADS_CACHE"):
        monkeypatch.setenv("EVY_CACHE_DIR", cache)
    boundary = gpd.GeoDataFrame(
        {"zone": ["probe"]}, geometry=[box(29.9, -2, 30.1, -1.9)], crs=4326
    )
    kwargs = dict(start_date="2023-01-01", end_date="2023-01-20")
    nasa = evy.load_modis(boundary, **kwargs, provider="laads").compute()
    pc = evy.load_modis(boundary, **kwargs, provider="planetary_computer").compute()
    np.testing.assert_array_equal(
        nasa.time, pd.to_datetime(["2023-01-01", "2023-01-09", "2023-01-17"])
    )
    aligned = nasa.reindex(x=pc.x, y=pc.y, method="nearest", tolerance=0.01)
    for key in ("evi_raw", "qa"):
        np.testing.assert_array_equal(aligned[key], pc[key])
    landcover = evy.load_landcover(boundary, pc).compute()
    options = dict(zone_col="zone", stats=["mean", "count"], land_cover=landcover)
    expected = evy.compute_zonal_stats(pc, boundary, **options)
    actual = evy.compute_zonal_stats(aligned, boundary, **options)
    np.testing.assert_allclose(
        actual[["mean", "count"]], expected[["mean", "count"]], rtol=1e-6
    )
    evi = evy.load_evi(boundary, **kwargs, provider="laads").compute()
    assert evi.count().item() > 0
    paths = evy.export_geotiff(evi, tmp_path / "exports")
    assert len(paths) == 3
    with rasterio.open(paths[0]) as source:
        np.testing.assert_allclose(
            source.read(1, masked=True).filled(np.nan), evi.isel(time=0), equal_nan=True
        )
