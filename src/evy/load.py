"""Data loading from STAC items via odc-stac."""

import logging
from datetime import datetime, timezone

import requests
import pystac
from shapely.geometry import shape

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


def load_modis(
    boundaries: gpd.GeoDataFrame, start_date: str, end_date: str,
    *, provider: str = "planetary_computer",
):
    """
    Load MODIS EVI and quality bands from Planetary Computer or NASA Earthdata.

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
    provider : str
        'planetary_computer' (default) or 'earthdata' (NASA directly).
        Earthdata requires ``evy[earthdata]`` and Earthdata Login credentials.
        HDF files are downloaded to ``EVY_CACHE_DIR/earthdata`` (or the
        platform evy cache), then cropped pixels are read lazily with pyhdf.

    Returns
    -------
    xr.Dataset
        Lazy Dataset of the composites whose start date falls inside
        ``[start_date, end_date]``, with two variables:

        - ``evi_raw`` : int16 EVI values (scaled ×10000 per MODIS convention)
        - ``qa`` : pixel reliability (0=good, 1=marginal, 2=snow/ice, 3=cloudy)

        Both are indexed by ``(time, y, x)``. Planetary Computer uses chunks
        of ``{x: 2048, y: 2048, time: 1}``; NASA uses one cropped tile window
        per chunk. NASA fill values are converted to NaN without scaling.

    Raises
    ------
    EmptyStacResultError
        If the STAC catalog returns zero items for the requested bbox and
        date range. The message includes the bbox, dates, and collection
        name so the caller can diagnose the query.
    ValueError
        For an unknown provider, or no matching NASA composites.
    RuntimeError
        If NASA authentication fails or a download is incomplete.

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('KEN', admin_level=1)
    >>> ds = evy.load_modis(gdf, '2023-01-01', '2023-12-31')
    >>> ds.evi_raw.sizes
    {'time': 23, 'y': ..., 'x': ...}
    """
    _validate_provider(provider)
    if provider == "earthdata":
        from evy._earthdata import load_modis_earthdata

        return load_modis_earthdata(boundaries, start_date, end_date)

    bbox = boundaries.to_crs(4326).total_bounds
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


