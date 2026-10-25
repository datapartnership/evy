"""GeoTIFF output for local raster data."""

import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401 — activates .rio accessor
import xarray as xr


def export_geotiff(data: xr.DataArray, output_dir: str | Path) -> list[Path]:
    """Save pixels as compressed GeoTIFFs, preserving CRS, grid and nodata.

    Accepts a 2-D raster or a raster series with a ``time`` or ``year``
    dimension. Writes one file per observation/year and returns its paths.
    Files are named after the DataArray (e.g. ``evi_2023-01-01.tif`` or
    ``landcover_2025.tif``). Existing files are never overwritten. Each file
    is computed separately and published only after its write succeeds.

    Floating rasters without a nodata value use NaN. Integer rasters retain
    their existing nodata value, if any. Data covers the loader's bounding
    box; this function does not clip pixels to administrative polygons.
    """
    if not isinstance(data, xr.DataArray):
        raise TypeError("data must be an xarray.DataArray")
    if data.rio.crs is None:
        raise ValueError("Raster must have a CRS before GeoTIFF export")
    series_dims = set(data.dims) - {"x", "y"}
    if not {"x", "y"}.issubset(data.dims) or series_dims not in (
        set(),
        {"time"},
        {"year"},
    ):
        raise ValueError("Expected (y, x), (time, y, x), or (year, y, x) raster")
    name = str(data.name or "raster")
    if Path(name).name != name or name in (".", ".."):
        raise ValueError("Raster name must be a filename without directory components")
    dim = next(iter(series_dims), None)
    if dim is None:
        labels = [""]
    elif dim == "time":
        labels = [
            pd.Timestamp(t).isoformat().replace(":", "-") for t in data.time.values
        ]
        labels = [label.removesuffix("T00-00-00") for label in labels]
    else:
        labels = [str(int(y)) for y in data.year.values]
    if not labels:
        raise ValueError("Cannot export an empty raster series")
    output_dir = Path(output_dir)
    paths = [
        output_dir / f"{name}{'_' + label if label else ''}.tif" for label in labels
    ]
    if len(set(paths)) != len(paths):
        raise ValueError("Raster series has duplicate output dates/years")
    for path in paths:
        if path.exists():
            raise FileExistsError(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, path in enumerate(paths):
        layer = data.isel({dim: i}, drop=True) if dim else data
        if np.issubdtype(layer.dtype, np.floating) and layer.rio.nodata is None:
            layer = layer.rio.write_nodata(np.nan)
        fd, temporary = tempfile.mkstemp(dir=output_dir, suffix=".tif")
        os.close(fd)
        try:
            layer.transpose("y", "x").rio.to_raster(temporary, compress="LZW")
            os.link(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return paths
