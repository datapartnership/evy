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
    Load MODIS EVI and quality bands from STAC items.

    Parameters
    ----------
    boundaries : gpd.GeoDataFrame
        GeoDataFrame containing zone boundaries, used to determine
        the bounding box for the STAC search.
    start_date : str
        Start date in ISO format (YYYY-MM-DD).
    end_date : str
        End date in ISO format (YYYY-MM-DD).

    Returns
    -------
    xr.Dataset
        Lazy Dataset with 'evi_raw' and 'qa' variables.
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
    Load MODIS land cover band from STAC items. The package currently only supports loading land cover for a single period,
    so the start and end dates are fixed to a single time.

    Parameters
    ----------
    boundaries : gpd.GeoDataFrame
        GeoDataFrame containing the zone boundaries, used to determine the bounding box for loading land cover data.
    ds_evi : xr.Dataset
        Dataset containing the EVI data, used to align the land cover data.

    Returns
    -------
    xr.Dataset
        Lazy Dataset with 'land_cover' variable.
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
