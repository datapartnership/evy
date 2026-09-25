"""Disk-cached wrapper around :func:`evy.zonal_stats` for fast recipe iteration.

The function :func:`cached_zonal_stats` is a drop-in replacement for
:func:`evy.zonal_stats` that stores results as parquet on disk, keyed by a
hash of the call arguments. Repeated calls with identical inputs skip the
STAC/GEE round trip and return in milliseconds.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Literal, Union

import geopandas as gpd
import pandas as pd
from platformdirs import user_cache_dir


logger = logging.getLogger(__name__)


def _resolve_cache_dir() -> Path:
    """Resolve the zonal-stats cache directory.

    Honors the ``EVY_CACHE_DIR`` environment variable, otherwise falls back
    to the platform user cache directory.
    """
    override = os.environ.get("EVY_CACHE_DIR")
    base = Path(override) if override else Path(user_cache_dir("evy"))
    return base / "zonal"


def _hash_boundaries(boundaries: gpd.GeoDataFrame, zone_col: str) -> str:
    """Compact deterministic fingerprint of a boundary GeoDataFrame.

    Uses total_bounds (rounded to 6 decimal places) + row count + sorted
    zone identifiers. This is not cryptographic; it's a recipe-iteration
    cache key. Users wanting bulletproof keying can pass ``cache_key``
    explicitly.
    """
    bounds = tuple(round(float(b), 6) for b in boundaries.total_bounds)
    zones = tuple(sorted(str(v) for v in boundaries[zone_col].tolist()))
    payload = json.dumps(
        {"bounds": bounds, "n": len(boundaries), "zones": zones},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# Bump when the zonal_stats output format changes, so old cache files are
# not returned in the old format. v2: plain stat names, period-start dates.
_SCHEMA_VERSION = 2


def _make_cache_key(
    *,
    boundaries: gpd.GeoDataFrame,
    zone_col: str,
    backend: str,
    source: str,
    start_date: str | None,
    end_date: str | None,
    freq: str,
    stats: str | list[str],
    mask_cropland: bool,
    include_geometry: bool,
    user_key: str | None,
    extra: dict | None = None,
) -> str:
    if user_key is not None:
        return user_key
    stats_norm = sorted([stats] if isinstance(stats, str) else list(stats))
    payload = {
        "schema": _SCHEMA_VERSION,
        "extra": extra or {},
        "boundaries": _hash_boundaries(boundaries, zone_col),
        "zone_col": zone_col,
        "backend": backend,
        "source": source,
        "start_date": start_date,
        "end_date": end_date,
        "freq": freq,
        "stats": stats_norm,
        "mask_cropland": mask_cropland,
        "include_geometry": include_geometry,
    }
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:24]


def cached_zonal_stats(
    boundaries: gpd.GeoDataFrame,
    *,
    zone_col: str,
    backend: Literal["gee", "local"] = "gee",
    source: Literal["modis", "sentinel2"] = "modis",
    start_date: str | None = None,
    end_date: str | None = None,
    freq: str = "ME",
    stats: str | list[str] = "mean",
    include_geometry: bool = False,
    mask_cropland: bool = True,
    cache_key: str | None = None,
    cache_dir: Union[str, Path, None] = None,
    recompute: bool = False,
    **kwargs,
) -> pd.DataFrame | gpd.GeoDataFrame:
    """Disk-cached wrapper around :func:`evy.zonal_stats`.

    On cache miss, calls :func:`evy.zonal_stats` and writes the result as a
    parquet file. On cache hit, returns the parquet contents directly,
    skipping the expensive STAC/GEE round trip.

    Parameters
    ----------
    boundaries, zone_col, backend, source, start_date, end_date, freq, stats, include_geometry, mask_cropland
        Forwarded to :func:`evy.zonal_stats` on cache miss. The cache key is
        derived from these arguments, so changing any of them produces a
        different cache file.
    cache_key : str, optional
        Explicit cache key, used verbatim instead of the hash of call
        arguments. Useful when you want to share an entry across slightly
        different invocations or pin a known-good result.
    cache_dir : str or Path, optional
        Override the cache directory. Defaults to the ``EVY_CACHE_DIR``
        environment variable, or the platform user cache directory (e.g.
        ``~/Library/Caches/evy/zonal`` on macOS, ``~/.cache/evy/zonal`` on
        Linux).
    recompute : bool
        Force recomputation, ignoring any cache hit. The fresh result is
        written back to the cache.
    **kwargs
        Additional GEE-only keyword arguments forwarded to
        :func:`evy.zonal_stats`. ``export_to_drive=True`` is rejected —
        caching a Drive-export task ID is meaningless; use
        :func:`evy.zonal_stats` directly for that path.

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame
        Same shape as :func:`evy.zonal_stats`. Returns a
        :class:`~geopandas.GeoDataFrame` iff ``include_geometry=True``.

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('RWA', admin_level=1)
    >>> df = evy.cached_zonal_stats(gdf, zone_col='shapeName', backend='local',
    ...                             start_date='2023-01-01', end_date='2023-12-31')
    >>> df2 = evy.cached_zonal_stats(gdf, zone_col='shapeName', backend='local',
    ...                              start_date='2023-01-01', end_date='2023-12-31')
    # First call: ~minutes. Second call: cache hit, ~milliseconds.
    """
    from evy.zonal import _default_dates, zonal_stats

    if kwargs.get("export_to_drive", False):
        raise ValueError(
            "cached_zonal_stats does not support export_to_drive=True. "
            "Use evy.zonal_stats directly for Drive exports."
        )

    if cache_dir is None:
        cache_dir = _resolve_cache_dir()
    cache_dir = Path(cache_dir)

    # Resolve default dates now: a key built from None would keep returning
    # the window that was "the last year" when the entry was first written.
    start_date, end_date = _default_dates(start_date, end_date)

    key = _make_cache_key(
        boundaries=boundaries,
        zone_col=zone_col,
        backend=backend,
        source=source,
        start_date=start_date,
        end_date=end_date,
        freq=freq,
        stats=stats,
        mask_cropland=mask_cropland,
        include_geometry=include_geometry,
        user_key=cache_key,
        extra=kwargs,
    )
    cache_file = cache_dir / f"{key}.parquet"

    if cache_file.exists() and not recompute:
        logger.info("cached_zonal_stats: cache hit (%s)", cache_file)
        if include_geometry:
            return gpd.read_parquet(cache_file)
        return pd.read_parquet(cache_file)

    logger.info("cached_zonal_stats: cache miss, computing (%s)", cache_file.name)
    result = zonal_stats(
        boundaries,
        zone_col=zone_col,
        backend=backend,
        source=source,
        start_date=start_date,
        end_date=end_date,
        freq=freq,
        stats=stats,
        include_geometry=include_geometry,
        mask_cropland=mask_cropland,
        **kwargs,
    )

    cache_dir.mkdir(parents=True, exist_ok=True)
    result.to_parquet(cache_file)
    logger.info("cached_zonal_stats: wrote %s", cache_file)

    return result


def clear_zonal_cache(cache_dir: Union[str, Path, None] = None) -> int:
    """Remove all cached zonal-stats parquet files.

    Parameters
    ----------
    cache_dir : str or Path, optional
        Override the cache directory. Defaults to the same location used by
        :func:`cached_zonal_stats`.

    Returns
    -------
    int
        Number of files removed.
    """
    if cache_dir is None:
        cache_dir = _resolve_cache_dir()
    cache_dir = Path(cache_dir)
    if not cache_dir.exists():
        return 0
    files = list(cache_dir.glob("*.parquet"))
    for f in files:
        f.unlink()
    logger.info("Removed %d cached zonal-stats files from %s", len(files), cache_dir)
    return len(files)
