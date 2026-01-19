"""MODIS collection definitions and quality masking functions."""

import logging

import pandas as pd
import ee

logger = logging.getLogger(__name__)

MODIS_COLLECTIONS = {
    "terra": "MODIS/061/MOD13Q1",
    "aqua": "MODIS/061/MYD13Q1",
}

SENTINEL2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

DYNAMIC_WORLD_COLLECTION = "GOOGLE/DYNAMICWORLD/V1"
DYNAMIC_WORLD_CROPLAND_VALUE = 4


def list_collections() -> pd.DataFrame:
    """
    List available vegetation index collections.

    Returns
    -------
    pd.DataFrame
        Available collections with columns:
        - 'id': Collection identifier
        - 'name': Human-readable name
        - 'indices': Available indices (evi)
        - 'resolution': Spatial resolution in meters
        - 'temporal': Temporal resolution
        - 'start_date': Data availability start
        - 'end_date': Data availability end
    """
    collections = [
        {
            "id": "MODIS/061/MOD13Q1",
            "name": "Terra MODIS Vegetation Indices",
            "satellite": "Terra",
            "indices": ["evi"],
            "resolution": 250,
            "temporal": "16-day",
            "start_date": "2000-02-18",
            "end_date": "present",
        },
        {
            "id": "MODIS/061/MYD13Q1",
            "name": "Aqua MODIS Vegetation Indices",
            "satellite": "Aqua",
            "indices": ["evi"],
            "resolution": 250,
            "temporal": "16-day",
            "start_date": "2002-07-04",
            "end_date": "present",
        },
        {
            "id": "COPERNICUS/S2_SR_HARMONIZED",
            "name": "Sentinel-2 MSI Surface Reflectance",
            "satellite": "Sentinel-2",
            "indices": ["evi"],
            "resolution": 10,
            "temporal": "5-day",
            "start_date": "2017-03-28",
            "end_date": "present",
        },
    ]
    return pd.DataFrame(collections)


def _bitwise_extract(
    value: ee.Image, from_bit: int, to_bit: int | None = None
) -> ee.Image:
    """
    Extract bits from a binary image.

    Parameters
    ----------
    value: ee.Image
        Input image with binary values
    from_bit:
        Starting bit position (0-indexed)
    to_bit:
        Ending bit position. If None, extracts single bit.

    Returns
    -------
    ee.Image
        Image with extracted bit values
    """
    import ee

    to_bit = from_bit if to_bit is None else to_bit
    mask_size = ee.Number(1).add(to_bit).subtract(from_bit)
    mask = ee.Number(1).leftShift(mask_size).subtract(1)
    return value.rightShift(from_bit).bitwiseAnd(mask)


def _apply_quality_mask(image: ee.Image) -> ee.Image:
    """
    Apply detailed MODIS QA masking.

    Uses both SummaryQA and DetailedQA bands for comprehensive quality control.
    Masks out:
    - Poor quality pixels (SummaryQA > 1 or DetailedQA > 1)
    - Snow/ice pixels (DetailedQA bit 14)

    Parameters
    ----------
    image:
        MODIS image with EVI, SummaryQA, and DetailedQA bands

    Returns
    -------
    ee.Image
        Quality-masked image
    """
    sqa = image.select("SummaryQA")
    dqa = image.select("DetailedQA")

    vi_quality_s = _bitwise_extract(sqa, 0, 1)  # VI quality from SummaryQA
    vi_quality_d = _bitwise_extract(dqa, 0, 1)  # VI quality from DetailedQA
    vi_snow_ice = _bitwise_extract(dqa, 14)  # Snow/ice flag

    # Keep good/marginal quality (0-1), no snow/ice
    mask = vi_quality_s.lte(1).And(vi_quality_d.lte(1)).And(vi_snow_ice.eq(0))

    return image.updateMask(mask)


def _apply_scale_factor(image: ee.Image) -> ee.Image:
    """
    Apply scale factor to MODIS EVI/NDVI values.

    MODIS stores values as integers scaled by 10000.
    This converts to actual values in range [-1, 1].

    Parameters
    ----------
    image:
        MODIS image with scaled values

    Returns
    -------
    ee.Image
        Image with values scaled to actual range
    """
    return image.multiply(0.0001).copyProperties(image, ["system:time_start"])


def _load_modis_collection(
    start_date: str,
    end_date: str,
    region: ee.Geometry | ee.FeatureCollection,
) -> ee.imagecollection:
    """
    Load and merge Terra + Aqua MODIS EVI collection.

    Merges both satellites for effective 8-day temporal resolution.
    Applies quality masking and scale factor.

    Parameters
    ----------
    start_date:
        Start date as ISO string (e.g., '2020-01-01')
    end_date:
        End date as ISO string (e.g., '2020-12-31')
    region:
        Region to filter by

    Returns
    -------
    ee.ImageCollection
        Merged, quality-masked, scaled ImageCollection with EVI band
    """
    band_name = "EVI"

    terra = (
        ee.ImageCollection(MODIS_COLLECTIONS["terra"])
        .filterDate(start_date, end_date)
        .filterBounds(region)
        .select([band_name, "SummaryQA", "DetailedQA"])
    )

    aqua = (
        ee.ImageCollection(MODIS_COLLECTIONS["aqua"])
        .filterDate(start_date, end_date)
        .filterBounds(region)
        .select([band_name, "SummaryQA", "DetailedQA"])
    )

    terra_masked = terra.map(_apply_quality_mask)
    aqua_masked = aqua.map(_apply_quality_mask)
    merged = terra_masked.merge(aqua_masked).sort("system:time_start")

    return merged.select([band_name]).map(_apply_scale_factor)


