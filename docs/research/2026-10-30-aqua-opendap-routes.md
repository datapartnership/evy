# Aqua MYD13Q1 OPeNDAP route recheck

Checked 2026-10-30. Question: does failure at `opendap.earthdata.nasa.gov` establish that Aqua MYD13Q1 v061 is unavailable through OPeNDAP generally?

Implementation follow-up: branch `feat/laads-opendap` now implements the LAADS
provider and defaults MODIS to local LAADS after country/year validation. The
prototype recommendation at the end is an earlier research snapshot; see the
[implementation and validation results](2026-10-30-nasa-benchmark.md#production-provider-countryyear-validation).

**No. NASA LAADS OPeNDAP successfully delivered EVI and QA data for the exact MYD13Q1 granule that failed at the central cloud endpoint.** The parent investigation confirmed a working data subset and numerical parity after the metadata checks below.

## Official evidence

NASA LAADS documents OPeNDAP for its public collections, with paths mirroring the archive hierarchy: archive set, product, year, day of year, filename. Its examples include an Aqua product, MYD04_3K. These statements describe LAADS's service, independently of LP DAAC's central-cloud route. [LAADS API guide](https://ladsweb.modaps.eosdis.nasa.gov/learn/using-laads-apis/), [LAADS tools and services](https://ladsweb.modaps.eosdis.nasa.gov/tools-and-services/).

The live LAADS archive explicitly lists **MYD13Q1 under archive set 61**, with year directories from 2002 through 2026. This establishes that the needed product is present in the source archive, rather than inferring it from support for an unrelated Aqua product. [MYD13Q1 archive](https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/61/MYD13Q1/).

LAADS announced that Earthdata Login authentication became mandatory for its OPeNDAP service on April 30, 2026. An unauthenticated failure therefore cannot establish absence. [Authentication notice](https://ladsweb.modaps.eosdis.nasa.gov/alerts-and-issues/193981).

The September 19, 2025 retirement announcement concerns **legacy on-premises OPeNDAP at LP DAAC**. It directs users to cloud granule links, AppEEARS, or source files. It does not announce retirement of LAADS OPeNDAP. [LP DAAC announcement](https://forum.earthdata.nasa.gov/viewtopic.php?t=7136).

## Authenticated metadata test

Exact tested base URL:

```text
https://ladsweb.modaps.eosdis.nasa.gov/opendap/RemoteResources/laads/allData/61/MYD13Q1/2023/009/MYD13Q1.A2023009.h20v09.061.2023026194807.hdf
```

Using configured Earthdata authentication:

| Suffix | HTTP | Evidence |
|---|---:|---|
| `.dmr` | 200 | DAP4 dataset metadata, 20,917 bytes |
| `.dds` | 200 | DAP2 dataset metadata, 1,076 bytes |
| `.dmr.html` | 200 | HTML interface; not treated as a data-read success |

The metadata contains flat science variables `_250m_16_days_EVI[YDim=4800][XDim=4800]` and `_250m_16_days_pixel_reliability[YDim][XDim]`. EVI is Int16; LAADS exposes reliability as Int32. This differs from the central cloud response, whose signed-byte reliability field prevented DAP2 metadata access. Therefore adapters must inspect each service's actual variables and data types rather than reuse central-cloud group paths unchanged.

Safe machine-readable results are in [laads-aqua-route-probe.json](benchmarks/laads-aqua-route-probe.json). The full public DMR metadata is under ignored `data/benchmarks/nasa-access/aqua-laads.dmr`. No raw error bodies or signed source URLs were saved.

## Scope of the conclusion

The correct distinction is **one failing endpoint versus a working alternate service for the same Aqua product and file**. This recheck does not prove availability for every date/tile or comparative end-to-end performance. The earlier central-cloud failures are insufficient grounds to exclude OPeNDAP as an Aqua access method.

## Actual EVI and QA delivery and parity

An authenticated DAP4 request to the same LAADS base URL plus `.dap.nc4` selected both flat variables through a `dap4.ce` constraint. The native source window was rows 864–912 and columns 4552–4600, inclusive:

```text
/_250m_16_days_EVI[864:1:912][4552:1:4600];/_250m_16_days_pixel_reliability[864:1:912][4552:1:4600]
```

The service returned HTTP 200 and a valid NetCDF4 payload, 21,963 bytes, in 4.81 seconds for the request (8.85 seconds including the separate probe's authentication/setup). Both 49×49 arrays were decoded with rasterio's NetCDF driver and compared against AppEEARS for the same date. All 2,353 finite comparison cells in each band matched exactly. AppEEARS masks cells outside its requested polygon, so cells it did not supply were excluded. [Actual-data and parity record](benchmarks/laads-aqua-data-parity.json).

The broader central-cloud recheck sampled 16 additional MYD13Q1 granules across two tiles and years 2002, 2005, 2010, 2015, 2020, 2023, 2025, and 2026. All returned DMR++ metadata 404 errors there. A different Aqua product, MYD11A2, successfully served a tiny temperature subset on the central cloud host, as did a Terra MOD13Q1 EVI+QA control. These controls directly disprove any general claim that the central host has no Aqua data, while the LAADS result directly disproves any general claim that MYD13Q1 cannot be accessed via OPeNDAP. [Broader central-cloud results](benchmarks/aqua-opendap-broader-recheck.json).

## Recent Aqua data missing from Planetary Computer also works

Both October 8, 2026 Aqua granules previously absent from Planetary Computer's catalogue were tested via LAADS:

| Tile | Granule | Metadata | Actual EVI+QA data |
|---|---|---:|---:|
| h20v09 (Rwanda test tile) | `MYD13Q1.A2026281.h20v09.061.2026300161933` | HTTP 200 | HTTP 200, valid decoded 2×2 bands |
| h28v09 (Indonesia test tile) | `MYD13Q1.A2026281.h28v09.061.2026300164059` | HTTP 200 | HTTP 200, valid decoded 2×2 bands |

The checks requested tiny center-of-tile windows to verify actual band delivery, rather than compute AOI statistics. Each NetCDF4 response was 18,126 bytes; metadata plus data took approximately 13.65 seconds and 5.30 seconds respectively, excluding prior shared authentication. Decoded sample values are recorded in [recent Aqua data checks](benchmarks/laads-recent-aqua-data.json). This demonstrates access to these recent files, not guaranteed global freshness or archive completeness.

## Like-for-like pipeline comparison and provider recommendation

A subsequent prototype compared the full small-area pipeline for the original Rwanda rectangle and January 1–20, 2023, covering Terra January 1 and 17 plus Aqua January 9. Both providers used the existing monthly pixel median and exactextract mean/fractional count; cropland masking was disabled. No application source-subset or final-result cache was used. Imports were excluded from both timings, and OS/server caches were uncontrolled.

| Provider/run | End-to-end time | Notes |
|---|---:|---|
| LAADS first | 12.29 s | Authentication 4.56 s; concurrent discovery 0.86 s; subset/decode 6.82 s |
| Planetary Computer contemporaneous run | 5.13 s | Discovery and full pixel materialization 5.08 s |
| LAADS repeat in fresh process | 20.27 s | Authentication 9.80 s; discovery 4.43 s; subset/decode 6.00 s |

LAADS transferred 65,491 bytes across the three source observations in each run. Each provider's final monthly mean and fractional count matched the earlier reference within `rtol=1e-6, atol=1e-8`. These are exploratory timings, not a statistical performance ranking or country-scale benchmark. The LAADS prototype derives the known MOD13Q1 native grid from tile identifiers and does not represent a production adapter with complete validation and multi-tile mosaicking.

Records: [LAADS first](benchmarks/laads-pipeline-first.json), [PC comparison](benchmarks/pc-pipeline-comparison.json), [LAADS repeat](benchmarks/laads-pipeline-repeat.json). The [comparison prototype](benchmarks/laads_comparison_prototype.py) preserves the measured approach and includes output assertions; run from the repository root with `--provider laads` or `--provider pc` and a unique `--label`. Its area, dates, and reference CSV are intentionally fixed for this research experiment.

Recommendation: expose LAADS as an explicit provider option. For Evy's requirement to retrieve recent MODIS observations independently of GEE, LAADS is the preferred intended default because the tested current Aqua files were available there and absent from PC. PC remains a useful selectable provider for convenient access without NASA login and was faster in the latest small-area comparison. Switching the default should follow a representative country/year test with cropland masking and a production adapter. The public provider API and default have not been changed by this comparison; `provider="laads"` is a proposed option, not an implemented one.
