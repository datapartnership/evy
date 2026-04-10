"""Pure data transformation functions for local EVI computation pipeline.

All functions are side-effect-free: they take xarray objects in and return
xarray objects out, with no I/O or external state.
"""

import xarray as xr

EVI_SCALE_FACTOR = 0.0001
EVI_VALID_MIN = -0.2
EVI_VALID_MAX = 1.0
CROP_CLASSES = [40]


def apply_quality_mask(ds: xr.Dataset) -> xr.DataArray:
    """Mask EVI pixels where quality is poor.

    Keeps pixels where ``qa <= 1`` (good + marginal quality). All other
    pixels are set to NaN.

    Parameters
    ----------
    ds : xr.Dataset
        Dataset containing ``evi_raw`` and ``qa`` variables with matching
        dimensions ``(time, y, x)``.

    Returns
    -------
    xr.DataArray
        Masked ``evi_raw`` values; bad-quality pixels replaced with NaN.
    """
    return ds["evi_raw"].where(ds["qa"] <= 1)


def scale_evi(evi: xr.DataArray) -> xr.DataArray:
    """Apply MODIS scale factor and clip to valid physical range.

    Multiplies raw integer EVI values by ``EVI_SCALE_FACTOR`` (0.0001) and
    clips the result to ``[EVI_VALID_MIN, EVI_VALID_MAX]`` ([-0.2, 1.0]).
    NaN values are preserved.

    Parameters
    ----------
    evi : xr.DataArray
        Raw (unscaled) EVI values.

    Returns
    -------
    xr.DataArray
        Scaled and clipped EVI values.
    """
    scaled = evi * EVI_SCALE_FACTOR
    return scaled.clip(min=EVI_VALID_MIN, max=EVI_VALID_MAX)


def apply_cropland_mask(evi: xr.DataArray, land_cover: xr.DataArray) -> xr.DataArray:
    """Mask non-cropland pixels.

    Retains only pixels whose ``land_cover`` class is in ``CROP_CLASSES``
    (ESA WorldCover class 40 = cropland). All other pixels are set to NaN.

    Parameters
    ----------
    evi : xr.DataArray
        EVI values to be filtered.
    land_cover : xr.DataArray
        Land cover classification raster with integer class codes.

    Returns
    -------
    xr.DataArray
        EVI values with non-cropland pixels set to NaN.
    """
    cropland_mask = land_cover.isin(CROP_CLASSES)
    return evi.where(cropland_mask)


def aggregate_temporal(evi: xr.DataArray, freq: str) -> xr.DataArray:
    """Resample EVI to a coarser temporal frequency using the median.

    Parameters
    ----------
    evi : xr.DataArray
        EVI time series with a ``time`` dimension.
    freq : str
        Pandas-compatible resample frequency string (e.g. ``"ME"`` for
        month-end, ``"QE"`` for quarter-end, ``"YE"`` for year-end). Pass
        ``"Original"`` to skip resampling and return ``evi`` unchanged.

    Returns
    -------
    xr.DataArray
        Temporally aggregated EVI. When ``freq="Original"``, the input is
        returned without modification.
    """
    if freq == "Original":
        return evi
    return evi.resample(time=freq).median()
