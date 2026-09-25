"""Shared fixtures for evy tests."""

from unittest.mock import MagicMock

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    """Point evy's cache at a per-test tmp dir.

    Applied to every test via ``autouse=True`` so unit tests never write to
    the user's real cache directory.
    """
    monkeypatch.setenv("EVY_CACHE_DIR", str(tmp_path / "evy_cache"))
    # Re-resolve the CACHE_DIR module-level constants that captured the
    # env at import time.
    import evy.boundaries
    import evy.cache

    evy.boundaries.CACHE_DIR = evy.boundaries._resolve_cache_dir()
    # evy.cache uses _resolve_cache_dir() lazily, so nothing to patch.
    yield


@pytest.fixture
def small_boundaries() -> gpd.GeoDataFrame:
    """A tiny two-row GeoDataFrame in EPSG:4326."""
    return gpd.GeoDataFrame(
        {
            "shapeName": ["zone_a", "zone_b"],
            "geometry": [box(0.0, 0.0, 1.0, 1.0), box(1.0, 0.0, 2.0, 1.0)],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def fake_zonal_df() -> pd.DataFrame:
    """A fake zonal_stats output for use in cache tests."""
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-31", "2023-02-28"] * 2),
            "shapeName": ["zone_a", "zone_a", "zone_b", "zone_b"],
            "evi_mean": [0.42, 0.51, 0.33, 0.47],
        }
    )


@pytest.fixture
def fake_stac_item():
    """A MagicMock standing in for a STAC item."""
    item = MagicMock()
    item.datetime = pd.Timestamp("2023-06-15", tz="UTC").to_pydatetime()
    item.bbox = [0.0, 0.0, 2.0, 1.0]
    return item
