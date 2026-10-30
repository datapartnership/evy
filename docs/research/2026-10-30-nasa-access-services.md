# Efficient direct NASA MODIS access

Research date: 2026-10-30. Scope: Evy's MOD13Q1/MYD13Q1 Collection 6.1 EVI workflow outside Earth Engine. This is an access-method investigation, not a measured performance comparison. No authenticated processing jobs or bulk downloads were submitted.

Follow-up: [implementation and authenticated pilot measurements](2026-10-30-nasa-benchmark.md) now include working Terra DAP4 subsets and an AppEEARS Terra/Aqua parity check. The findings below describe the initial research snapshot; the pilot supersedes the preliminary OPeNDAP availability probes.

Further correction: [the broader route recheck](2026-10-30-aqua-opendap-routes.md) established working Aqua MYD13Q1 EVI+QA subsets through NASA LAADS OPeNDAP, including recent files missing from Planetary Computer. Failure of the central-cloud endpoint must not be generalized to all OPeNDAP access.

## Findings

### 1. Subset before transfer: AppEEARS is a verified candidate

NASA's own migration guide recommends AppEEARS where possible, particularly for MODIS, to reduce preprocessing. It supports spatial, temporal, and variable selection and reformatting. This offers a way to avoid transferring entire multi-band HDF tiles for a small study area. [NASA migration guide](https://github.com/nasa/MODIS-VIIRS-Data-Resources/blob/main/guides/after_datapool.md).

