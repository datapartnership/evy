"""Data loading from STAC items via odc-stac."""

import logging

import planetary_computer
from odc import stac as odc_stac
import pystac_client
from pystac_client.exceptions import APIError
import xarray as xr
import geopandas as gpd
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


logger = logging.getLogger(__name__)

_PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Retry failed pixel reads (GDAL_HTTP_MAX_RETRY=10, 0.5 s delay) instead of
# aborting the whole analysis on one flaky tile. Runs once at import, so a
# later odc.stac.configure_rio() call by the user still takes precedence.
odc_stac.configure_rio(cloud_defaults=True)


class EmptyStacResultError(RuntimeError):
    """Raised when a STAC search returns zero items for the given query."""


def _is_transient(exc: BaseException) -> bool:
    """True for STAC errors worth retrying.

    pystac-client wraps every network failure in ``APIError``. Retry when there
    is no HTTP status (connection error, timeout), on 429, or on a 5xx; do not
    retry other 4xx errors, which will fail the same way again.
    """
    if not isinstance(exc, APIError):
        return False
    status = getattr(exc, "status_code", None)
    return status is None or status == 429 or status >= 500


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(_is_transient),
    reraise=True,
)
def _stac_search(collections: list[str], bbox, datetime_range: str | None = None):
    """Open the Planetary Computer STAC catalog and run a search with retries.

    Returns the materialized list of items. Retries up to 3 times on transient
    network failures with exponential backoff (1-8s).
    """
    catalog = pystac_client.Client.open(_PC_STAC_URL)
    kwargs: dict = {"collections": collections, "bbox": bbox}
    if datetime_range is not None:
        kwargs["datetime"] = datetime_range
    search = catalog.search(**kwargs)
    return list(search.items())


def load_modis(boundaries: gpd.GeoDataFrame, start_date: str, end_date: str):
    """
    Load MODIS EVI and quality bands from a STAC catalog.

    Searches the Microsoft Planetary Computer STAC endpoint for MOD13Q1 and
    MYD13Q1 (MODIS Terra and Aqua 16-day, 250m) items intersecting the boundary bounding
    box and opens them lazily via ``odc-stac``. The returned Dataset is
    Dask-backed; no pixels are materialized until you call ``.compute()``
    or reduce over the data.

    Parameters
    ----------
    boundaries : gpd.GeoDataFrame
        Zone boundaries used to derive the STAC search bounding box. Any
        CRS is accepted; only the total bounds are used.
    start_date : str
        Inclusive start date as an ISO string (YYYY-MM-DD).
    end_date : str
        Inclusive end date as an ISO string (YYYY-MM-DD).

    Returns
    -------
    xr.Dataset
        Lazy Dataset of the composites whose start date falls inside
        ``[start_date, end_date]``, with two variables:

        - ``evi_raw`` : int16 EVI values (scaled ×10000 per MODIS convention)
        - ``qa`` : pixel reliability (0=good, 1=marginal, 2=snow/ice, 3=cloudy)

        Both are indexed by ``(time, y, x)`` with chunks of ``{x: 2048,
        y: 2048, time: 1}``.

    Raises
    ------
    EmptyStacResultError
        If the STAC catalog returns zero items for the requested bbox and
        date range. The message includes the bbox, dates, and collection
        name so the caller can diagnose the query.

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('KEN', admin_level=1)
    >>> ds = evy.load_modis(gdf, '2023-01-01', '2023-12-31')
    >>> ds.evi_raw.sizes
    {'time': 23, 'y': ..., 'x': ...}
    """
    bbox = boundaries.total_bounds
    datetime_range = f"{start_date}/{end_date}"
    collection = "modis-13Q1-061"

    items = _stac_search([collection], bbox, datetime_range)

    if not items:
        raise EmptyStacResultError(
            f"No MODIS items found for collection='{collection}', "
            f"bbox={list(bbox)}, dates={datetime_range}. "
            "Check that the date range is non-empty and the boundary "
            "intersects MODIS coverage."
        )

    logger.info(
        f"Found {len(items)} MODIS items for bounding box {bbox} and date range {start_date} to {end_date}."
    )
    ds = odc_stac.load(
        items,
        bands=["250m_16_days_EVI", "250m_16_days_pixel_reliability"],
        bbox=bbox,
        chunks={"x": 2048, "y": 2048, "time": 1},
        patch_url=planetary_computer.sign,
        dtype="float32",
    )

    ds = ds.rename(
        {
            "250m_16_days_EVI": "evi_raw",
            "250m_16_days_pixel_reliability": "qa",
        }
    )

    # STAC matches any 16-day composite that *overlaps* the range, so a
    # composite starting before start_date can be returned. Keep only
    # composites that start inside the range, as the GEE backend does.
    return ds.sel(time=slice(start_date, end_date))


def load_landcover(boundaries: gpd.GeoDataFrame, ds_evi: xr.Dataset):
    """
    Load an ESA WorldCover land cover raster aligned to an EVI dataset.

    Searches the Microsoft Planetary Computer STAC endpoint for the
    ``esa-worldcover`` collection over the boundary bounding box and
    reprojects the result to match the grid of ``ds_evi`` using nearest-
    neighbor (mode) resampling. Only a single timestep is loaded, because
    WorldCover is a static (annual) product.

    Parameters
    ----------
    boundaries : gpd.GeoDataFrame
        Zone boundaries used to derive the STAC search bounding box.
    ds_evi : xr.Dataset
        An EVI Dataset (typically from :func:`load_modis`) whose grid the
        land cover layer should be aligned to.

    Returns
    -------
    xr.DataArray
        Eager (computed) DataArray of WorldCover class codes, indexed by
        ``(y, x)``. Class code 40 is cropland; see the ESA WorldCover
        documentation for the full legend.

    Raises
    ------
    EmptyStacResultError
        If the STAC catalog returns zero ``esa-worldcover`` items for the
        requested bbox.

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('KEN', admin_level=1)
    >>> ds = evy.load_modis(gdf, '2023-01-01', '2023-12-31')
    >>> lc = evy.load_landcover(gdf, ds)
    >>> cropland_mask = (lc == 40)
    """
    bbox = boundaries.total_bounds
    collection = "esa-worldcover"

    items = _stac_search([collection], bbox)

    if not items:
        raise EmptyStacResultError(
            f"No land cover items found for collection='{collection}', "
            f"bbox={list(bbox)}. Check that the boundary intersects ESA "
            "WorldCover coverage."
        )

    logger.info(f"Found {len(items)} land cover items for bounding box {bbox}.")
    wc = odc_stac.load(
        items,
        bands=["map"],
        like=ds_evi,
        chunks={"x": 2048, "y": 2048, "time": 1},
        patch_url=planetary_computer.sign,
        resampling="mode",
    )

    lc = wc["map"].isel(time=0).compute()

    return lc
