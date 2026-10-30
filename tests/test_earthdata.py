"""Real HDF4 fixtures exercise NASA decoding without network or credentials."""

from pathlib import Path
import shutil
from unittest.mock import MagicMock, patch

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

pytest.importorskip("earthaccess")
pytest.importorskip("pyhdf")
from pyhdf.SD import SD, SDC

import evy
from evy._earthdata import _open_tile


@pytest.fixture
def nasa(tmp_path, monkeypatch):
    """NASA transport stub; actual pyhdf writes and reads the downloaded files."""
    source = tmp_path / "source"
    source.mkdir()
    granules = []
    monkeypatch.setattr("evy._earthdata._TILE_SIZE", 4000)

    def add(day=1, left=0, value=5000, revision="2023001000000"):
        name = f"MOD13Q1.A2023{day:03d}.h{18 + left // 4000:02d}v08.061.{revision}.hdf"
        path = source / name
        hdf = SD(str(path), SDC.WRITE | SDC.CREATE)
        try:
            hdf.attr("StructMetadata.0").set(
                SDC.CHAR8,
                (
                    f"XDim=4\nYDim=4\nUpperLeftPointMtrs=({left},4000)\n"
                    f"LowerRightMtrs=({left + 4000},0)\nProjection=GCTP_SNSOID\n"
                ),
            )
            raw = np.full((4, 4), value, dtype=np.int16)
            raw[0, 0] = -3000
            qa = np.zeros((4, 4), dtype=np.int8)
            qa[0, 1] = 3
            qa[0, 2] = -1
            for name_, data, dtype, fill in (
                ("250m 16 days EVI", raw, SDC.INT16, -3000),
                ("250m 16 days pixel reliability", qa, SDC.INT8, -1),
            ):
                band = hdf.create(name_, dtype, (4, 4))
                band.setfillvalue(fill)
                band[:] = data
                band.endaccess()
        finally:
            hdf.end()
        granule = MagicMock()
        granule.data_links.return_value = [f"https://example.nasa.gov/{name}"]
        granules.append(granule)
        return path

    def download(results, local_path, threads):
        return [
            Path(shutil.copy(source / Path(result.data_links()[0]).name, local_path))
            for result in results
        ]

    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    monkeypatch.delenv("EARTHDATA_USERNAME", raising=False)
    with (
        patch("earthaccess.login") as login,
        patch("earthaccess.search_data") as search,
        patch("earthaccess.download", side_effect=download) as fetch,
    ):
        login.return_value.authenticated = True
        search.side_effect = lambda short_name, **kwargs: (
            granules if short_name == "MOD13Q1" else []
        )
        yield add, login, search, fetch


def region(right=0.035):
    return gpd.GeoDataFrame(
        {"zone": ["a"]}, geometry=[box(0, 0, right, 0.035)], crs=4326
    )


def test_hdf_pixels_dates_scaling_quality_and_cache(nasa):
    add, login, search, fetch = nasa
    add(day=1)
    add(day=17, value=3000)
    # Overlapping earlier composite and older revision must be excluded.
    add(day=1, value=1000, revision="2022001000000")
    ds = evy.load_modis(region(), "2023-01-01", "2023-01-17", provider="earthdata")
    assert hasattr(ds.evi_raw.data, "dask")
    assert ds.sizes == {"time": 2, "y": 4, "x": 4}
    assert ds.rio.crs.to_dict()["proj"] == "sinu"
    assert ds.x.values.tolist() == [500, 1500, 2500, 3500]
    assert ds.y.values.tolist() == [3500, 2500, 1500, 500]
    np.testing.assert_array_equal(
        ds.time.values, pd.to_datetime(["2023-01-01", "2023-01-17"])
    )
    assert ds.evi_raw.isel(time=0, y=1, x=1).compute().item() == 5000
    assert np.isnan(ds.qa.isel(time=0, y=0, x=2).compute())
    evi = evy.load_evi(
        region(), "2023-01-01", "2023-01-17", provider="earthdata", mask_cropland=False
    ).compute()
    np.testing.assert_allclose(evi[:, 1, 1], [0.5, 0.3])
    assert np.isnan(evi[:, 0, :3]).all()
    assert fetch.call_count == 1  # repeated call uses only complete cached HDFs
    assert len(fetch.call_args.args[0]) == 2
    assert fetch.call_args.kwargs["threads"] == 4
    assert {call.kwargs["short_name"] for call in search.call_args_list} == {
        "MOD13Q1",
        "MYD13Q1",
    }
    login.assert_called_with(strategy="netrc")
    out = evy.zonal_stats(
        region(),
        zone_col="zone",
        backend="local",
        provider="earthdata",
        start_date="2023-01-01",
        end_date="2023-01-17",
        mask_cropland=False,
    )
    np.testing.assert_allclose(out["mean"], [0.4], atol=1e-6)


def test_adjacent_tiles_and_missing_tile_at_another_date(nasa):
    add, _, _, _ = nasa
    add()
    add(left=4000, value=7000)
    add(day=17, value=3000)
    ds = evy.load_modis(
        region(0.07), "2023-01-01", "2023-01-17", provider="earthdata"
    ).compute()
    assert ds.sizes == {"time": 2, "y": 4, "x": 8}
    np.testing.assert_array_equal(np.diff(ds.x), np.full(7, 1000))
    assert ds.evi_raw.isel(time=0, y=1, x=4).item() == 7000
    assert np.isnan(ds.evi_raw.isel(time=1, x=slice(4, None))).all()


