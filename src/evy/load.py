"""Data loading from STAC items via odc-stac."""

import logging

import planetary_computer
from odc import stac as odc_stac
import pystac_client
import xarray as xr
import geopandas as gpd


logger = logging.getLogger(__name__)


def load_modis(boundaries: gpd.GeoDataFrame, start_date: str, end_date: str):
    """
    Load MODIS EVI and quality bands from a STAC catalog.

    Searches the Microsoft Planetary Computer STAC endpoint for MOD13Q1
    (MODIS Terra 16-day, 250m) items intersecting the boundary bounding
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
        Lazy Dataset with two variables:

        - ``evi_raw`` : int16 EVI values (scaled ×10000 per MODIS convention)
        - ``qa`` : pixel reliability (0=good, 1=marginal, 2=snow/ice, 3=cloudy)

        Both are indexed by ``(time, y, x)`` with chunks of ``{x: 2048,
        y: 2048, time: 1}``.

    Raises
    ------
    RuntimeError
        If the STAC catalog is unreachable or returns no items for the
        requested bbox and date range.

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('KEN', admin_level=1)
    >>> ds = evy.load_modis(gdf, '2023-01-01', '2023-12-31')
    >>> ds.evi_raw.sizes
    {'time': 23, 'y': ..., 'x': ...}
    """

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
    )

    bbox = boundaries.total_bounds

    search = catalog.search(
        collections=["modis-13Q1-061"],
        bbox=bbox,
        datetime=f"{start_date}/{end_date}",
    )

    logger.info(
        f"Found {search.matched()} MODIS items for bounding box {bbox} and date range {start_date} to {end_date}."
    )
    ds = odc_stac.load(
        search.items(),
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

    return ds


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

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('KEN', admin_level=1)
    >>> ds = evy.load_modis(gdf, '2023-01-01', '2023-12-31')
    >>> lc = evy.load_landcover(gdf, ds)
    >>> cropland_mask = (lc == 40)
    """
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
    )

    search = catalog.search(
        collections=["esa-worldcover"],
        bbox=boundaries.total_bounds,
    )

    logger.info(
        f"Found {search.matched()} land cover items for bounding box {boundaries.total_bounds}."
    )
    wc = odc_stac.load(
        search.items(),
        bands=["map"],
        like=ds_evi,
        chunks={"x": 2048, "y": 2048, "time": 1},
        patch_url=planetary_computer.sign,
        resampling="mode",
    )

    lc = wc["map"].isel(time=0).compute()

    return lc
