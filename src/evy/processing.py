import logging

import xarray as xr
from rasterio.enums import Resampling

logger = logging.getLogger(__name__)
xr.set_options(keep_attrs=True)


def mask_evi_by_quality(ds: xr.Dataset, confidence_threshold: int = 0) -> xr.Dataset:
    """
    Mask EVI data using VI Quality band for high confidence pixels.

    Args:
        ds: xarray Dataset containing EVI and quality bands
        confidence_threshold: Quality threshold (0=good, 1=marginal, 2-3=poor)

    Returns:
        xarray Dataset with masked EVI data
    """
    vi_quality = ds["250m_16_days_VI_Quality"]
    pixel_reliability = ds["250m_16_days_pixel_reliability"]
    evi = ds["250m_16_days_EVI"]

    # Lower digit in VI Quality means higher confidence
    # We use number 3 because it is the first two bits (11 in binary)
    vi_quality_mask = (vi_quality.astype(int) & 3) <= confidence_threshold
    reliability_mask = pixel_reliability.astype(int) <= confidence_threshold

    combined_mask = vi_quality_mask & reliability_mask
    evi_masked = evi.where(combined_mask)

    # Update the dataset with the masked EVI data
    ds = ds.copy()
    ds["250m_16_days_EVI"] = evi_masked
    return ds


def mask_evi_by_cropland(evi: xr.DataArray, land_cover: xr.DataArray) -> xr.DataArray:
    """
    Mask EVI data to include only cropland areas based on land cover classification.

    Args:
        evi: xarray DataArray containing EVI data
        land_cover: xarray DataArray with land cover classification

    Returns:
        xarray Dataset with masked EVI data
    """
    crop_classes = [v for k, v in land_cover.class_names.items() if "crop" in k.lower()]

    # Upsample land cover from 10m to match EVI resolution (250m)
    land_cover = land_cover.rio.reproject_match(
        evi,
        resampling=Resampling.mode,
    )

    crop_mask = land_cover.isin(crop_classes)
    return evi.where(crop_mask)
