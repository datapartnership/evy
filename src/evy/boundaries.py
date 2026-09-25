"""Fetch and load administrative boundaries."""

import logging
import os
from pathlib import Path
from typing import Union

import geopandas as gpd
import requests
from platformdirs import user_cache_dir

logger = logging.getLogger(__name__)


def _resolve_cache_dir() -> Path:
    """Resolve the boundaries cache directory.

    Honors the ``EVY_CACHE_DIR`` environment variable when set (useful for
    tests and CI). Otherwise uses the platform-native user cache directory
    (``~/Library/Caches/evy`` on macOS, ``~/.cache/evy`` on Linux).
    """
    override = os.environ.get("EVY_CACHE_DIR")
    base = Path(override) if override else Path(user_cache_dir("evy"))
    return base / "boundaries"


CACHE_DIR = _resolve_cache_dir()
_MEMORY_CACHE: dict[str, gpd.GeoDataFrame] = {}

GEOBOUNDARIES_BASE_URL = "https://www.geoboundaries.org/api/current"
CRS = "EPSG:4326"


def _legacy_cache_dir() -> Path:
    """Old cwd-based cache location used by evy before the platformdirs migration."""
    return Path.cwd() / ".evy" / "boundaries"


def _warn_legacy_cache_once():
    """Emit a one-time warning if an old cwd-based cache is present."""
    legacy = _legacy_cache_dir()
    if legacy.exists() and any(legacy.glob("*.geojson")):
        logger.warning(
            "Found legacy boundaries cache at %s. evy now caches to %s; "
            "you can safely delete the legacy directory.",
            legacy,
            CACHE_DIR,
        )


