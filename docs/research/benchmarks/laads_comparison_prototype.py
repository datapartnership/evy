import argparse
import concurrent.futures
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio
from rasterio.io import MemoryFile
import requests
from shapely.geometry import box
import xarray as xr
import evy
from evy._earthdata import _CRS, _TILE_SIZE

p = argparse.ArgumentParser()
p.add_argument("--provider", choices=["laads", "pc"], required=True)
p.add_argument("--label", required=True)
args = p.parse_args()
bbox = (29.5, -1.9, 29.6, -1.8)
start = "2023-01-01"
end = "2023-01-20"
boundaries = gpd.GeoDataFrame({"zone": ["probe"]}, geometry=[box(*bbox)], crs=4326)
report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "provider": args.provider,
    "bbox": bbox,
    "start": start,
    "end": end,
    "mask_cropland": False,
    "note": "Exploratory small-area comparison; no source-subset or final-result cache used. Prototype uses known MOD13Q1 native sinusoidal grid, concurrent public CMR discovery, and up to four LAADS subset requests. OS/server cache state uncontrolled. Imports excluded for both.",
}
began = stage = time.perf_counter()
if args.provider == "pc":
    ds = evy.load_modis(boundaries, start, end).compute()
    report["acquisition_seconds"] = time.perf_counter() - stage
else:
    import earthaccess

    earthaccess.login(strategy="netrc")
    session = earthaccess.get_requests_https_session()
    report["authentication_seconds"] = time.perf_counter() - stage
    stage = time.perf_counter()

    def search(product):
        r = requests.get(
            "https://cmr.earthdata.nasa.gov/search/granules.json",
            params={
                "short_name": product,
                "version": "061",
                "provider": "LPCLOUD",
                "bounding_box": ",".join(map(str, bbox)),
                "temporal": start + "T00:00:00Z," + end + "T23:59:59Z",
                "page_size": 100,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["feed"]["entry"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        entries = sum(list(pool.map(search, ["MOD13Q1", "MYD13Q1"])), [])
    selected = {}
    for e in entries:
        name = e["title"]
        m = re.fullmatch(r"(M[OY]D13Q1)\.A(\d{7})\.(h\d{2}v\d{2})\.061\.(\d{13})", name)
        if not m:
            continue
        date = datetime.strptime(m[2], "%Y%j")
        if not pd.Timestamp(start) <= date <= pd.Timestamp(end):
            continue
        key = m[1], m[2], m[3]
        if key not in selected or name > selected[key]:
            selected[key] = name
    report["discovery_seconds"] = time.perf_counter() - stage
    projected = Transformer.from_crs(4326, _CRS, always_xy=True).transform_bounds(
        *bbox, densify_pts=21
    )

    def fetch(name):
        s = requests.Session()
        s.headers.update(session.headers)
        s.cookies.update(session.cookies)
        m = re.fullmatch(
            r"(M[OY]D13Q1)\.A(\d{4})(\d{3})\.h(\d{2})v(\d{2})\.061\.(\d{13})", name
        )
        left = (int(m[4]) - 18) * _TILE_SIZE
        top = (9 - int(m[5])) * _TILE_SIZE
        pixel = _TILE_SIZE / 4800
        c0 = max(0, int(np.floor((projected[0] - left) / pixel)))
        c1 = min(4799, int(np.ceil((projected[2] - left) / pixel)) - 1)
        r0 = max(0, int(np.floor((top - projected[3]) / pixel)))
        r1 = min(4799, int(np.ceil((top - projected[1]) / pixel)) - 1)
        assert c0 <= c1 and r0 <= r1
        ce = ";".join(
            "/" + band + f"[{r0}:1:{r1}][{c0}:1:{c1}]"
            for band in ["_250m_16_days_EVI", "_250m_16_days_pixel_reliability"]
        )
        url = f"https://ladsweb.modaps.eosdis.nasa.gov/opendap/RemoteResources/laads/allData/61/{m[1]}/{m[2]}/{m[3]}/{name}.hdf.dap.nc4"
        t = time.perf_counter()
        r = s.get(url, params={"dap4.ce": ce}, timeout=60)
        # Keep server error bodies out of logs (may contain signed source URLs).
        if r.status_code != 200 or not r.content.startswith(b"\x89HDF\r\n\x1a\n"):
            raise RuntimeError(f"LAADS subset failed HTTP {r.status_code}")
        variables = {}
        with rasterio.Env(GDAL_NETCDF_BOTTOMUP="NO"):
            with MemoryFile(r.content) as memory:
                with memory.open() as container:
                    for sub in container.subdatasets:
                        key = "evi_raw" if sub.endswith("_EVI") else "qa"
                        if key == "qa" and not sub.endswith("_pixel_reliability"):
                            continue
                        with rasterio.open(sub) as src:
                            a = (
                                src.read(1, masked=True)
                                .astype("float32")
                                .filled(np.nan)
                            )
                            assert a.shape == (r1 - r0 + 1, c1 - c0 + 1)
                            variables[key] = (("y", "x"), a)
        assert set(variables) == {"evi_raw", "qa"}
        date = datetime.strptime(m[2] + m[3], "%Y%j")
        ds = (
            xr.Dataset(
                variables,
                coords={
                    "x": left + (np.arange(c0, c1 + 1) + 0.5) * pixel,
                    "y": top - (np.arange(r0, r1 + 1) + 0.5) * pixel,
                },
            )
            .expand_dims(time=[date])
            .rio.write_crs(_CRS)
        )
        return ds, {
            "granule": name,
            "bytes": len(r.content),
            "request_and_decode_seconds": time.perf_counter() - t,
        }

    stage = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, sorted(selected.values())))
    report["subset_and_decode_seconds"] = time.perf_counter() - stage
    ds = (
        xr.concat([r[0] for r in results], dim="time")
        .sortby("time")
        .rio.write_crs(_CRS)
    )
    report["requests"] = [r[1] for r in results]
    report["transferred_bytes"] = sum(r[1]["bytes"] for r in results)
    report["acquisition_seconds"] = time.perf_counter() - began
stage = time.perf_counter()
result = evy.compute_zonal_stats(
    ds, boundaries, zone_col="zone", freq="ME", stats=["mean", "count"]
)
report["processing_seconds"] = time.perf_counter() - stage
report["total_seconds"] = time.perf_counter() - began
expected = pd.read_csv("docs/research/benchmarks/pc-first.csv", parse_dates=["date"])
pd.testing.assert_frame_equal(result[["date", "zone"]], expected[["date", "zone"]])
np.testing.assert_allclose(
    result[["mean", "count"]], expected[["mean", "count"]], rtol=1e-6, atol=1e-8
)
assert len(ds.time) == 3
report.update(
    statistics_match_reference=True,
    shape=dict(ds.sizes),
    statistics=result.assign(date=result.date.astype(str)).to_dict("records"),
)
Path("docs/research/benchmarks/" + args.label + ".json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(json.dumps(report, indent=2), flush=True)