def _apply_s2_cloud_mask(image: ee.Image) -> ee.Image:
    """
    Apply cloud mask to Sentinel-2 image using Scene Classification Layer.

    Masks out clouds, cloud shadows, and other poor quality pixels.

    Parameters
    ----------
    image:
        Sentinel-2 image with SCL band

    Returns
    -------
    ee.Image
        Cloud-masked image
    """
    scl = image.select("SCL")

    # SCL classes to mask out:
    # 3 = Cloud shadows
    # 7 = Unclassified (often clouds)
    # 8 = Cloud medium probability
    # 9 = Cloud high probability
    # 10 = Thin cirrus
    cloud_mask = (
        scl.neq(3).And(scl.neq(7)).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    )

    return image.updateMask(cloud_mask)


def _calculate_s2_evi(image: ee.Image) -> ee.Image:
    """
    Calculate EVI from Sentinel-2 bands.

    EVI = 2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))

    Parameters
    ----------
    image:
        Sentinel-2 image with B2, B4, B8 bands (scaled to reflectance)

    Returns
    -------
    ee.Image
        Image with EVI band
    """
    nir = image.select("B8")
    red = image.select("B4")
    blue = image.select("B2")

    evi = (
        nir.subtract(red)
        .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(10000))
        .multiply(2.5)
        .rename("EVI")
    )

    return evi.copyProperties(image, ["system:time_start"])


def _mask_and_calculate_s2_evi(image: ee.Image) -> ee.Image:
    """
    Apply cloud mask and calculate EVI in a single operation.

    Combines cloud masking and EVI calculation to avoid iterating
    over the collection twice.

    Parameters
    ----------
    image:
        Sentinel-2 image with B2, B4, B8, SCL bands

    Returns
    -------
    ee.Image
        Cloud-masked image with EVI band
    """

    masked = _apply_s2_cloud_mask(image)
    evi = _calculate_s2_evi(masked)

    return evi.copyProperties(image, ["system:time_start"])


def _load_sentinel2_collection(
    start_date: str, end_date: str, region: ee.Geometry | ee.FeatureCollection
) -> ee.ImageCollection:
    """
    Load Sentinel-2 collection and compute EVI.

    Applies cloud masking and computes EVI from surface reflectance bands.

    Parameters
    ----------
    start_date:
        Start date as ISO string (e.g., '2020-01-01')
    end_date:
        End date as ISO string (e.g., '2020-12-31')
    region:
        Region to filter by

    Returns
    -------
    ee.ImageCollection
        Cloud-masked ImageCollection with EVI band
    """
    s2 = (
        ee.ImageCollection(SENTINEL2_COLLECTION)
        .filterDate(start_date, end_date)
        .filterBounds(region)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 50))
        .select(["B2", "B4", "B8", "SCL"])
    )

    return s2.map(_mask_and_calculate_s2_evi).sort("system:time_start")


def _build_yearly_cropland_masks(
    years: ee.List, region: ee.Geometry | ee.FeatureCollection
) -> ee.Dictionary:
    """
    Pre-compute cropland masks for a list of years.

    Creates an ee.Dictionary mapping year -> cropland mask for efficient
    server-side lookup. This avoids recomputing the Dynamic World mode
    for each image in the collection.

    Parameters
    ----------
    years:
        List of years (as ee.Number) to compute masks for
    region:
        Region to filter by

    Returns
    -------
    ee.Dictionary
        Dictionary mapping year (as string) to binary cropland mask
    """

    def compute_yearly_mask(year):
        """Compute cropland mask for a single year."""
        year = ee.Number(year)

        # Dynamic World starts 2015
        mask_year = year.max(2015)

        yearly_start = ee.Date.fromYMD(mask_year, 1, 1)
        yearly_end = ee.Date.fromYMD(mask_year, 12, 31)

        yearly_lc = (
            ee.ImageCollection(DYNAMIC_WORLD_COLLECTION)
            .filterDate(yearly_start, yearly_end)
            .filterBounds(region)
            .select("label")
            .reduce(ee.Reducer.mode())
        )

        cropland_mask = yearly_lc.eq(DYNAMIC_WORLD_CROPLAND_VALUE)
        return ee.List([year.format("%d"), cropland_mask])

    # Build list of [year, mask] pairs and convert to dictionary
    mask_pairs = years.map(compute_yearly_mask).flatten()
    return ee.Dictionary(mask_pairs)


def apply_cropland_mask(
    ic: ee.ImageCollection, region: ee.Geometry | ee.FeatureCollection
) -> ee.ImageCollection:
    """
    Apply yearly cropland masks to an ImageCollection efficiently.

    Pre-computes masks for all unique years in the collection, then
    applies them via dictionary lookup. This is much more efficient
    than computing the mask separately for each image.

    Parameters
    ----------
    ic:
        Input ImageCollection
    region:
        Region for cropland mask

    Returns
    -------
    ee.ImageCollection
        Masked ImageCollection
    """
    years = ic.aggregate_array("system:time_start").map(
        lambda ts: ee.Date(ts).get("year")
    )
    unique_years = years.distinct()

    mask_dict = _build_yearly_cropland_masks(unique_years, region)

    def apply_mask(image):
        year = ee.Date(image.get("system:time_start")).get("year")
        mask = ee.Image(mask_dict.get(year.format("%d")))
        return image.updateMask(mask)

    return ic.map(apply_mask)