def test_overlap_is_filtered_before_download(nasa):
    add, _, _, fetch = nasa
    add(day=1)
    add(day=17)
    ds = evy.load_modis(region(), "2023-01-02", "2023-01-17", provider="earthdata")
    assert ds.sizes["time"] == 1
    assert fetch.call_count == 1
    with pytest.raises(ValueError, match="No NASA MODIS"):
        evy.load_modis(region(), "2023-01-02", "2023-01-10", provider="earthdata")


def test_failed_download_does_not_publish_cache(nasa, tmp_path):
    add, _, _, fetch = nasa
    add()
    fetch.side_effect = lambda *args, **kwargs: []
    with pytest.raises(RuntimeError, match="download incomplete"):
        evy.load_modis(region(), "2023-01-01", "2023-01-01", provider="earthdata")
    assert not list((tmp_path / "evy_cache" / "earthdata").iterdir())


def test_partial_batch_is_not_published_and_can_retry(nasa, tmp_path):
    add, _, _, fetch = nasa
    add()
    add(day=17)
    download = fetch.side_effect
    fetch.side_effect = lambda results, **kwargs: download(results[:1], **kwargs)
    with pytest.raises(RuntimeError, match="download incomplete"):
        evy.load_modis(region(), "2023-01-01", "2023-01-17", provider="earthdata")
    assert not list((tmp_path / "evy_cache" / "earthdata").iterdir())
    fetch.side_effect = download
    ds = evy.load_modis(region(), "2023-01-01", "2023-01-17", provider="earthdata")
    assert ds.sizes["time"] == 2


def test_corrupt_download_is_not_published(nasa, tmp_path):
    from pyhdf.error import HDF4Error

    add, _, _, fetch = nasa
    add()
    download = fetch.side_effect

    def corrupt(results, **kwargs):
        files = download(results, **kwargs)
        files[0].write_bytes(b"not an HDF file")
        return files

    fetch.side_effect = corrupt
    with pytest.raises(HDF4Error):
        evy.load_modis(region(), "2023-01-01", "2023-01-01", provider="earthdata")
    assert not list((tmp_path / "evy_cache" / "earthdata").iterdir())


def test_extended_range_downloads_only_missing_files_in_any_return_order(nasa):
    add, _, _, fetch = nasa
    add()
    evy.load_modis(region(), "2023-01-01", "2023-01-01", provider="earthdata")
    add(day=17, value=3000)
    add(day=33, value=2000)
    download = fetch.side_effect
    fetch.side_effect = lambda *args, **kwargs: download(*args, **kwargs)[::-1]
    ds = evy.load_modis(region(), "2023-01-01", "2023-02-02", provider="earthdata")
    assert fetch.call_count == 2
    assert len(fetch.call_args.args[0]) == 2
    np.testing.assert_allclose(ds.evi_raw[:, 1, 1].compute(), [5000, 3000, 2000])


def test_later_batch_failure_preserves_completed_batches(nasa, tmp_path):
    add, _, _, fetch = nasa
    for day in (1, 17, 33, 49, 65):
        add(day=day)
    download = fetch.side_effect
    fetch.side_effect = lambda results, **kwargs: (
        download(results, **kwargs) if len(results) == 4 else []
    )
    with pytest.raises(RuntimeError, match="download incomplete"):
        evy.load_modis(region(), "2023-01-01", "2023-03-06", provider="earthdata")
    cache = tmp_path / "evy_cache" / "earthdata"
    assert len(list(cache.glob("*.hdf"))) == 4
    fetch.side_effect = download
    ds = evy.load_modis(region(), "2023-01-01", "2023-03-06", provider="earthdata")
    assert len(fetch.call_args.args[0]) == 1
    assert ds.sizes["time"] == 5


def test_auth_and_validation_before_download(nasa):
    _, login, search, fetch = nasa
    with pytest.raises(ValueError, match="start_date"):
        evy.load_modis(region(), "2023-02-01", "2023-01-01", provider="earthdata")
    login.assert_not_called()
    login.return_value.authenticated = False
    with pytest.raises(RuntimeError, match="login failed"):
        evy.load_modis(region(), "2023-01-01", "2023-01-01", provider="earthdata")
    search.assert_not_called()
    fetch.assert_not_called()


def test_environment_credentials_and_login_exception(nasa, monkeypatch):
    from earthaccess.exceptions import LoginStrategyUnavailable

    add, login, _, _ = nasa
    add()
    monkeypatch.setenv("EARTHDATA_TOKEN", "test-token")
    evy.load_modis(region(), "2023-01-01", "2023-01-01", provider="earthdata")
    login.assert_called_with(strategy="environment")
    login.side_effect = LoginStrategyUnavailable("missing credentials")
    with pytest.raises(RuntimeError, match="Configure Earthdata credentials"):
        evy.load_modis(region(), "2023-01-01", "2023-01-01", provider="earthdata")


def test_missing_optional_reader_has_install_instructions():
    with patch.dict("sys.modules", {"pyhdf.SD": None}):
        with pytest.raises(ImportError, match=r"evy\[earthdata\]"):
            evy.load_modis(region(), "2023-01-01", "2023-01-01", provider="earthdata")


def test_window_reads_only_intersecting_pixels(nasa):
    add, _, _, _ = nasa
    tile = _open_tile(add(), pd.Timestamp("2023-01-01"), (1100, 1100, 1900, 1900))
    assert tile.sizes == {"time": 1, "y": 1, "x": 1}
    assert tile.rio.resolution() == (1000, -1000)
    assert tile.evi_raw.compute().item() == 5000
    assert (
        _open_tile(add(day=17), pd.Timestamp("2023-01-17"), (5000, 0, 6000, 1000))
        is None
    )
