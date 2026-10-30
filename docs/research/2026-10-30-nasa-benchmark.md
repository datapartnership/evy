# NASA access pilot and downloader change

Date: 2026-10-30. This follows [the access-method research](2026-10-30-nasa-access-services.md).

**Implementation follow-up on `feat/laads-opendap`:** LAADS is now implemented
and is the default local MODIS provider; omitted MODIS backend arguments resolve
to local computation. Sentinel-2 still resolves to GEE. Explicit PC, GEE, and
full-HDF choices remain available. The initial investigation below is retained
as a record; statements about a proposed/unimplemented provider are superseded
by this follow-up.

## Production-provider country/year validation

The implemented provider completed Rwanda ADM1 for all of 2023 with WorldCover
cropland masking: 46 observations, 92 native tile windows, five zones, and 60
monthly rows. The cold run took 260.91 seconds and cached 61,919,285 bytes of
validated EVI/QA subsets. Its eager benchmark peak RSS was approximately 1,726
MiB. The normal public `zonal_stats` call with backend/provider omitted reused
those subsets, returned all 60 rows, matched the cold result, and took 42.09
seconds including boundary loading. [Cold run](benchmarks/laads-rwanda-year.json),
[default-call warm run](benchmarks/laads-default-rwanda-warm.json).

The PC run completed in 828.53 seconds but returned only 44 observations. Its
February 18 Terra and October 24 Aqua cohorts were absent, and none of the four
corresponding NASA granule IDs matched PC's catalogue even without spatial or
date filters. As expected, the full-cohort monthly statistics differed in
February and October. This is a source-coverage difference, not an adapter parity
success. [PC run](benchmarks/pc-rwanda-year.json),
[missing granules](benchmarks/pc-rwanda-missing-granules.json),
[coverage impact](benchmarks/rwanda-year-coverage-impact.json).

Restricting NASA to the same 44 PC observation dates for a separate comparison
produced matching country/year masked statistics (`rtol=1e-6, atol=1e-8`): maximum
absolute EVI-mean difference 5.99e-12, maximum fractional-count difference
1.11e-6. Production retains all 46 NASA observations.
[Common-observation parity](benchmarks/rwanda-year-common-observation-parity.json).

These are exploratory runs under variable remote-service latency, not universal
performance promises. Small validation requests overlapped portions of the PC
run. In addition to the country/year checks, an opt-in live test passed raw
EVI/QA pixel parity across a tile boundary, crop-masked statistics, and GeoTIFF
export. A fresh public-default request retrieved the October 8, 2026 Aqua data
absent from the tested PC catalogue.
[Recent default-provider check](benchmarks/laads-provider-recent.json).

Implementation details: discovery and input validation are shared with the
full-HDF provider. LAADS transfers are lazy and bounded to four per process;
both bands share one request, transient failures retry with a bound, and only
validated subsets are atomically cached. Authentication/network exceptions
are sanitized to avoid exposing upstream auth metadata. `earthaccess` is a
core dependency; pyhdf remains optional for full-HDF downloads. Existing
notebooks explicitly preserve their previous PC or GEE choices. Changing from
GEE's Dynamic World to local WorldCover can change crop-masked results, and the
README/API migration notes call this out.

Final branch validation: 97 tests passed with two opt-in live tests skipped in
the normal suite. The LAADS live test was separately enabled and passed. Ruff
checks, changed-file formatting, notebook Python syntax, and lockfile validation
passed. The full-HDF live export test was not rerun because it requires large
source-tile downloads; its offline HDF fixture tests passed.

**Correction after a broader route check:** Aqua MYD13Q1 data is accessible through NASA LAADS OPeNDAP. The exact Jan 9, 2023 granule that failed at the central cloud endpoint successfully delivered a 49×49 EVI+QA subset via LAADS: HTTP 200, 21,963 bytes, 4.81 seconds for the data request. Both bands matched every valid AppEEARS comparison cell exactly. Earlier endpoint failures below remain valid observations of `opendap.earthdata.nasa.gov`, but must not be generalized to all NASA OPeNDAP services. See [the corrected route findings](2026-10-30-aqua-opendap-routes.md) and [data/parity results](benchmarks/laads-aqua-data-parity.json). The implementation follow-up above records the subsequent provider integration and country/year tests.

## Scope and implementation

Evy's NASA provider now downloads missing files in batches of up to four concurrent transfers. HDF4 validation and reading remain serial under the existing lock. Each file is validated before atomic publication to the cache; completed batches survive a later batch failure. Existing files are reused. The public API, processing rules, and default backend/provider are unchanged.

