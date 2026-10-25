"""Raster export and annual land-cover behavior, without network access."""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import rasterio
import rioxarray  # noqa: F401
import xarray as xr

import evy
from evy._process import apply_cropland_mask, prepare_evi


def raster(values, **coords):
    dims = [*coords, "y", "x"]
    return xr.DataArray(
        values,
        dims=dims,
        coords={**coords, "y": [15, 5], "x": [5, 15]},
        name="evi",
    ).rio.write_crs(32637)


def test_annual_crop_mask_matches_observation_year():
    times = pd.to_datetime(["2022-12-20", "2023-01-05"])
    evi = raster(np.full((2, 2, 2), 0.5), time=times)
    lc = raster([[[5, 2], [0, 5]], [[2, 5], [5, 0]]], year=[2022, 2023])
    lc.attrs["crop_class"] = 5
    result = apply_cropland_mask(evi, lc)
    np.testing.assert_equal(
        result.values, [[[0.5, np.nan], [np.nan, 0.5]], [[np.nan, 0.5], [0.5, np.nan]]]
    )
    with pytest.raises(ValueError, match="2023"):
        apply_cropland_mask(evi, lc.sel(year=[2022]))


def test_prepare_evi_quality_scale_and_static_worldcover():
    raw = raster([[[5000, 12000], [3000, 4000]]], time=pd.to_datetime(["2023-01-01"]))
    qa = xr.zeros_like(raw)
    qa.values[0, 1, 1] = 3
    lc = raster([[40, 40], [2, 40]])
    out = prepare_evi(xr.Dataset({"evi_raw": raw, "qa": qa}), lc)
    np.testing.assert_allclose(out.values, [[[0.5, np.nan], [np.nan, np.nan]]])


def test_geotiff_roundtrip_and_overwrite_protection(tmp_path):
    data = raster(
        [[[0.5, np.nan], [0.2, 0.3]], [[0.1, 0.2], [0.3, 0.4]]],
        time=pd.to_datetime(["2022-12-20", "2023-01-05"]),
    )
    paths = evy.export_geotiff(data.chunk({"time": 1}), tmp_path)
    assert [p.name for p in paths] == ["evi_2022-12-20.tif", "evi_2023-01-05.tif"]
    with rasterio.open(paths[0]) as src:
        assert src.crs.to_epsg() == 32637
        assert src.res == (10, 10)
        assert src.count == 1
        assert np.isnan(src.nodata)
        np.testing.assert_allclose(src.read(1), data.values[0])
    with pytest.raises(FileExistsError):
        evy.export_geotiff(data, tmp_path)


def test_export_native_classes_and_binary_mask(tmp_path):
    lc = (
        raster([[0, 5], [2, 5]]).rename("landcover").astype("uint8").rio.write_nodata(0)
    )
    paths = evy.export_geotiff(lc, tmp_path)
    with rasterio.open(paths[0]) as src:
        assert src.nodata == 0
        np.testing.assert_equal(src.read(1), lc.values)
    mask = (
        (lc == 5)
        .where(lc != 0, 255)
        .astype("uint8")
        .rename("cropland")
        .rio.write_nodata(255)
    )
    path = evy.export_geotiff(mask, tmp_path)[0]
    with rasterio.open(path) as src:
        assert src.nodata == 255
        np.testing.assert_equal(src.read(1), [[255, 1], [0, 1]])


