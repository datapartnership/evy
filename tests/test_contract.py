"""Both backends must return the same output shape (the evy output contract)."""

import numpy as np
import pandas as pd
import pytest
import rioxarray  # noqa: F401 — activates .rio accessor
import xarray as xr

from evy import compute_zonal_stats, zonal_stats
from evy.zonal import _to_output_contract


def _synthetic_modis(evi_values):
    """Tiny EVI/QA Dataset in EPSG:3857 covering the small_boundaries boxes."""
    x = np.arange(500, 223_000, 1000.0)
    y = np.arange(111_500, 0, -1000.0)
    time = pd.to_datetime(["2023-01-05", "2023-01-20", "2023-02-10"])
    shape = (len(time), len(y), len(x))
    evi = np.stack([np.full(shape[1:], v, dtype="float32") for v in evi_values])
    ds = xr.Dataset(
        {
            "evi_raw": (("time", "y", "x"), evi),
            "qa": (("time", "y", "x"), np.zeros(shape, dtype="float32")),
        },
        coords={"time": time, "y": y, "x": x},
    )
    return ds.rio.write_crs("EPSG:3857")


def test_local_output_contract(small_boundaries):
    ds = _synthetic_modis([5000, 3000, 6000])
    out = compute_zonal_stats(
        ds,
        small_boundaries,
        zone_col="shapeName",
        stats=["mean", "std"],
        include_geometry=True,
    )
    assert list(out.columns) == ["date", "shapeName", "mean", "std", "geometry"]
    # Period-start labels, same as GEE.
    assert sorted(out["date"].unique()) == list(
        pd.to_datetime(["2023-01-01", "2023-02-01"])
    )
    jan = out[out["date"] == "2023-01-01"]
    assert np.allclose(jan["mean"], 0.4)  # median of 0.5 and 0.3
    # Geometry comes back in the input CRS, not the raster CRS.
    assert out.crs == small_boundaries.crs
    assert np.allclose(out.total_bounds, small_boundaries.total_bounds, atol=1e-6)


def test_gee_output_contract_renames_and_drops_extras():
    raw = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-01"]),
            "shapeName": ["a"],
            "shapeISO": ["X-A"],
            "_evy_boundary_id": [0],
            "mean": [0.4],
            "stdDev": [0.1],
        }
    )
    out = _to_output_contract(raw, "shapeName", ["mean", "std"], include_geometry=False)
    assert list(out.columns) == ["date", "shapeName", "mean", "std"]
    assert out["std"].iloc[0] == 0.1


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"freq": "D"}, ValueError),
        ({"stats": "stdDev"}, ValueError),
        ({"backend": "Local"}, ValueError),
        ({"scael": 100}, TypeError),
        ({"backend": "local", "scale": 100}, ValueError),
    ],
)
def test_zonal_stats_rejects_bad_args_before_any_work(small_boundaries, kwargs, error):
    # Validation runs before GEE init or downloads, so no network is touched.
    with pytest.raises(error):
        zonal_stats(small_boundaries, zone_col="shapeName", **kwargs)


def test_local_extracts_from_memory_not_lazy_dask(small_boundaries, monkeypatch):
    """Each time step must be computed once before exactextract reads it.

    exactextract reads one window per zone; on a lazy Dask array every read
    repeats the downloads (a 30-zone query took over 51 min instead of 4 min).
    """
    import evy._zonal_local as zl

    seen = []
    original = zl.exact_extract

    def spy(raster, *args, **kwargs):
        seen.append(raster.chunks)
        return original(raster, *args, **kwargs)

    monkeypatch.setattr(zl, "exact_extract", spy)
    ds = _synthetic_modis([5000, 3000, 6000]).chunk({"time": 1})
    compute_zonal_stats(ds, small_boundaries, zone_col="shapeName")
    assert seen and all(chunks is None for chunks in seen)