`scripts/benchmark_modis.py` measures discovery/acquisition/setup, raster materialization, optional WorldCover preparation, temporal aggregation plus zonal extraction, total time, source-cache growth, and process peak memory. Each run writes JSON and statistics CSV. It bypasses the final-statistics cache, refuses an occupied output path, and can require an empty source-cache directory without deleting anything. It is a small-area, in-memory benchmark harness for macOS/Linux, not a memory-bounded country-history runner.

## Pilot definition

- Region: longitude 29.5–29.6, latitude -1.9–-1.8, a small rectangle in Rwanda, one MODIS tile.
- Dates: 2023-01-01 through 2023-01-20 inclusive by composite start: Terra Jan 1, Aqua Jan 9, Terra Jan 17.
- Science: MOD13Q1/MYD13Q1 v061, raw EVI plus pixel reliability, existing quality filtering and scale factor, pixel-wise monthly median followed by exactextract mean and fractional count.
- Cropland mask disabled to isolate MODIS acquisition; this does not establish performance or parity of a masked country-scale workflow.
- Local Python 3.11.12, xarray 2025.12.0, Dask 2026.1.2, rasterio 1.4.4. No GEE compute used.

## Completed observations

| Path | Observed time | Transfer/storage observation | Result |
|---|---:|---|---|
| Planetary Computer, first process | 29.63 s total | Remote bytes not instrumented | All 3 observations; monthly mean 0.3850227060 |
| Planetary Computer, repeated fresh process | 59.27 s total | No Evy source-pixel cache; OS/server caches uncontrolled | Statistics matched first process |
| Serial NASA full-HDF attempt | Aborted after at least 798 s since cache creation | Only 1 of 3 granules completed: 221,645,171 bytes | Incomplete; not an end-to-end timing |
| Concurrent NASA full-HDF attempt, 4 workers | Stopped after at least 360 s since cache creation | 274,726,912 bytes in partial downloads; no complete granules | Incomplete; not an end-to-end timing |
| NASA cached HDF, Jan 1 only | 57.27 s total | No new source bytes | 57.19 s setup/discovery; 0.058 s pixels, 0.012 s aggregation/extraction |
| AppEEARS area task | 459.31 s to ready; 100.86 s raster download; 564.49 s including login/setup/bundle access | 70,983 bytes across returned rasters | All 3 requested observations matched; see parity below |
| Cloud OPeNDAP DAP4, Terra Jan 1 | 12.60 s subset response | 137,910 bytes | EVI and QA matched on shared grid |
| Cloud OPeNDAP DAP4, Terra Jan 17 | 7.38 s subset response | 137,896 bytes | EVI and QA matched on shared grid |
| Cloud OPeNDAP, Aqua Jan 9 | Metadata request returned 404 | No working subset | Cannot replace combined Terra/Aqua pipeline |

The DAP4 prototype took 53.03 seconds in total including authentication, discovery, metadata, both successful subsets, and the failed Aqua probe. Its per-response times exclude these other stages and local processing; they must not be presented as equivalent to complete PC pipeline timings.

The single-observation warm NASA run is a different date range from the 3-observation comparisons. It isolates where time went after a source-file cache hit, not relative provider throughput. Its setup stage includes authentication, two CMR searches, tile selection, and metadata setup, so it does not establish that authentication alone or either individual search took 57 seconds. Avoiding repeated discovery for identical workloads is another possible optimization; Evy's existing final-statistics cache already skips it on a complete result-cache hit.

These are exploratory single-run observations. The first serial attempt overlapped small service probes and a briefly started parallel attempt that was canceled to avoid competing full downloads. This prevents a controlled serial/parallel speedup claim. The subsequent concurrent run used a new empty cache and was stopped after six minutes of acquisition, with no other full-tile download running. Its partial transfers were removed after recording their sizes. Latency varied substantially even between PC repeats. No request was made from a controlled in-region cloud worker.

## Subset parity and important adapter details

For AppEEARS, all 3 requested observations had exactly equal raw EVI and QA arrays on the shared PC grid (`time=3, y=48, x=49`). Monthly mean and fractional count also matched when computed on AppEEARS' own native grid (`49×49`) within `rtol=1e-6, atol=1e-8`. Mean was 0.38502270595 and count 2302.79820368. Source pixel coordinates differed slightly, so shared-grid comparison used nearest coordinate matching with 0.01 m tolerance and no radiometric interpolation.