def test_export_failed_write_does_not_publish_file(tmp_path):
    data = raster([[1.0, 2.0], [3.0, 4.0]])
    with patch(
        "rioxarray.raster_array.RasterArray.to_raster", side_effect=OSError("failed")
    ):
        with pytest.raises(OSError, match="failed"):
            evy.export_geotiff(data, tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("year", [2016, 2026])
def test_esri_rejects_unavailable_year_before_network(small_boundaries, year):
    with pytest.raises(ValueError, match="2017–2025"):
        evy.load_landcover(small_boundaries, source="esri", year=year)


def test_esri_loader_uses_years_and_current_download_urls(small_boundaries):
    feature = {
        "properties": {"ImageName": "37M"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[36, -8], [42, -8], [42, 0], [36, 0], [36, -8]]],
        },
    }
    grid = raster(np.ones((2, 2, 2)), time=pd.to_datetime(["2023-05-01", "2025-06-01"]))
    layer = grid.isel(time=[0]).rename("data").to_dataset()
    with (
        patch("evy.load._esri_footprints", return_value=[feature]),
        patch("evy.load.odc_stac.load", return_value=layer) as load,
    ):
        lc = evy.load_landcover(small_boundaries, grid, source="esri")
    assert list(lc.year.values) == [2023, 2025]
    assert lc.attrs["crop_class"] == 5
    calls = load.call_args_list
    assert (
        calls[0]
        .args[0][0]
        .assets["data"]
        .href.endswith("lc2023/37M_20230101-20240101.tif")
    )
    assert (
        calls[1]
        .args[0][0]
        .assets["data"]
        .href.endswith("lc2025/37M_20250101-20251231.tif")
    )
    assert calls[0].kwargs["like"] is grid
    assert calls[0].kwargs["resampling"] == "mode"


def test_export_annual_series_names(tmp_path):
    lc = raster(np.ones((2, 2, 2), dtype="uint8"), year=[2024, 2025]).rename(
        "landcover"
    )
    paths = evy.export_geotiff(lc, tmp_path)
    assert [p.name for p in paths] == ["landcover_2024.tif", "landcover_2025.tif"]


def test_load_evi_returns_pixels_with_selected_mask(small_boundaries):
    raw = raster([[[5000, 5000], [5000, 5000]]], time=pd.to_datetime(["2023-01-01"]))
    ds = xr.Dataset({"evi_raw": raw, "qa": xr.zeros_like(raw)})
    lc = raster([[[5, 2], [0, 5]]], year=[2023])
    lc.attrs["crop_class"] = 5
    with (
        patch("evy.load.load_modis", return_value=ds),
        patch("evy.load.load_landcover", return_value=lc) as load_lc,
    ):
        data = evy.load_evi(
            small_boundaries, "2023-01-01", "2023-01-31", landcover_source="esri"
        )
    assert load_lc.call_args.kwargs["source"] == "esri"
    assert data.dims == ("time", "y", "x")
    np.testing.assert_allclose(data.values, [[[0.5, np.nan], [np.nan, 0.5]]])


@pytest.mark.parametrize("source,crop", [("worldcover", 40), ("esri", 5)])
def test_landcover_retains_exact_target_coordinates(small_boundaries, source, crop):
    raw = raster(np.full((1, 2, 2), 5000), time=pd.to_datetime(["2023-01-01"]))
    ds = xr.Dataset({"evi_raw": raw, "qa": xr.zeros_like(raw)})
    layer = raster([[[crop, 2], [crop, crop]]], time=raw.time.values)
    layer = layer.assign_coords(x=layer.x + 1e-8, y=layer.y - 1e-8)
    feature = {
        "properties": {"ImageName": "37M"},
        "geometry": small_boundaries.geometry.iloc[0].__geo_interface__,
    }
    with (
        patch("evy.load._stac_search", return_value=[object()]),
        patch("evy.load._esri_footprints", return_value=[feature]),
        patch("evy.load.odc_stac.load", return_value=layer.to_dataset(name="map" if source == "worldcover" else "data")),
    ):
        lc = evy.load_landcover(small_boundaries, ds, source=source)
    np.testing.assert_array_equal(lc.x, ds.x)
    np.testing.assert_array_equal(lc.y, ds.y)
    result = prepare_evi(ds, lc)
    assert result.sizes == raw.sizes
    np.testing.assert_allclose(result, [[[0.5, np.nan], [0.5, 0.5]]])
