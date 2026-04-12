# Design Decisions

This page documents the methodological choices baked into evy's defaults: which index, which satellite product, which masks, and which aggregations. It is intended to give researchers the justification they need to defend evy's outputs in a paper or report. Each section ends with a citable anchor.

## Why EVI and not NDVI

The Enhanced Vegetation Index (EVI) uses three bands (blue, red, near-infrared) plus a soil-adjustment factor and two atmospheric-resistance coefficients, whereas NDVI uses only red and NIR. The practical consequence is that EVI is less prone to saturation over dense canopies and less sensitive to aerosol contamination over land. For agricultural and vegetation-health monitoring in cloudy or dusty regions, EVI gives a more faithful signal. NDVI is still a reasonable choice for historical comparisons or for sensors that lack a blue band, but evy does not expose NDVI as a primary output.

*If you are citing this choice in a paper, the primary source is Huete et al. (2002), "Overview of the radiometric and biophysical performance of the MODIS vegetation indices."*

## Which MODIS product

evy's default MODIS product is **MOD13Q1**: 16-day composites from Terra at 250 m spatial resolution. Terra has been operational since February 2000, giving a ~25-year continuous record that spans longer than any alternative MODIS VI product. The companion product MYD13Q1 (Aqua, same cadence) is available from mid-2002 and can be substituted if you need observations from the afternoon overpass, but Terra is evy's default because of the record length.

*Primary source: the MODIS MOD13 User Guide (Didan et al., current revision).*

## Quality masking

MOD13Q1 ships a per-pixel ``pixel_reliability`` band with four values: 0 (good data), 1 (marginal data), 2 (snow/ice), and 3 (cloudy). evy retains pixels with reliability 0 or 1 and masks the rest to NaN before any aggregation (see ``evy._process.apply_quality_mask``). This matches the "Rank 1" recommendation in the MOD13 user guide for typical land-monitoring workflows. If you need a stricter mask (e.g., only reliability 0), apply it downstream of evy's outputs.

## Cropland masking is on by default

When ``mask_cropland=True`` (the default), evy restricts the analysis to pixels classified as cropland. The source of the cropland mask depends on the backend:

- **GEE backend:** Dynamic World (Brown et al., 2022), class 4 (crops).
- **Local backend:** ESA WorldCover v200, class 40 (cropland).

These two products do not always agree at the pixel level because they are derived from different sensors with different training data. For paper-ready methodology sections, state which backend was used and cite the corresponding source. If you are comparing results across backends, be aware that a portion of any difference will come from the mask rather than the EVI signal itself. Pass ``mask_cropland=False`` to disable the mask and aggregate over all pixels in the zone.

## Monthly aggregation is the default frequency

The default temporal frequency for ``zonal_stats`` is ``"ME"`` (month-end). This reflects two constraints. First, MOD13Q1 composites are already 16-day, so sub-monthly aggregation gives at most two data points per period — often one — and does not improve signal. Second, monthly totals align with most agricultural and food-security reporting cycles, making evy's outputs directly comparable to climate and yield statistics. Use ``freq="D"`` when you need daily interpolation for phenology work, ``"QE"`` for quarterly summaries, and ``"YE"`` for annual means.

## TIMESAT-style phenology

evy's phenology module implements a lightweight version of the TIMESAT preprocessing-and-extraction pipeline: outlier removal against a rolling median, Savitzky-Golay smoothing, and amplitude-threshold detection of the start, middle, and end of the growing season. The implementation is a Python port of the algorithmic ideas, not a bit-exact reproduction of the TIMESAT software. For papers that require strict TIMESAT reproducibility, use the original Fortran TIMESAT software and cite it directly.

*Primary source: Jönsson & Eklundh (2004), "TIMESAT — a program for analyzing time-series of satellite sensor data."*

## Coordinate reference system

evy defaults to **EPSG:4326** (WGS 84 geographic coordinates) for all inputs and outputs. This is the CRS GeoBoundaries ships by default and the one most researchers expect from a lat/lon workflow. Some internal operations reproject transiently to EPSG:3857 (Web Mercator) for compatibility with Earth Engine defaults, but you do not see that CRS in any returned GeoDataFrame. If you need a different CRS in your outputs, reproject after calling evy.
