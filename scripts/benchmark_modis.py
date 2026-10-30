"""Time one local MODIS run without using or clearing the user's cache.

Run from the checkout with: python scripts/benchmark_modis.py --help
Use separate processes and empty cache directories for cold comparisons.
"""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
from time import perf_counter

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

import evy
from evy.load import load_landcover


def cache_size(cache):
    files = list((cache / "earthdata").glob("*.hdf"))
    files += list((cache / "laads").glob("*.nc4"))
    return len(files), sum(path.stat().st_size for path in files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=["earthdata", "planetary_computer", "laads"],
        required=True,
    )
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--bbox", type=float, nargs=4, default=[29.5, -1.9, 29.6, -1.8])
    parser.add_argument("--country", help="ISO3 country instead of the small pilot box")
    parser.add_argument("--admin-level", type=int, default=1)
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2023-01-20")
    parser.add_argument("--download-threads", type=int, default=4)
    parser.add_argument("--mask-cropland", action="store_true")
    parser.add_argument("--require-empty-cache", action="store_true")
    parser.add_argument(
        "--reference", type=Path, help="Statistics CSV from an equivalent run"
    )
    args = parser.parse_args()
    if args.download_threads < 1:
        parser.error("--download-threads must be positive")
    xmin, ymin, xmax, ymax = args.bbox
    if not (-180 <= xmin < xmax <= 180 and -90 <= ymin < ymax <= 90):
        parser.error("--bbox must be west south east north with non-zero area")
    if (
        args.require_empty_cache
        and args.cache_dir.exists()
        and any(args.cache_dir.iterdir())
    ):
        parser.error("cold runs require an empty cache directory; nothing was deleted")
    if (
        args.output.with_suffix(".json").exists()
        or args.output.with_suffix(".csv").exists()
    ):
        parser.error("output already exists; choose a new output path")
    os.environ["EVY_CACHE_DIR"] = str(args.cache_dir.resolve())
    from evy import boundaries as boundary_module

    boundary_module.CACHE_DIR = boundary_module._resolve_cache_dir()
    if args.provider == "earthdata":
        from evy import _earthdata

        _earthdata._DOWNLOAD_THREADS = args.download_threads

    if args.country:
        boundaries = evy.get_boundaries(args.country, admin_level=args.admin_level)
        boundaries = boundaries.rename(columns={"shapeName": "zone"})
    else:
        boundaries = gpd.GeoDataFrame(
            {"zone": ["probe"]}, geometry=[box(*args.bbox)], crs=4326
        )
    before_files, before_bytes = cache_size(args.cache_dir)
    report = {
        "label": args.label,
        "provider": args.provider,
        "bbox": boundaries.to_crs(4326).total_bounds.tolist(),
        "country": args.country,
        "zones": len(boundaries),
        "start": args.start,
        "end": args.end,
        "mask_cropland": args.mask_cropland,
        "freq": "ME",
        "stats": ["mean", "count"],
        "download_threads": args.download_threads
        if args.provider == "earthdata"
        else None,
        "cache_files_before": before_files,
        "cache_bytes_before": before_bytes,
        "python": sys.version.split()[0],
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("evy", "xarray", "dask", "rasterio")
        },
        "note": "No final-result cache used. PC network bytes and OS/remote caches are not measured. Peak RSS includes imports and intermediate arrays.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = stage = perf_counter()
    try:
        ds = evy.load_modis(boundaries, args.start, args.end, provider=args.provider)
        report["discovery_acquisition_setup_seconds"] = perf_counter() - stage
        stage = perf_counter()
        ds = ds.compute()
        report["materialize_seconds"] = perf_counter() - stage
        report["shape"] = dict(ds.sizes)
        report["observations"] = [str(date) for date in ds.time.values]
        assert ds.sizes["time"] > 0 and np.isfinite(ds.evi_raw.values).any()
        stage = perf_counter()
        landcover = (
            load_landcover(boundaries, ds).compute() if args.mask_cropland else None
        )
        report["landcover_seconds"] = perf_counter() - stage
        stage = perf_counter()
        result = (
            evy.compute_zonal_stats(
                ds,
                boundaries,
                zone_col="zone",
                land_cover=landcover,
                freq="ME",
                stats=["mean", "count"],
            )
            .sort_values(["date", "zone"])
            .reset_index(drop=True)
        )
        report["aggregate_and_extract_seconds"] = perf_counter() - stage
        report["total_seconds"] = perf_counter() - started
        assert len(result) > 0 and result["count"].sum() > 0
        result.to_csv(args.output.with_suffix(".csv"), index=False)
        if args.reference:
            reference = (
                pd.read_csv(args.reference, parse_dates=["date"])
                .sort_values(["date", "zone"])
                .reset_index(drop=True)
            )
            pd.testing.assert_frame_equal(
                result[["date", "zone"]], reference[["date", "zone"]]
            )
            np.testing.assert_allclose(
                result[["mean", "count"]],
                reference[["mean", "count"]],
                rtol=1e-6,
                atol=1e-8,
                equal_nan=True,
            )
            report["statistics_match_reference"] = True
        report["status"] = "ok"
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        raise
    finally:
        report["elapsed_seconds"] = perf_counter() - started
        report["cache_files_after"], report["cache_bytes_after"] = cache_size(
            args.cache_dir
        )
        report["new_cached_bytes"] = report["cache_bytes_after"] - before_bytes
        report["process_peak_rss_mib"] = resource.getrusage(
            resource.RUSAGE_SELF
        ).ru_maxrss / (1024**2 if sys.platform == "darwin" else 1024)
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
