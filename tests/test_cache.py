"""Tests for the parquet-cached zonal_stats wrapper in evy.cache."""

from unittest.mock import patch

import pandas as pd
import pytest

from evy.cache import (
    _hash_boundaries,
    _make_cache_key,
    cached_zonal_stats,
    clear_zonal_cache,
)


def test_hash_boundaries_is_deterministic(small_boundaries):
    a = _hash_boundaries(small_boundaries, "shapeName")
    b = _hash_boundaries(small_boundaries.copy(), "shapeName")
    assert a == b
    assert len(a) == 16


def test_hash_boundaries_changes_with_zones(small_boundaries):
    flipped = small_boundaries.copy()
    flipped["shapeName"] = ["zone_c", "zone_d"]
    assert _hash_boundaries(small_boundaries, "shapeName") != _hash_boundaries(
        flipped, "shapeName"
    )


def test_make_cache_key_changes_with_dates(small_boundaries):
    base = dict(
        boundaries=small_boundaries,
        zone_col="shapeName",
        backend="local",
        source="modis",
        start_date="2023-01-01",
        end_date="2023-06-30",
        freq="ME",
        stats="mean",
        mask_cropland=True,
        include_geometry=False,
        user_key=None,
    )
    assert _make_cache_key(**base) != _make_cache_key(
        **{**base, "end_date": "2023-12-31"}
    )


def test_make_cache_key_changes_with_gee_kwargs(small_boundaries):
    base = dict(
        boundaries=small_boundaries,
        zone_col="shapeName",
        backend="gee",
        source="modis",
        start_date="2023-01-01",
        end_date="2023-06-30",
        freq="ME",
        stats="mean",
        mask_cropland=True,
        include_geometry=False,
        user_key=None,
    )
    assert _make_cache_key(**base, extra={"scale": 250}) != _make_cache_key(
        **base, extra={"scale": 500}
    )


def test_cached_zonal_stats_keys_on_resolved_default_dates(
    tmp_path, small_boundaries, fake_zonal_df
):
    """Without dates, the key must use today's window, not a frozen None."""
    with patch("evy.zonal.zonal_stats", return_value=fake_zonal_df) as mock_zs:
        cached_zonal_stats(small_boundaries, zone_col="shapeName", cache_dir=tmp_path)
    _, kwargs = mock_zs.call_args
    assert kwargs["start_date"] is not None and kwargs["end_date"] is not None


def test_make_cache_key_honors_user_key(small_boundaries):
    explicit = _make_cache_key(
        boundaries=small_boundaries,
        zone_col="shapeName",
        backend="local",
        source="modis",
        start_date="2023-01-01",
        end_date="2023-06-30",
        freq="ME",
        stats="mean",
        mask_cropland=True,
        include_geometry=False,
        user_key="my-pinned-key",
    )
    assert explicit == "my-pinned-key"


def test_cached_zonal_stats_writes_then_reads(
    tmp_path, small_boundaries, fake_zonal_df
):
    """First call computes + writes parquet; second call hits the cache."""
    cache_dir = tmp_path / "zonal_cache"

    with patch("evy.zonal.zonal_stats", return_value=fake_zonal_df) as mock_zs:
        first = cached_zonal_stats(
            small_boundaries,
            zone_col="shapeName",
            backend="local",
            start_date="2023-01-01",
            end_date="2023-02-28",
            cache_dir=cache_dir,
        )
        second = cached_zonal_stats(
            small_boundaries,
            zone_col="shapeName",
            backend="local",
            start_date="2023-01-01",
            end_date="2023-02-28",
            cache_dir=cache_dir,
        )

    # Underlying zonal_stats called exactly once.
    assert mock_zs.call_count == 1
    pd.testing.assert_frame_equal(first, fake_zonal_df)
    pd.testing.assert_frame_equal(
        second.reset_index(drop=True),
        fake_zonal_df.reset_index(drop=True),
    )
    assert list(cache_dir.glob("*.parquet"))


def test_cached_zonal_stats_recompute_forces_recall(
    tmp_path, small_boundaries, fake_zonal_df
):
    cache_dir = tmp_path / "zonal_cache"
    with patch("evy.zonal.zonal_stats", return_value=fake_zonal_df) as mock_zs:
        cached_zonal_stats(
            small_boundaries,
            zone_col="shapeName",
            backend="local",
            start_date="2023-01-01",
            end_date="2023-02-28",
            cache_dir=cache_dir,
        )
        cached_zonal_stats(
            small_boundaries,
            zone_col="shapeName",
            backend="local",
            start_date="2023-01-01",
            end_date="2023-02-28",
            cache_dir=cache_dir,
            recompute=True,
        )
    assert mock_zs.call_count == 2


def test_cached_zonal_stats_rejects_drive_export(small_boundaries):
    with pytest.raises(TypeError, match="export_to_drive"):
        cached_zonal_stats(
            small_boundaries,
            zone_col="shapeName",
            export_to_drive=True,
        )


def test_clear_zonal_cache_removes_files(tmp_path, small_boundaries, fake_zonal_df):
    cache_dir = tmp_path / "zonal_cache"
    with patch("evy.zonal.zonal_stats", return_value=fake_zonal_df):
        cached_zonal_stats(
            small_boundaries,
            zone_col="shapeName",
            backend="local",
            start_date="2023-01-01",
            end_date="2023-02-28",
            cache_dir=cache_dir,
        )
    assert any(cache_dir.glob("*.parquet"))
    removed = clear_zonal_cache(cache_dir=cache_dir)
    assert removed == 1
    assert not any(cache_dir.glob("*.parquet"))


def test_clear_zonal_cache_on_missing_dir_returns_zero(tmp_path):
    removed = clear_zonal_cache(cache_dir=tmp_path / "does-not-exist")
    assert removed == 0


def test_cached_zonal_stats_roundtrips_geometry(
    tmp_path, small_boundaries, fake_zonal_df
):
    """include_geometry=True must round-trip a GeoDataFrame through parquet."""
    import geopandas as gpd

    fake_gdf = gpd.GeoDataFrame(
        fake_zonal_df.assign(
            geometry=[
                small_boundaries.geometry.iloc[0],
                small_boundaries.geometry.iloc[0],
                small_boundaries.geometry.iloc[1],
                small_boundaries.geometry.iloc[1],
            ]
        ),
        geometry="geometry",
        crs="EPSG:4326",
    )

    cache_dir = tmp_path / "zonal_cache"
    with patch("evy.zonal.zonal_stats", return_value=fake_gdf) as mock_zs:
        first = cached_zonal_stats(
            small_boundaries,
            zone_col="shapeName",
            backend="local",
            start_date="2023-01-01",
            end_date="2023-02-28",
            include_geometry=True,
            cache_dir=cache_dir,
        )
        second = cached_zonal_stats(
            small_boundaries,
            zone_col="shapeName",
            backend="local",
            start_date="2023-01-01",
            end_date="2023-02-28",
            include_geometry=True,
            cache_dir=cache_dir,
        )

    assert mock_zs.call_count == 1
    assert isinstance(first, gpd.GeoDataFrame)
    assert isinstance(second, gpd.GeoDataFrame)
    assert second.crs.to_epsg() == 4326
    assert second.geometry.notna().all()
