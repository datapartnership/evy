"""Direct NASA MOD13Q1/MYD13Q1 downloads, normalized to the local pipeline."""

from datetime import datetime
from pathlib import Path
import os
import re
from tempfile import TemporaryDirectory
from threading import Lock
from urllib.parse import urlparse

import dask.array as da
from dask import delayed
import numpy as np
import pandas as pd
from pyproj import Transformer
from rasterio.transform import from_origin
import rioxarray  # noqa: F401
import xarray as xr

from evy.cache import _cache_base


_CRS = "+proj=sinu +R=6371007.181 +nadgrids=@null +wktext"
_TILE_SIZE = 1111950.5196666667
_BANDS = {"evi_raw": "250m 16 days EVI", "qa": "250m 16 days pixel reliability"}
_FILENAME = re.compile(r"(M[OY]D13Q1)\.A(\d{7})\.(h\d{2}v\d{2})\.061\.(\d{13})\.hdf")
# HDF4's C library is not thread safe; Dask still schedules other work normally.
_HDF_LOCK = Lock()


def _read_band(path, name, start, count):
    from pyhdf.SD import SD

    with _HDF_LOCK:
        hdf = SD(str(path))
        try:
            band = hdf.select(name)
            try:
                data = band.get(start=start, count=count).astype("float32")
                fill = band.attributes().get("_FillValue")
                if fill is not None:
                    data[data == fill] = np.nan
                return data
            finally:
                band.endaccess()
        finally:
            hdf.end()


def _open_tile(path, date, bounds):
    """Read grid metadata now and only the requested pixel window on compute."""
    from pyhdf.SD import SD

    with _HDF_LOCK:
        hdf = SD(str(path))
        try:
            metadata = hdf.attributes()["StructMetadata.0"]
            if "Projection=GCTP_SNSOID" not in metadata:
                raise ValueError(f"Unsupported MODIS projection in {path.name}")
            nx = int(re.search(r"XDim=(\d+)", metadata)[1])
            ny = int(re.search(r"YDim=(\d+)", metadata)[1])
            left, top = map(
                float,
                re.search(r"UpperLeftPointMtrs=\(([^)]+)\)", metadata)[1].split(","),
            )
            right, bottom = map(
                float, re.search(r"LowerRightMtrs=\(([^)]+)\)", metadata)[1].split(",")
            )
            for name in _BANDS.values():
                if hdf.datasets()[name][1] != (ny, nx):
                    raise ValueError(f"Unexpected MODIS band dimensions in {path.name}")
        finally:
            hdf.end()

    dx, dy = (right - left) / nx, (top - bottom) / ny
    xmin, ymin, xmax, ymax = bounds
    col0, col1 = (
        max(0, int(np.floor((xmin - left) / dx))),
        min(nx, int(np.ceil((xmax - left) / dx))),
    )
    row0, row1 = (
        max(0, int(np.floor((top - ymax) / dy))),
        min(ny, int(np.ceil((top - ymin) / dy))),
    )
    if col0 >= col1 or row0 >= row1:
        return None

    count = (row1 - row0, col1 - col0)
    variables = {
        key: (
            ("y", "x"),
            da.from_delayed(
                delayed(_read_band)(path, name, (row0, col0), count),
                shape=count,
                dtype="float32",
            ),
        )
        for key, name in _BANDS.items()
    }
    ds = xr.Dataset(
        variables,
        coords={
            "x": left + (np.arange(col0, col1) + 0.5) * dx,
            "y": top - (np.arange(row0, row1) + 0.5) * dy,
        },
    )
    return (
        ds.expand_dims(time=[date])
        .rio.write_crs(_CRS)
        .rio.write_transform(from_origin(left + col0 * dx, top - row0 * dy, dx, dy))
    )


def load_modis_earthdata(boundaries, start_date, end_date):
    """Search both satellites, atomically cache HDF files, and mosaic by date."""
    try:
        import earthaccess
        import pyhdf.SD  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Direct NASA access requires: pip install 'evy[earthdata]'"
        ) from exc

    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError(
            "start_date and end_date must be valid dates with start_date <= end_date"
        )
    if start.tzinfo is not None or end.tzinfo is not None:
        raise ValueError("Use timezone-naive dates (YYYY-MM-DD)")
    bbox = tuple(boundaries.to_crs(4326).total_bounds)
    if not np.isfinite(bbox).all() or boundaries.empty:
        raise ValueError("boundaries must have finite, non-empty bounds")
    if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        raise ValueError("boundaries must have a non-zero bounding box")

    # Never start an interactive password prompt inside a library call.
    strategy = (
        "environment"
        if os.getenv("EARTHDATA_TOKEN") or os.getenv("EARTHDATA_USERNAME")
        else "netrc"
    )
    from earthaccess.exceptions import LoginAttemptFailure, LoginStrategyUnavailable

    try:
        auth = earthaccess.login(strategy=strategy)
    except (LoginAttemptFailure, LoginStrategyUnavailable) as exc:
        raise RuntimeError(
            "NASA Earthdata login failed. Configure Earthdata credentials or call earthaccess.login(persist=True)."
        ) from exc
    if not auth.authenticated:
        raise RuntimeError(
            "NASA Earthdata login failed. Configure Earthdata credentials or call earthaccess.login(persist=True)."
        )

    granules = []
    for product in ("MOD13Q1", "MYD13Q1"):
        granules.extend(
            earthaccess.search_data(
                short_name=product,
                version="061",
                bounding_box=bbox,
                temporal=(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")),
            )
        )

    # CMR returns overlapping composites. Match evy's composite-start semantics
    # and keep only the latest processing revision for each product/date/tile.
    bounds = Transformer.from_crs(4326, _CRS, always_xy=True).transform_bounds(
        *bbox, densify_pts=21
    )
    selected = {}
    for granule in granules:
        names = [Path(urlparse(url).path).name for url in granule.data_links()]
        names = [name for name in names if _FILENAME.fullmatch(name)]
        if len(set(names)) != 1:
            raise ValueError("NASA granule has no unique MODIS v061 HDF download")
        name = names[0]
        match = _FILENAME.fullmatch(name)
        date = datetime.strptime(match[2], "%Y%j")
        h, v = int(match[3][1:3]), int(match[3][4:6])
        left, top = (h - 18) * _TILE_SIZE, (9 - v) * _TILE_SIZE
        # CMR's geographic tile footprints can overselect sinusoidal tiles.
        if (
            left >= bounds[2]
            or left + _TILE_SIZE <= bounds[0]
            or top <= bounds[1]
            or top - _TILE_SIZE >= bounds[3]
        ):
            continue
        if start <= date <= end:
            key = match[1], match[2], match[3]
            if key not in selected or name > selected[key][0]:
                selected[key] = name, date, granule
    if not selected:
        raise ValueError(
            f"No NASA MODIS composites start within {start_date}/{end_date} for bbox={bbox}"
        )

    cache = _cache_base() / "earthdata"
    cache.mkdir(parents=True, exist_ok=True)
    by_date = {}
    for name, date, granule in sorted(selected.values(), key=lambda item: item[0]):
        path = cache / name
        if not path.exists():
            with TemporaryDirectory(dir=cache) as staging:
                files = earthaccess.download([granule], local_path=staging, threads=1)
                if len(files) != 1 or Path(files[0]).name != name:
                    raise RuntimeError(
                        f"NASA download incomplete for {name}; retry the request"
                    )
                # Validate before publishing; a failed transfer never poisons cache.
                _open_tile(Path(files[0]), date, bounds)
                Path(files[0]).replace(path)
        tile = _open_tile(path, date, bounds)
        if tile is not None:
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