AppEEARS native GeoTIFF EVI was **raw int16** with a scale metadata tag of 0.0001. Rasterio's raw read was compared, then Evy's scale was applied once. An adapter that automatically decodes scale metadata must not apply it again. The task also returned composites beginning before Jan 1 and ancillary VI Quality rasters. Those earlier composites were excluded from parity and monthly statistics to preserve Evy's composite-start semantics. The pilot downloaded all returned TIFFs; a production downloader can skip unused dates and ancillary bands to save HTTP round trips. Request GeoJSON and exact products/layers are recorded in `benchmarks/appeears-probe.json`.

For cloud OPeNDAP, `.dds` returned HTTP 400 **because DAP2 cannot represent the signed-byte reliability band**, not because the entire cloud service was unavailable. `.dmr` successfully returned DAP4 metadata for the two in-range Terra granules. Selecting both bands through `.dap.nc4` with a `dap4.ce` constraint produced working NetCDF4 subsets. Each constraint selected a native 49×49 pixel window. Both bands matched PC exactly on the shared grid for the two Terra dates. The older `.dds` probe is retained as a diagnostic artifact; the DAP4 result supersedes its apparent failure.

The constraint uses the full group path, e.g. `/MODIS_Grid_16DAY_250m_500m_VI/Data_Fields/_250m_16_days_EVI[row0:1:row1][col0:1:col1]`, plus pixel reliability separated by `;`. The `.dmr` supplies the tile's native extent and dimensions. Returned group subdatasets were read using rasterio's NetCDF driver with `GDAL_NETCDF_BOTTOMUP=NO`, preserving source row order, and coordinates were constructed from the source metadata. A production adapter must validate dimensions, fill values, projection, dates, and granule coverage rather than assume these pilot constants apply universally.

The tested Aqua granule lacked an advertised OPeNDAP link; a diagnostic request using its collection and granule identifier returned 404. This does not prove collection-wide unavailability, but rules out silently treating the tested combined workflow as fully supported.

A subsequent authenticated recheck confirmed the current Aqua collection ID (`C2307290656-LPCLOUD`) and again returned HTTP 404 from the same `opendap.earthdata.nasa.gov` host. The server error identified failure to retrieve the granule's `.hdf.dmrpp` source metadata sidecar. This is a granule-level backend metadata retrieval problem, not evidence that the cloud OPeNDAP service as a whole is unavailable. Raw error bodies were not saved because they can contain temporary signed source URLs.

A broader follow-up sampled five Aqua granules: Rwanda in January 2023, January 2024, and September 2026, plus US and Indonesia tiles in January 2023. All five lacked advertised cloud OPeNDAP links and returned DAP4 metadata HTTP 404 with source `.dmrpp` retrieval errors. A Terra control using the same authentication and request pattern returned valid DAP4 metadata and a successful tiny EVI+QA NetCDF4 subset. This strengthens the evidence for an Aqua service-metadata coverage problem in the sampled files, but does not establish collection-wide unavailability or its underlying cause. [Structured coverage probe](benchmarks/aqua-coverage-probe.json).