Live unauthenticated metadata checks confirmed `Available: true` for **both `MOD13Q1.061` and `MYD13Q1.061`**. Both expose `_250m_16_days_EVI`, `_250m_16_days_VI_Quality`, and `_250m_16_days_pixel_reliability`. Their metadata distinguishes original integer EVI from scaled float output, so an adapter must check downloaded output metadata to avoid scaling twice. [Product registry](https://appeears.earthdatacloud.nasa.gov/api/product), [Terra layers](https://appeears.earthdatacloud.nasa.gov/api/product/MOD13Q1.061), [Aqua layers](https://appeears.earthdatacloud.nasa.gov/api/product/MYD13Q1.061).

The API accepts an `area` task with geographic GeoJSON, date ranges, selected product/layer pairs, and an output projection and format. Documented area output types include GeoTIFF and NetCDF4; projections include native and MODIS sinusoidal. Processing is task based: submit, inspect status, then download the bundle. [AppEEARS API](https://appeears.earthdatacloud.nasa.gov/api/).

**Inference for Evy:** request EVI plus the exact quality layer Evy uses, retain the MODIS grid where possible, cache returned subsets, and calculate polygon statistics locally. The service reduces transfer volume, but queue/processing delay can outweigh that saving for a tiny immediate query. End-to-end timing and pixel parity need testing before making it the default. Native projection alone does not prove identical pixel alignment or clipping behavior.

### 2. Cloud OPeNDAP deserves a targeted prototype, with availability checks

The legacy LP DAAC on-premises OPeNDAP retirement is **not** evidence that all modern NASA OPeNDAP access is unavailable. NASA's 2025 retirement announcement explicitly points users toward Earthdata Cloud OPeNDAP links in granule metadata. In May 2026 LP DAAC staff again explained that distinction. [Retirement announcement on NASA's forum](https://forum.earthdata.nasa.gov/viewtopic.php?t=7136), [2026 LP DAAC staff clarification](https://forum.earthdata.nasa.gov/viewtopic.php?t=7911).

A live CMR check advertised a cloud OPeNDAP URL for MOD13Q1 granules, including `MOD13Q1.A2022353.h20v09.061.2023006045317`: [CMR Terra metadata query](https://cmr.earthdata.nasa.gov/search/granules.json?short_name=MOD13Q1&version=061&provider=LPCLOUD&page_size=1&bounding_box=29,-3,31,-1&temporal=2023-01-01T00:00:00Z,2023-02-01T00:00:00Z). Example endpoint: `https://opendap.earthdata.nasa.gov/collections/C1748066515-LPCLOUD/granules/MOD13Q1.A2022353.h20v09.061.2023006045317`.

However, this investigation **did not establish working authenticated subsetting**. Unauthenticated `.dds` probes of two advertised Terra URLs returned HTTP 400 and 404. Three Aqua granules returned by a Rwanda-area/January-2023 search, plus an earliest-archive sample, had no OPeNDAP URL: [CMR Aqua metadata query](https://cmr.earthdata.nasa.gov/search/granules.json?short_name=MYD13Q1&version=061&provider=LPCLOUD&page_size=3&bounding_box=29,-3,31,-1&temporal=2023-01-01T00:00:00Z,2023-02-01T00:00:00Z). These samples do not establish collection-wide absence. Discover links from CMR rather than manufacture an endpoint for every granule.

For a practitioner implementation to study, the `modisfast` authors document selecting spatial/temporal/variable subsets and parallel downloads. The author website announces a September 29, 2026 return using the new NASA Earthdata Cloud OPeNDAP endpoint and Earthdata token authentication. Some indexed GitHub results still display the older interruption notice. This is evidence of a current implementation pattern, not proof that every Evy granule is supported. The useful transferable pattern is **small subset requests plus controlled concurrency**, not an assumed published speedup for Evy. [modisfast author documentation](https://ptaconet.github.io/modisfast/index.html).

### 3. Harmony currently does not provide the needed service for these collections

Harmony exposes collection-specific capability discovery. Live HTTP 200 responses for **both exact collection IDs** returned `services: []`, with variable, bbox, shape, temporal subsetting and reprojection disabled. Therefore Harmony should not be proposed as an already available replacement for this workflow just because the platform supports such operations for other datasets. [Terra capabilities](https://harmony.earthdata.nasa.gov/capabilities?collectionId=C1748066515-LPCLOUD), [Aqua capabilities](https://harmony.earthdata.nasa.gov/capabilities?collectionId=C2307290656-LPCLOUD), [Capability API documentation](https://harmony.earthdata.nasa.gov/docs).

### 4. Parallel acquisition and colocated compute solve different costs

`earthaccess` documents configurable concurrent downloads (`Store.get(..., threads=8)` by default) and authenticated S3 filesystems for in-region access in AWS `us-west-2`, with temporary credentials lasting one hour. Its file-opening interface also exposes caching/block-size options. [earthaccess Store API](https://earthaccess.readthedocs.io/en/stable/api/store/store/).

**Inference for Evy:** bounded parallel HTTPS downloads are a near-term improvement for laptop users. For repeated country-scale histories, a worker in the archive's region can process cached source data and return small results, avoiding repeated transfers to the laptop. Source data availability does not supply free compute: hosting, storage, and operational complexity must be measured. Opening an HDF4 file through a generic remote filesystem also does not make it a COG or guarantee that a chosen HDF4 reader supports efficient remote window reads.

## Suggested investigation order

1. Measure Evy's existing NASA and Planetary Computer paths with the same region, dates, quality rules, and land-cover mask; record cold and warm cache timings separately.
2. Compare bounded parallel full-granule acquisition with the current sequential acquisition.
3. Prototype AppEEARS area extraction for both Terra and Aqua, checking scaling, QA, dates, grid alignment, and result parity.
4. Prototype authenticated cloud OPeNDAP for representative granules only after confirming advertised links and supported variables; retain a full-file fallback.
5. Consider an in-region worker or persistent analysis-ready cache only if repeated large workloads justify it.

No method above has a measured speedup in this investigation. A provider-default decision should follow representative end-to-end benchmarks.

## Findings from Evy's current implementation

These are source-code observations, not timings:

- `src/evy/_earthdata.py:200–217` already caches complete HDF granules and publishes validated downloads atomically. However, each missing granule is downloaded sequentially using `earthaccess.download([granule], threads=1)`. Merely increasing Dask workers later does not parallelize this acquisition loop. A bounded queue of missing-file downloads is the first optimization to measure, preserving validation and atomic publication.
- `_open_tile` crops pixel reads after the complete file has been downloaded. Spatial cropping therefore saves local processing but not network transfer on the first run. Search and array construction use the collective boundary bounding box; sparse or island geometries can cause substantial overfetch.
- `_read_band` uses a global lock around HDF4 reads because the reader is not thread safe. More threads cannot remove that serialization. Converting repeatedly used EVI and QA bands to a suitable tiled format, or using isolated reader processes, is an option to profile after download costs are measured; do not simply remove the lock.
- `src/evy/_zonal_local.py:108–132` already computes bounded time blocks before extracting all zones, avoiding repeated lazy raster evaluation per polygon. Preserve this behavior. Its 1 GB target is a nominal output-array budget, not a hard cap on intermediate memory during temporal medians.
- `src/evy/cache.py` already caches final statistics with provider and mask parameters in the key. Existing source and result caches should be reused. An intermediate reusable pixel cache would be an additional layer, justified only by repeated workloads.
- `src/evy/load.py:154–161` already reads just EVI and pixel reliability through Planetary Computer. A live public STAC query confirmed that these are COG assets for `modis-13Q1-061`, including sample `MOD13Q1.A2026273.h35v10.061.2026289235152`. This is the same NASA MODIS product distributed in a different storage layout. It provides a useful existing local-compute baseline. Metadata availability does not establish completeness or download performance. [Live collection](https://planetarycomputer.microsoft.com/api/stac/v1/collections/modis-13Q1-061), [Live items](https://planetarycomputer.microsoft.com/api/stac/v1/collections/modis-13Q1-061/items?limit=1).
- Cropland masking adds a separate data dependency and resampling step. Cache the categorical mask on the MODIS grid for repeated runs, keyed by source, year, grid, resampling, and crop class. Measure unmasked access separately from the full masked pipeline.

## Benchmark design before a default switch

Use a small district, Rwanda, and a large or spatially dispersed country; test one year and a longer history. Compare current NASA download, bounded parallel NASA download, AppEEARS subsets, verified cloud OPeNDAP subsets, and existing Planetary Computer COG reads. Include GEE as the user-facing baseline where quota permits.

Record discovery, queue wait, transfer bytes/time, HDF decode, land-cover preparation, temporal aggregation, zonal extraction, peak memory, disk use, and total time. Measure (1) empty application cache, (2) raw files already cached with final results absent, and (3) final-result cache hits separately. For hosted workers also record startup, storage, and compute cost. Repeat enough to expose variable service latency; do not compare a queued request's download time alone with another method's full runtime.

Hold product/version, composite-start date semantics, EVI scaling, pixel-reliability filtering, native grid, nodata, crop-mask source/year, polygon weighting, and temporal frequency constant. Evy takes a temporal median at each pixel before zonal statistics. Computing zonal means first and then a temporal median generally changes the result. Likewise, replacing 250 m composites with NASA's coarser monthly product changes the scientific input rather than simply accelerating the same analysis.

For a repeated service, an incremental EVI+QA cache in COG or a workload-appropriate Zarr layout is a possible second-stage architecture: ingest new granules once, reuse the native grid and prepared masks, and cache outputs. This is an engineering proposal, not a NASA-provided MOD13Q1 Zarr service. Align compute chunks with storage blocks and available memory, following [Dask's array guidance](https://docs.dask.org/en/stable/array-best-practices.html).

For small site-centered requests, ORNL DAAC's TESViS REST service is another documented practitioner route. Its rectangular subsets and per-request limits make it a specialized candidate, rather than an assumed replacement for arbitrary country-wide polygon statistics. Verify current version and QA availability before adoption. [ORNL REST service](https://modis.ornl.gov/data/modis_webservice.html).
