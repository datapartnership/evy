# Design Decisions

This page documents the methodological choices baked into evy's defaults: which index, which satellite product, which masks, and which aggregations. It is intended to give researchers the justification they need to defend evy's outputs in a paper or report. Each section ends with a citable anchor.

## Why EVI and not NDVI

The Enhanced Vegetation Index (EVI) uses three bands (blue, red, near-infrared) plus a soil-adjustment factor and two atmospheric-resistance coefficients, whereas NDVI uses only red and NIR. The practical consequence is that EVI is less prone to saturation over dense canopies and less sensitive to aerosol contamination over land. For agricultural and vegetation-health monitoring in cloudy or dusty regions, EVI gives a more faithful signal. NDVI is still a reasonable choice for historical comparisons or for sensors that lack a blue band, but evy does not expose NDVI as a primary output.

*Primary source: [Huete et al. (2002), “Overview of the radiometric and biophysical performance of the MODIS vegetation indices”](https://doi.org/10.1016/S0034-4257(02)00096-2).*

## Which MODIS product

For the GEE backend, evy merges **MOD13Q1** (Terra) and **MYD13Q1** (Aqua): two 16-day, 250 m products offset to provide observations roughly every eight days after Aqua begins in July 2002. Before then, only Terra observations are available. The local Planetary Computer backend currently reads the `modis-13Q1-061` collection, so backend choice also determines whether Aqua observations are included.

*Primary source: the [MOD13 User Guide](https://lpdaac.usgs.gov/documents/103/MOD13_User_Guide_V6.pdf).*

## Quality masking

Quality masking differs with the data delivery path. The GEE backend retains good or marginal pixels according to both `SummaryQA` and the VI-quality bits in `DetailedQA`, and removes pixels carrying the snow/ice flag. The local backend uses the Planetary Computer `pixel_reliability` band and retains values 0 (good) and 1 (marginal), masking snow/ice and cloudy pixels. Masking happens before temporal and zonal aggregation.

## Cropland masking is on by default

When ``mask_cropland=True`` (the default), evy restricts the analysis to pixels classified as cropland. The source of the cropland mask depends on the backend:

- **GEE backend:** Dynamic World (Brown et al., 2022), class 4 (crops).
- **Local backend:** ESA WorldCover v200, class 40 (cropland).

These two products do not always agree at the pixel level because they are derived from different sensors with different training data. For paper-ready methodology sections, state which backend was used and cite the corresponding source. If you are comparing results across backends, be aware that a portion of any difference will come from the mask rather than the EVI signal itself. Pass ``mask_cropland=False`` to disable the mask and aggregate over all pixels in the zone.

*Primary sources: [Brown et al. (2022), Dynamic World](https://doi.org/10.1038/s41597-022-01307-4) and [ESA WorldCover](https://esa-worldcover.org/).*

## Monthly aggregation is the default frequency

The default temporal frequency for ``zonal_stats`` is monthly (`"ME"`). The output date is the first day of each calendar month despite the pandas-style alias. Monthly summaries align with common agricultural and food-security reporting cycles while smoothing the source composites into a regular series. The requested statistic controls the spatial summary; temporal aggregation uses the backend's monthly composite. Use ``freq="Original"`` when you need every source observation for phenology work, ``"QE"`` for quarterly summaries, and ``"YE"`` for annual summaries.

## TIMESAT-style phenology

evy's phenology module implements a lightweight version of the TIMESAT preprocessing-and-extraction pipeline: outlier removal against a rolling median, Savitzky-Golay smoothing, and amplitude-threshold detection of the start, middle, and end of the growing season. The implementation is a Python port of the algorithmic ideas, not a bit-exact reproduction of the TIMESAT software. For papers that require strict TIMESAT reproducibility, use the original Fortran TIMESAT software and cite it directly.

*Primary source: [Jönsson & Eklundh (2004), “TIMESAT — a program for analyzing time-series of satellite sensor data”](https://doi.org/10.1016/j.compag.2004.05.006).*

## Coordinate reference system

evy defaults to **EPSG:4326** (WGS 84 geographic coordinates) for all inputs and outputs. This is the CRS GeoBoundaries ships by default and the one most researchers expect from a lat/lon workflow. Some internal operations reproject transiently to EPSG:3857 (Web Mercator) for compatibility with Earth Engine defaults, but you do not see that CRS in any returned GeoDataFrame. If you need a different CRS in your outputs, reproject after calling evy.
