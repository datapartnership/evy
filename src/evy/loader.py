import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import planetary_computer
import pystac_client
import requests
import stackstac
import xarray as xr

from evy.processing import mask_evi_by_quality

logger = logging.getLogger(__name__)
xr.set_options(keep_attrs=True)


def fetch_boundaries(
    iso3_code: str,
    adm_level: int = 0,
    release_type: str = "gbOpen",
    output_dir: str | Path = "data/boundaries",
) -> gpd.GeoDataFrame:
    """
    Fetch administrative boundaries from GeoBoundaries API.

    Args:
        iso3_code: ISO3 code of the country.
        adm_level: Administrative level (1, 2, etc.).
        release_type: Release type (e.g., gbOpen, gbHumanitarian, gbAuthoritative).
        output_dir: Directory to save the downloaded GeoJSON file.

    Returns:
        A GeoDataFrame containing the boundaries.

    """
    cache_dir = Path(output_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{iso3_code}_ADM{adm_level}_{release_type}.geojson"

    if cache_file.exists():
        logger.debug(f"Loading boundaries from cache: {cache_file}")
        return gpd.read_file(cache_file)

    url = f"https://www.geoboundaries.org/api/current/{release_type}/{iso3_code}/ADM{adm_level}"
    logger.debug(f"Fetching boundaries from API: {url}")
    response = requests.get(url)
    response.raise_for_status()
    download_url = response.json()["gjDownloadURL"]
    logger.debug(f"Downloading GeoJSON from: {download_url}")
    gdf = gpd.read_file(download_url)
    gdf.to_file(cache_file, driver="GeoJSON")
    return gdf


def open_evi(
    product: str = "MOD13Q1",
    bbox: tuple | None = None,
    date_range: tuple | None = None,
    collections: list[str] | None = None,
    assets: list[str] | None = None,
    mask_quality: bool = True,
    **kwargs,
) -> xr.DataArray:
    """
    Open MODIS EVI data following xarray conventions.

    Args:
        product: MODIS product name (e.g., 'MOD13Q1')
        bbox: Bounding box as (lon_min, lat_min, lon_max, lat_max)
        date_range: Date range as (start_date, end_date)
        collections: STAC collection IDs to search
        assets: Asset names to load
        mask_quality: Whether to apply quality masking
        **kwargs: Additional arguments for quality masking

    Returns:
        EVIData with MODIS EVI data
    """
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    if date_range is None:
        date_range = ("2024-01-01", "2024-01-01")

    start_date, end_date = date_range
    time_range = f"{start_date}/{end_date}"

    if collections is None:
        if product == "MOD13Q1":
            collections = ["modis-13Q1-061"]
        else:
            collections = [product]

    if assets is None:
        assets = [
            "250m_16_days_EVI",
            "250m_16_days_VI_Quality",
            "250m_16_days_pixel_reliability",
        ]

    search_kwargs = {"collections": collections, "datetime": time_range}

    if bbox is not None:
        search_kwargs["bbox"] = bbox

    search = catalog.search(**search_kwargs)
    items = search.item_collection()

    stacked = (
        stackstac.stack(items, epsg=4326, bounds_latlon=bbox, assets=assets)
        .assign_coords(
            {
                "time": lambda ds: pd.to_datetime(
                    ds.start_datetime, format="ISO8601"
                ).tz_localize(None)
            }
        )
        .sortby("time")
        .sel(time=slice(start_date, end_date))
    )

    ds = stacked.to_dataset(dim="band")

    for var in ds.data_vars:
        ds[var].attrs.update(stacked.sel(band=var).attrs)

    if mask_quality:
        confidence_threshold = kwargs.get("confidence_threshold", 0)
        ds = mask_evi_by_quality(ds, confidence_threshold=confidence_threshold)
    ds = ds.rename_vars({"250m_16_days_EVI": "evi"})

    return ds["evi"]


def load_land_cover(
    collection: str = "io-lulc-annual-v02",
    bbox: tuple | None = None,
    date_range: tuple | None = None,
) -> xr.DataArray:
    """
    Load land use/land cover classification data.

    Args:
        collections: STAC collection IDs to search
        bbox: Bounding box as (lon_min, lat_min, lon_max, lat_max)
        date_range: Date range as (start_date, end_date)
        add_class_names: Whether to add class names as attributes (loaded from collection metadata)

    Returns:
        Land use/land cover classification data as an xarray DataArray.
        If add_class_names=True, class names will be available in .attrs['class_names']

    Notes:
        Class names are dynamically loaded from the STAC collection metadata.
        For io-lulc-annual-v02 collection, this typically includes classes like:
        Water, Trees, Crops, Built area, Bare ground, etc.
    """
    if date_range is None:
        date_range = ("2024-01-01", "2024-01-01")

    start_date, end_date = date_range
    time_range = f"{start_date}/{end_date}"

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    search_kwargs = {"collections": [collection], "datetime": time_range}

    if bbox is not None:
        search_kwargs["bbox"] = bbox

    search = catalog.search(**search_kwargs)
    items = search.item_collection()

    ds = (
        stackstac.stack(items, epsg=4326, bounds_latlon=bbox)
        .assign_coords(
            time=pd.to_datetime([item.properties["start_datetime"] for item in items])
            .tz_convert(None)
            .to_numpy()
        )
        .sortby("time")
        # Get the most recent observation only
        .pipe(stackstac.mosaic)
        # And drop the band dimension since there's only one band
        .squeeze()
    )

    land_collection = catalog.get_collection(collection)
    x = land_collection.item_assets["data"]
    class_names = {x["summary"]: x["values"][0] for x in x.properties["file:values"]}
    # values_to_classes = {v: k for k, v in class_names.items()}
    ds.attrs["class_names"] = class_names

    return ds
