"""Lazy MODIS EVI/QA windows from NASA LAADS OPeNDAP."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import BoundedSemaphore, Lock
from time import sleep
import warnings

import dask.array as da
from dask import delayed
import numpy as np
import rasterio
from rasterio.errors import NotGeoreferencedWarning
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
import requests
import xarray as xr

from evy._earthdata import _CRS, _FILENAME, _TILE_SIZE, _find_modis_tiles
from evy.cache import _cache_base


# MOD13Q1/MYD13Q1 v061 have 4800 pixels per sinusoidal tile axis.
_PIXELS = 4800
_BANDS = {"evi_raw": "_250m_16_days_EVI", "qa": "_250m_16_days_pixel_reliability"}
_TRANSFERS = BoundedSemaphore(4)
_NETCDF_LOCK = Lock()
_SIGNATURE = b"\x89HDF\r\n\x1a\n"


def _decode_subset(content, shape):
    """Validate both raw bands; GDAL applies nodata masking but not scale tags."""
    if not content.startswith(_SIGNATURE):
        raise ValueError("LAADS did not return a NetCDF4 subset")
    bands = {}
    # GDAL's NetCDF/HDF libraries can have process-wide state; keep reads serial.
    with (
        _NETCDF_LOCK,
        warnings.catch_warnings(),
        rasterio.Env(GDAL_NETCDF_BOTTOMUP="NO"),
    ):
        # Coordinate arrays are omitted; the caller sets the native grid.
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with MemoryFile(content) as memory, memory.open() as container:
            for subdataset in container.subdatasets:
                for key, name in _BANDS.items():
                    if subdataset.rsplit("/", 1)[-1] != name:
                        continue
                    if key in bands:
                        raise ValueError(f"Duplicate LAADS band: {name}")
                    with rasterio.open(subdataset) as source:
                        if source.shape != shape or source.count != 1:
                            raise ValueError("Unexpected LAADS subset dimensions")
                        if not np.issubdtype(np.dtype(source.dtypes[0]), np.integer):
                            raise ValueError(
                                "LAADS subset must contain unscaled integer bands"
                            )
                        bands[key] = (
                            source.read(1, masked=True).astype("float32").filled(np.nan)
                        )
    if set(bands) != set(_BANDS):
        raise ValueError("LAADS subset is missing EVI or pixel reliability")
    return np.stack([bands[key] for key in _BANDS])


def _read_subset(name, window, cache, headers, cookies):
    """Fetch/cache one validated window, sharing a single task across both bands."""
    row0, row1, col0, col1 = window
    shape = (row1 - row0, col1 - col0)
    path = cache / f"{Path(name).stem}.{row0}-{row1}.{col0}-{col1}.nc4"
    if path.exists():
        return _decode_subset(path.read_bytes(), shape)

    match = _FILENAME.fullmatch(name)
    product, day = match[1], match[2]
    url = (
        "https://ladsweb.modaps.eosdis.nasa.gov/opendap/RemoteResources/laads/"
        f"allData/61/{product}/{day[:4]}/{day[4:]}/{name}.dap.nc4"
    )
    constraint = ";".join(
        f"/{band}[{row0}:1:{row1 - 1}][{col0}:1:{col1 - 1}]" for band in _BANDS.values()
    )
    with _TRANSFERS, requests.Session() as session:
        session.headers.update(headers)
        session.cookies.update(cookies)
        for attempt in range(3):
            try:
                response = session.get(
                    url, params={"dap4.ce": constraint}, timeout=(15, 120)
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 2:
                    raise RuntimeError(
                        f"LAADS request failed for {name}; retry the request"
                    ) from None
            except requests.RequestException:
                # Server errors and redirect URLs can embed credentials. Don't echo them.
                raise RuntimeError(
                    f"LAADS request failed for {name}; retry the request"
                ) from None
            else:
                if (
                    response.status_code not in (429, 500, 502, 503, 504)
                    or attempt == 2
                ):
                    break
            sleep(2**attempt)
        if response.status_code != 200:
            raise RuntimeError(
                f"LAADS returned HTTP {response.status_code} for {name}. "
                "Check Earthdata authorization and retry; no provider was substituted."
            )
        data = _decode_subset(response.content, shape)
        cache.mkdir(parents=True, exist_ok=True)
        staging = None
        try:
            with NamedTemporaryFile(dir=cache, delete=False) as file:
                staging = Path(file.name)
                file.write(response.content)
            staging.replace(path)
        finally:
            if staging is not None:
                staging.unlink(missing_ok=True)
    return data


def load_modis_laads(boundaries, start_date, end_date):
    """Discover both satellites now; fetch only their native pixel windows on compute."""
    with rasterio.Env() as env:
        if "netCDF" not in env.drivers():
            raise ImportError(
                "LAADS requires a rasterio/GDAL build with the NetCDF driver"
            )
    selected, bounds = _find_modis_tiles(boundaries, start_date, end_date)
    import earthaccess

    session = earthaccess.get_requests_https_session()
    cache = _cache_base() / "laads"
    pixel = _TILE_SIZE / _PIXELS
    xmin, ymin, xmax, ymax = bounds
    by_date = {}
    for name, date, _ in sorted(selected.values(), key=lambda item: item[0]):
        match = _FILENAME.fullmatch(name)
        h, v = int(match[3][1:3]), int(match[3][4:6])
        left, top = (h - 18) * _TILE_SIZE, (9 - v) * _TILE_SIZE
        col0 = max(0, int(np.floor((xmin - left) / pixel)))
        col1 = min(_PIXELS, int(np.ceil((xmax - left) / pixel)))
        row0 = max(0, int(np.floor((top - ymax) / pixel)))
        row1 = min(_PIXELS, int(np.ceil((top - ymin) / pixel)))
        if col0 >= col1 or row0 >= row1:
            continue
        data = da.from_delayed(
            delayed(_read_subset)(
                name,
                (row0, row1, col0, col1),
                cache,
                dict(session.headers),
                session.cookies.copy(),
            ),
            shape=(2, row1 - row0, col1 - col0),
            dtype="float32",
        )
        tile = (
            xr.Dataset(
                {key: (("y", "x"), data[i]) for i, key in enumerate(_BANDS)},
                coords={
                    "x": left + (np.arange(col0, col1) + 0.5) * pixel,
                    "y": top - (np.arange(row0, row1) + 0.5) * pixel,
                },
            )
            .expand_dims(time=[date])
            .rio.write_crs(_CRS)
            .rio.write_transform(
                from_origin(left + col0 * pixel, top - row0 * pixel, pixel, pixel)
            )
        )
        by_date.setdefault(date, []).append(tile)
    if not by_date:
        raise ValueError("NASA MODIS tiles do not intersect the requested bounding box")
    mosaics = [
        xr.combine_by_coords(tiles, combine_attrs="override", join="outer")
        for _, tiles in sorted(by_date.items())
    ]
    return (
        xr.concat(mosaics, dim="time", join="outer").sortby("time").rio.write_crs(_CRS)
    )