def load_landcover(
    boundaries: gpd.GeoDataFrame,
    ds_evi: xr.Dataset | None = None,
    *,
    source: str = "worldcover",
    year: int | None = None,
) -> xr.DataArray:
    """Load land cover from WorldCover or Esri/Impact Observatory.

    ``source="worldcover"`` preserves the static ESA WorldCover mask (class
    40). ``source="esri"`` uses Esri's annual v003 maps for 2017–2025
    (class 5), downloaded from the public Land Cover Explorer assets.
    Missing coverage or unavailable years raise an error; no year is substituted.

    With ``ds_evi``, resample categories by mode to its grid. Esri returns
    dimensions ``(year, y, x)`` for the observation years in that dataset.
    Without ``ds_evi``, Esri requires ``year`` and returns a native 10 m
    raster in the first intersecting tile's UTM CRS. WorldCover also supports
    native 10 m loading. Results cover the boundaries' bounding box and are
    lazy, allowing large native rasters to be exported one year at a time.
    Metadata includes ``crop_class`` and ``landcover_source``.
    """
    if source not in ("worldcover", "esri"):
        raise ValueError("landcover source must be 'worldcover' or 'esri'")
    bbox = boundaries.to_crs(4326).total_bounds
    if source == "esri":
        if ds_evi is None and year is None:
            raise ValueError("year is required for native Esri land cover")
        years = [year] if year is not None else sorted(set(ds_evi.time.dt.year.values))
        if not years or any(y < 2017 or y > 2025 for y in years):
            raise ValueError("Esri land cover supports years 2017–2025 only")
        features = _esri_footprints(bbox)
        if not features:
            raise EmptyStacResultError(
                f"No Esri land cover tiles for bbox={list(bbox)}"
            )
        layers = []
        for y in years:
            items = []
            for feature in features:
                tile = feature["properties"]["ImageName"]
                end = f"{y}1231" if y >= 2024 else f"{y + 1}0101"
                url = (
                    "https://lulctimeseries.blob.core.windows.net/lulctimeseriesv003/"
                    f"lc{y}/{tile}_{y}0101-{end}.tif"
                )
                item = pystac.Item(
                    f"{tile}-{y}",
                    feature["geometry"],
                    list(shape(feature["geometry"]).bounds),
                    datetime(int(y), 1, 1, tzinfo=timezone.utc),
                    {},
                )
                item.add_asset(
                    "data", pystac.Asset(url, media_type=pystac.MediaType.COG)
                )
                items.append(item)
            # Tile names encode UTM zone and latitude band (N and above are north).
            tile = features[0]["properties"]["ImageName"]
            epsg = (32600 if tile[2] >= "N" else 32700) + int(tile[:2])
            grid = (
                {"like": ds_evi}
                if ds_evi is not None
                else {
                    "bbox": bbox,
                    "crs": f"EPSG:{epsg}",
                    "resolution": 10,
                }
            )
            layer = odc_stac.load(
                items,
                bands=["data"],
                chunks={"x": 2048, "y": 2048},
                dtype="uint8",
                nodata=0,
                resampling="mode",
                **grid,
            )["data"].isel(time=0, drop=True)
            layers.append(layer.expand_dims(year=[int(y)]))
        lc = xr.concat(layers, dim="year")
        if ds_evi is None:
            lc = lc.isel(year=0, drop=True)
        crop_class = 5
    else:
        date_range = f"{year}-01-01/{year}-12-31" if year is not None else None
        items = _stac_search(["esa-worldcover"], bbox, date_range)
        if not items:
            raise EmptyStacResultError(
                f"No land cover items found for collection='esa-worldcover', bbox={list(bbox)}"
            )
        grid = {"like": ds_evi} if ds_evi is not None else {"bbox": bbox}
        lc = odc_stac.load(
            items,
            bands=["map"],
            chunks={"x": 2048, "y": 2048, "time": 1},
            patch_url=planetary_computer.sign,
            resampling="mode",
            **grid,
        )["map"].isel(time=0, drop=True)
        crop_class = 40
    if ds_evi is not None:
        # `like` resamples to this grid; keep exact labels for xarray masks.
        lc = lc.assign_coords(x=ds_evi.x, y=ds_evi.y)
    lc = lc.rename("landcover")
    lc.attrs.update(crop_class=crop_class, landcover_source=source)
    return lc


def _esri_footprints(bbox):
    """Query the tile index used by Esri's Land Cover Explorer."""
    features = []
    while True:
        response = requests.get(
            "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
            "S2LULCFootprints/FeatureServer/0/query",
            params={
                "f": "geojson",
                "where": "1=1",
                "outFields": "ImageName",
                "geometry": ",".join(str(v) for v in bbox),
                "geometryType": "esriGeometryEnvelope",
                "inSR": 4326,
                "outSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "resultOffset": len(features),
                "resultRecordCount": 1000,
                "orderByFields": "OBJECTID",
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            raise RuntimeError(f"Esri tile search failed: {result['error']}")
        page = result["features"]
        features.extend(page)
        if len(page) < 1000:
            return features


def _validate_provider(provider: str) -> None:
    if provider not in ("planetary_computer", "earthdata"):
        raise ValueError("provider must be 'planetary_computer' or 'earthdata'")


def load_evi(
    boundaries: gpd.GeoDataFrame,
    start_date: str,
    end_date: str,
    *,
    mask_cropland: bool = True,
    landcover_source: str = "worldcover",
    provider: str = "planetary_computer",
) -> xr.DataArray:
    """Load scaled, quality-filtered MODIS EVI pixels without aggregation.

    Returns lazy ``(time, y, x)`` data at MODIS resolution over the boundary
    bounding box. Optionally mask cropland with WorldCover or annual Esri
    maps. Use :func:`evy.export_geotiff` to save one raster per observation.
    ``provider`` selects 'planetary_computer' (default) or direct NASA
    'earthdata'; land cover still comes from Planetary Computer.
    """
    from evy._process import prepare_evi

    if landcover_source not in ("worldcover", "esri"):
        raise ValueError("landcover_source must be 'worldcover' or 'esri'")
    ds = load_modis(boundaries, start_date, end_date, provider=provider)
    lc = (
        load_landcover(boundaries, ds, source=landcover_source)
        if mask_cropland
        else None
    )
    return prepare_evi(ds, lc)