The modisfast website and current cloud CSV were subsequently inspected to reconcile its Aqua support claim with these probes. The published table lists Aqua products such as `MYD11A1.061` and `MYD11A2.061` (land-surface temperature). Neither `MYD13Q1.061` nor `MOD13Q1.061` appears in the 95-row current cloud CSV; catalogue absence alone is not proof of service unavailability, since Terra worked in this pilot and the source also has historical-catalogue fallbacks. Its cloud URL builder constructs the same `/collections/{collection_id}/granules/{granule_id}` route used here. Its `.mf_cloud_dds` helper explicitly detects missing DMR++ metadata errors and suggests other dates, Earthdata Search, AppEEARS, or LP DAAC support. Its availability-check function distinguishes sampled operational, partial, and unavailable states and warns against extrapolating a successful sample to every granule. These details reconcile general Aqua product support with the observed MYD13Q1 failures; the package was inspected, not installed or executed in this comparison. [Published collection table](https://ptaconet.github.io/modisfast/#collections-available-in-modisfast), [current cloud catalogue](https://github.com/ptaconet/modisfast/blob/master/inst/extdata/data_collections_cloud.csv), [URL/error handling](https://github.com/ptaconet/modisfast/blob/master/R/mf_get_url.R), [availability probes and URL construction](https://github.com/ptaconet/modisfast/blob/master/R/mf_list_collections_cloud.R).

The completed full NASA HDF for Terra Jan 1 was also decoded through Evy's reader and compared with the corresponding DAP4 subset, which retains the rectangular source window: both 49×49 EVI and QA arrays matched exactly. This checks the real HDF decoding path independently of the synthetic fixtures without re-downloading additional tiles. AppEEARS masks cells outside the requested AOI within its outer raster rectangle; a comparison of its full bounding array against an unmasked source window must account for that clipping. The shared-PC-grid and native polygon-statistics comparisons above do account for the differing extents.

## Reproduce the local-provider runs

Install the checkout with the existing optional Earthdata readers and configure Earthdata Login. Run these from the repository root; use fresh output paths and cache directories for each new experiment:

```sh
.venv/bin/python scripts/benchmark_modis.py \
  --provider planetary_computer \
  --cache-dir data/benchmarks/example/pc \
  --output data/benchmarks/example/pc-first \
  --label pc-first --require-empty-cache

.venv/bin/python scripts/benchmark_modis.py \
  --provider earthdata --download-threads 4 \
  --cache-dir data/benchmarks/example/nasa \
  --output data/benchmarks/example/nasa-cold \
  --label nasa-cold --require-empty-cache \
  --reference data/benchmarks/example/pc-first.csv

.venv/bin/python scripts/benchmark_modis.py \
  --provider earthdata --download-threads 4 \
  --cache-dir data/benchmarks/example/nasa \
  --output data/benchmarks/example/nasa-warm \
  --label nasa-warm \
  --reference data/benchmarks/example/pc-first.csv
```

Use `--download-threads 1` with another empty cache to measure serial acquisition, and `--mask-cropland` consistently on both reference and candidate to include WorldCover. `--bbox`, `--start`, and `--end` change the pilot area and period. Run full-tile acquisition comparisons sequentially to avoid bandwidth contention. This benchmark script loads the small raw raster cube in memory; use Evy's normal bounded pipeline for larger analyses.

## Evidence and next decision

### Freshness follow-up: the fast provider is not necessarily complete

A live July–October 2026 catalogue comparison, checked on October 30, found the same recent Aqua gap in the Rwanda and Indonesia test areas. Terra's latest listed composite start was September 30 in both NASA CMR and Planetary Computer. Aqua's latest was October 8 in NASA CMR but September 22 in Planetary Computer. The October 8 Aqua composite was therefore missing from PC's spatial/temporal search results for both tested tiles. The structured record also checks exact NASA granule IDs without spatial or date filters. These are metadata availability checks, not asset-download tests or evidence of a permanent global cutoff. Search results were filtered to composite starts within the same interval; valid STAC interval timestamps and overlapping earlier composites were accounted for. [Coverage comparison](benchmarks/recent-pc-nasa-coverage.json).

This qualifies the earlier provider recommendation: the historical pilot established speed and output parity, not current completeness. A proposed local default should verify expected product/date/tile coverage against NASA's catalogue, use PC where available, and expose gaps or fetch the missing granules through NASA. Merely returning a non-empty STAC result or checking the collection's open-ended temporal extent is insufficient. An open [PC MODIS ingestion-gap report](https://github.com/microsoft/PlanetaryComputer/issues/453) also documents historical reports across MODIS collections, although it does not by itself establish the current state of Evy's specific product.

Machine-readable records and statistics are in [benchmarks/](benchmarks/); downloaded HDF/NetCDF/GeoTIFF files are under ignored `data/benchmarks/nasa-access/`. Records contain no credentials or signed download URLs.

Validation: 73 unit tests passed; the existing opt-in full NASA/PC live test remained skipped. New tests cover batch acquisition/cache reuse, partial responses and retries, corrupt HDF rejection, arbitrary return order, fetching only missing dates, and preserving completed batches after a later failure. Ruff checks and formatting passed. The authenticated parity checks described above were run separately from pytest.

AppEEARS demonstrates a correct, compact direct-NASA route for the tested Terra/Aqua workflow, but its observed queue latency is unsuitable for promising an immediate response. The central-cloud MYD13Q1 endpoint failures do not apply to the independent LAADS OPeNDAP route, which delivered matching Aqua EVI+QA pixels and successfully served both tested October 8, 2026 granules missing from PC. Direct NASA OPeNDAP therefore remains a viable candidate for Evy's default processing. A LAADS-aware adapter and representative masked, larger end-to-end benchmarks are still needed before choosing a default; the present loader still downloads full HDFs and does not use this newly verified subset route.
