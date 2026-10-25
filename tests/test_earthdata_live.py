"""Opt-in authenticated NASA/Planetary Computer parity and export check.

Run with EVY_TEST_EARTHDATA=1 and installed evy[earthdata]. Optionally set
EVY_TEST_EARTHDATA_CACHE to reuse downloaded HDFs between test runs.
"""

import os

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from shapely.geometry import box

import evy
from evy._process import prepare_evi


@pytest.mark.skipif(
    os.getenv("EVY_TEST_EARTHDATA") != "1",
    reason="requires live NASA credentials and network",
)
def test_live_nasa_pixels_stats_and_export(tmp_path, monkeypatch):
    pytest.importorskip("earthaccess")
    pytest.importorskip("pyhdf")
    if cache := os.getenv("EVY_TEST_EARTHDATA_CACHE"):
        monkeypatch.setenv("EVY_CACHE_DIR", cache)
    # Cross the h20/h21 tile boundary, including Terra and Aqua observations.
    boundary = gpd.GeoDataFrame(
        {"zone": ["probe"]}, geometry=[box(29.9, -2.0, 30.1, -1.9)], crs=4326
    )
    nasa = evy.load_modis(
        boundary, "2023-01-01", "2023-01-20", provider="earthdata"
    ).compute()
    pc = evy.load_modis(boundary, "2023-01-01", "2023-01-20").compute()
    np.testing.assert_array_equal(
        nasa.time, pd.to_datetime(["2023-01-01", "2023-01-09", "2023-01-17"])
    )
    # Providers can select different outermost rows. Compare identical cells;
    # NASA metadata and COG coordinates differ by fractions of a millimetre.
    aligned = nasa.reindex(x=pc.x, y=pc.y, method="nearest", tolerance=0.01)
    for name, fill in (("evi_raw", -3000), ("qa", -1)):
        np.testing.assert_array_equal(aligned[name].fillna(fill), pc[name].fillna(fill))
    kwargs = dict(zone_col="zone", freq="Original", stats=["mean", "count"])
    actual = evy.compute_zonal_stats(aligned, boundary, **kwargs)
    expected = evy.compute_zonal_stats(pc, boundary, **kwargs)
    np.testing.assert_allclose(
        actual[["mean", "count"]], expected[["mean", "count"]], rtol=1e-7
    )
    evi = prepare_evi(nasa)
    assert evi.count().item() > 0
    cropped = evy.load_evi(
        boundary, "2023-01-01", "2023-01-20", provider="earthdata"
    ).compute()
    assert cropped.sizes == evi.sizes
    np.testing.assert_array_equal(cropped.x, evi.x)
    np.testing.assert_array_equal(cropped.y, evi.y)
    assert cropped.count().item() > 0
    assert cropped.count().item() <= evi.count().item()
    paths = evy.export_geotiff(evi, tmp_path / "exports")
    assert len(paths) == 3
    with rasterio.open(paths[0]) as src:
        np.testing.assert_allclose(
            src.read(1, masked=True).filled(np.nan), evi.isel(time=0), equal_nan=True
        )
        assert src.crs == nasa.rio.crs
