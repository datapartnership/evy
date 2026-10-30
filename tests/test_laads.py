"""Real NetCDF subsets exercise lazy LAADS reads, caching, and tile mosaics."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from requests.cookies import RequestsCookieJar

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from shapely.geometry import box

import evy
from evy._earthdata import _TILE_SIZE, _find_modis_tiles
from evy._laads import _decode_subset, _read_subset


@pytest.fixture
def laads(monkeypatch):
    pytest.importorskip("earthaccess")
    with rasterio.Env() as env:
        if "netCDF" not in env.drivers():
            pytest.skip("requires GDAL NetCDF reader")
    name = "MYD13Q1.A2023009.h20v09.061.2023026194807.hdf"
    pixel = _TILE_SIZE / 4800
    left, top = 2 * _TILE_SIZE, 0
    # Exact pixel edges keep the fixture's requested shape at 49x49.
    bounds = (
        left + (4552.1 * pixel),
        top - (912.9 * pixel),
        left + (4600.9 * pixel),
        top - (864.1 * pixel),
    )
    selected = {
        ("MYD13Q1", "2023009", "h20v09"): (name, pd.Timestamp("2023-01-09"), None)
    }
    monkeypatch.setattr("evy._laads.sleep", lambda _: None)
    monkeypatch.setattr(
        "evy._laads._find_modis_tiles", lambda *args: (selected, bounds)
    )
    payload = (
        Path(__file__).parent / "fixtures" / "laads-aqua-subset.nc4"
    ).read_bytes()
    session = MagicMock()
    session.headers = {}
    session.cookies = RequestsCookieJar()
    response = MagicMock(status_code=200, content=payload)
    with (
        patch("earthaccess.get_requests_https_session", return_value=session),
        patch("evy._laads.requests.Session") as factory,
    ):
        fetch = factory.return_value.__enter__.return_value.get
        fetch.return_value = response
        yield selected, bounds, fetch, payload


def region():
    return gpd.GeoDataFrame(
        {"zone": ["a"]}, geometry=[box(29.5, -1.9, 29.6, -1.8)], crs=4326
    )


def test_login_network_failure_is_sanitized_and_retried(monkeypatch):
    import requests

    monkeypatch.setattr("evy._earthdata.sleep", lambda _: None)
    with (
        patch(
            "earthaccess.login",
            side_effect=requests.ConnectionError("private Authorization header"),
        ) as login,
        patch("earthaccess.search_data") as search,
    ):
        with pytest.raises(RuntimeError, match="login connection failed") as exc:
            _find_modis_tiles(region(), "2023-01-01", "2023-01-20")
        assert login.call_count == 3
        assert exc.value.__suppress_context__
        assert "private" not in str(exc.value)
        search.assert_not_called()


def test_invalid_dates_fail_before_nasa_login():
    with patch("earthaccess.login") as login:
        with pytest.raises(ValueError, match="start_date"):
            _find_modis_tiles(region(), "2023-02-01", "2023-01-01")
        login.assert_not_called()


def test_lazy_pixels_scaling_quality_and_cache(laads, tmp_path):
    _, _, fetch, payload = laads
    ds = evy.load_modis(region(), "2023-01-01", "2023-01-20")
    fetch.assert_not_called()
    assert ds.sizes == {"time": 1, "y": 49, "x": 49}
    assert ds.rio.crs.to_dict()["proj"] == "sinu"
    actual = ds.compute()
    assert fetch.call_count == 1  # EVI and QA share the same download task.
    expected = _decode_subset(payload, (49, 49))
    np.testing.assert_array_equal(actual.evi_raw[0], expected[0])
    np.testing.assert_array_equal(actual.qa[0], expected[1])
    assert (expected[1] == 3).any()
    url = fetch.call_args.args[0]
    assert "/61/MYD13Q1/2023/009/" in url
    constraint = fetch.call_args.kwargs["params"]["dap4.ce"]
    assert "[864:1:912][4552:1:4600]" in constraint
    assert "_250m_16_days_EVI" in constraint and "_pixel_reliability" in constraint
    evi = evy.load_evi(
        region(), "2023-01-01", "2023-01-20", provider="laads", mask_cropland=False
    ).compute()
    good = (expected[1] <= 1) & (expected[0] >= -2000) & (expected[0] <= 10000)
    np.testing.assert_allclose(evi[0].values[good], expected[0][good] * 0.0001)
    assert np.isnan(evi[0].values[~good]).all()
    assert fetch.call_count == 1
    assert len(list((tmp_path / "evy_cache" / "laads").glob("*.nc4"))) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 503])
def test_http_failure_is_sanitized_and_not_cached(laads, tmp_path, status):
    _, _, fetch, _ = laads
    fetch.return_value.status_code = status
    fetch.return_value.text = "secret signed URL must never appear"
    with pytest.raises(RuntimeError, match=f"HTTP {status}") as exc:
        evy.load_modis(region(), "2023-01-01", "2023-01-20", provider="laads").compute()
    assert "secret" not in str(exc.value)
    assert not list((tmp_path / "evy_cache" / "laads").glob("*"))


def test_invalid_subset_is_not_cached_and_retry_succeeds(laads, tmp_path):
    _, _, fetch, payload = laads
    fetch.return_value.content = b"<html>login page or signed error URL</html>"
    ds = evy.load_modis(region(), "2023-01-01", "2023-01-20", provider="laads")
    with pytest.raises(ValueError, match="NetCDF4 subset"):
        ds.compute()
    assert not list((tmp_path / "evy_cache" / "laads").glob("*"))
    fetch.return_value.content = payload
    assert ds.compute().sizes["time"] == 1
    assert fetch.call_count == 2


def test_wrong_shape_is_rejected(laads):
    with pytest.raises(ValueError, match="dimensions"):
        _decode_subset(laads[3], (48, 49))


def test_transient_failure_retries(laads):
    _, _, fetch, payload = laads
    fetch.side_effect = [
        MagicMock(status_code=503),
        MagicMock(status_code=200, content=payload),
    ]
    ds = evy.load_modis(
        region(), "2023-01-01", "2023-01-20", provider="laads"
    ).compute()
    assert ds.sizes["time"] == 1
    assert fetch.call_count == 2


def test_connection_errors_do_not_leak_credentials(laads):
    import requests

    _, _, fetch, _ = laads
    fetch.side_effect = requests.ConnectionError("secret signed URL")
    with pytest.raises(RuntimeError, match="LAADS request failed") as exc:
        evy.load_modis(region(), "2023-01-01", "2023-01-20", provider="laads").compute()
    assert "secret" not in str(exc.value)
    assert exc.value.__suppress_context__
    assert fetch.call_count == 3


def test_distinct_windows_do_not_reuse_incompatible_cache(laads, tmp_path):
    selected, _, fetch, _ = laads
    name = next(iter(selected.values()))[0]
    cache = tmp_path / "windows"
    _read_subset(name, (864, 913, 4552, 4601), cache, {}, {})
    _read_subset(name, (864, 913, 4553, 4602), cache, {}, {})
    assert fetch.call_count == 2
    assert len(list(cache.glob("*.nc4"))) == 2


def test_adjacent_tiles_missing_date_and_shared_grid(laads, monkeypatch):
    selected, _, fetch, _ = laads
    date = pd.Timestamp("2023-01-09")
    name = next(iter(selected.values()))[0]
    selected[("MYD13Q1", "2023009", "h21v09")] = (
        name.replace("h20v09", "h21v09"),
        date,
        None,
    )
    selected[("MYD13Q1", "2023025", "h20v09")] = (
        name.replace("A2023009", "A2023025"),
        date + pd.Timedelta(days=16),
        None,
    )
    pixel = _TILE_SIZE / 4800
    edge = 3 * _TILE_SIZE
    bounds = (edge - 48.9 * pixel, -912.9 * pixel, edge + 48.9 * pixel, -864.1 * pixel)
    monkeypatch.setattr(
        "evy._laads._find_modis_tiles", lambda *args: (selected, bounds)
    )
    ds = evy.load_modis(
        region(), "2023-01-01", "2023-01-31", provider="laads"
    ).compute()
    assert ds.sizes == {"time": 2, "y": 49, "x": 98}
    np.testing.assert_allclose(np.diff(ds.x), pixel, atol=1e-8)
    assert np.isnan(ds.evi_raw.isel(time=1, x=slice(49, None))).all()
    assert fetch.call_count == 3


def test_laads_flows_through_stats_and_export(laads, tmp_path):
    stats = evy.zonal_stats(
        region(),
        zone_col="zone",
        backend="local",
        provider="laads",
        start_date="2023-01-01",
        end_date="2023-01-20",
        mask_cropland=False,
        stats=["mean", "count"],
    )
    assert list(stats.columns) == ["date", "zone", "mean", "count"]
    assert stats["count"].iloc[0] > 0
    evi = evy.load_evi(
        region(), "2023-01-01", "2023-01-20", provider="laads", mask_cropland=False
    )
    paths = evy.export_geotiff(evi, tmp_path / "export")
    assert len(paths) == 1
    with rasterio.open(paths[0]) as src:
        assert src.shape == (49, 49)
