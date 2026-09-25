"""Tests for boundaries cache-dir behavior and helpers."""

from pathlib import Path


from evy.boundaries import _ensure_crs, _resolve_cache_dir


def test_resolve_cache_dir_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("EVY_CACHE_DIR", str(tmp_path / "custom_cache"))
    resolved = _resolve_cache_dir()
    assert resolved == tmp_path / "custom_cache" / "boundaries"


def test_resolve_cache_dir_defaults_to_platformdirs(monkeypatch):
    monkeypatch.delenv("EVY_CACHE_DIR", raising=False)
    resolved = _resolve_cache_dir()
    # Whatever platformdirs returns, it should NOT be inside the current cwd
    # (that was the old footgun).
    cwd = Path.cwd().resolve()
    assert not str(resolved.resolve()).startswith(str(cwd))
    assert resolved.name == "boundaries"
    assert resolved.parent.name == "evy"


def test_get_boundaries_returns_independent_copies(monkeypatch, small_boundaries):
    import evy.boundaries as b

    monkeypatch.setitem(b._MEMORY_CACHE, "TST_ADM1_gbOpen", small_boundaries)
    first = b.get_boundaries("TST")
    first["extra"] = 1
    assert "extra" not in b.get_boundaries("TST").columns


def test_ensure_crs_assigns_when_missing():
    import geopandas as gpd
    from shapely.geometry import box

    gdf = gpd.GeoDataFrame({"geometry": [box(0, 0, 1, 1)]}, crs=None)
    out = _ensure_crs(gdf)
    assert str(out.crs) == "EPSG:4326"


def test_ensure_crs_reprojects_when_different():
    import geopandas as gpd
    from shapely.geometry import box

    gdf = gpd.GeoDataFrame({"geometry": [box(0, 0, 1, 1)]}, crs="EPSG:3857")
    out = _ensure_crs(gdf)
    assert str(out.crs) == "EPSG:4326"
    # Reprojected geometry should no longer be the original 0..1 box.
    minx, miny, maxx, maxy = out.total_bounds
    assert maxx != 1.0 or maxy != 1.0