def get_boundaries(
    iso3: str,
    admin_level: int = 1,
    release_type: str = "gbOpen",
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """
    Fetch administrative boundaries from GeoBoundaries API.

    Results are cached locally for faster subsequent access.

    Parameters
    ----------
    iso3:
        ISO3 country code (e.g., 'USA', 'KEN', 'SYR')
    admin_level:
        Administrative level:
        - 0: Country
        - 1: Province/State (default)
        - 2: District/County
        - 3-5: Lower levels (availability varies)
    release_type:
        GeoBoundaries release type:
        - 'gbOpen': Open license data (default)
        - 'gbHumanitarian': Humanitarian use
        - 'gbAuthoritative': Most authoritative
    use_cache:
        Whether to use cached data if available

    Returns
    -------
    gpd.GeoDataFrame
        Boundary geometries in EPSG:4326 with columns:
        - 'shapeName': Zone name
        - 'shapeISO': ISO code for zone (if available)
        - 'shapeType': Administrative type
        - 'geometry': Polygon/MultiPolygon geometry

    Raises
    ------
    ValueError
        If admin_level not in 0-5 or ISO3 code not found
    """
    if admin_level not in range(6):
        raise ValueError(f"admin_level must be 0-5, got {admin_level}")

    iso3 = iso3.upper()
    cache_key = f"{iso3}_ADM{admin_level}_{release_type}"

    if use_cache and cache_key in _MEMORY_CACHE:
        logger.debug(f"Loading boundaries from memory cache: {cache_key}")
        return _MEMORY_CACHE[cache_key].copy()

    cache_file = CACHE_DIR / f"{cache_key}.geojson"

    if use_cache and cache_file.exists():
        logger.info(f"Loading boundaries from disk cache: {cache_file}")
        gdf = gpd.read_file(cache_file)
        _MEMORY_CACHE[cache_key] = gdf
        return gdf.copy()

    logger.info(f"Fetching {iso3} ADM{admin_level} from GeoBoundaries API")

    url = f"{GEOBOUNDARIES_BASE_URL}/{release_type}/{iso3}/ADM{admin_level}"
    logger.debug(f"API URL: {url}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        metadata = response.json()
        download_url = metadata["gjDownloadURL"]
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            raise ValueError(
                f"No boundaries found for {iso3} ADM{admin_level}. "
                "Check ISO3 code and admin level."
            ) from e
        raise RuntimeError(f"Failed to fetch boundary metadata: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to fetch boundary metadata: {e}") from e

    logger.debug(f"Downloading from: {download_url}")
    try:
        gdf = gpd.read_file(download_url)
    except Exception as e:
        raise RuntimeError(f"Failed to download boundary GeoJSON: {e}") from e

    gdf = _ensure_crs(gdf)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _warn_legacy_cache_once()
    logger.info(f"Caching boundaries to: {cache_file}")
    gdf.to_file(cache_file, driver="GeoJSON")
    _MEMORY_CACHE[cache_key] = gdf

    # Return a copy so callers who add columns do not change the cached object.
    return gdf.copy()


def load_boundaries(path: Union[str, Path]) -> gpd.GeoDataFrame:
    """
    Load boundaries from a local file (shapefile, GeoJSON, GeoPackage).

    Parameters
    ----------
    path:
        Path to boundary file. Supported formats:
        - Shapefile (.shp)
        - GeoJSON (.geojson, .json)
        - GeoPackage (.gpkg)
        - Any format supported by geopandas

    Returns
    -------
    gpd.GeoDataFrame
        Boundaries reprojected to EPSG:4326. Columns are returned as-is from
        the source file; callers pass the desired identifier column to
        :func:`evy.zonal_stats` via its ``zone_col`` parameter.

    Raises
    ------
    FileNotFoundError
        If the file does not exist
    ValueError
        If the file cannot be read as geospatial data
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Boundary file not found: {path}")

    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        raise ValueError(f"Failed to read boundary file: {e}") from e

    gdf = _ensure_crs(gdf)

    logger.info(f"Loaded {len(gdf)} boundaries from {path}")
    return gdf


def clear_cache(iso3: str | None = None) -> int:
    """
    Clear cached boundary files (both disk and memory).

    Parameters
    ----------
    iso3:
        If provided, only clear cache for this country.
        If None, clear all cached boundaries.

    Returns
    -------
    int
        Number of files removed
    """
    if iso3:
        iso3_upper = iso3.upper()
        keys_to_remove = [k for k in _MEMORY_CACHE if k.startswith(iso3_upper)]
        for key in keys_to_remove:
            del _MEMORY_CACHE[key]
        pattern = f"{iso3_upper}_*.geojson"
        files = list(CACHE_DIR.glob(pattern))
    else:
        _MEMORY_CACHE.clear()
        files = list(CACHE_DIR.glob("*.geojson"))

    for f in files:
        logger.info(f"Removing cached file: {f}")
        f.unlink()

    logger.info(f"Cleared {len(files)} cached boundary files")
    return len(files)


def _ensure_crs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Ensure GeoDataFrame is in EPSG:4326."""
    if gdf.crs is None:
        logger.warning("No CRS found, assuming EPSG:4326")
        return gdf.set_crs(CRS)
    elif str(gdf.crs) != CRS:
        logger.info(f"Reprojecting from {gdf.crs} to {CRS}")
        return gdf.to_crs(CRS)
    return gdf


def _gdf_to_ee_feature_collection(gdf: gpd.GeoDataFrame):
    """
    Convert GeoDataFrame to Earth Engine FeatureCollection.

    Uses geemap for conversion. Adds a unique boundary ID for reliable
    client-side geometry joining after server-side computation.

    Geometries are simplified before conversion to prevent GEE's 10MB request
    payload limit. Original geometries are preserved in the source GDF for
    client-side joining when include_geometry=True.
    """
    import geemap

    # Add unique boundary ID for client-side geometry joining
    # This allows us to strip geometries server-side and join back later
    if "_evy_boundary_id" not in gdf.columns:
        gdf = gdf.copy()
        gdf["_evy_boundary_id"] = range(len(gdf))

    # Simplify geometries to reduce computation graph size
    # This prevents "Request payload size exceeds 10MB" errors when boundaries
    # have high coordinate density (e.g., complex coastlines, detailed admin boundaries)
    # Tolerance of 0.001 degrees ≈ 111m at equator - safe for MODIS (250m) and
    # Sentinel-2 (10m) since zonal stats use pixel centroids, not exact polygon edges
    simplified = gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(
        tolerance=0.001, preserve_topology=True
    )

    return geemap.geopandas_to_ee(simplified)
