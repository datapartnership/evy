# LAADS subset fixture

`laads-aqua-subset.nc4` is an unscaled EVI + pixel-reliability subset of NASA
MYD13Q1 v061 granule `MYD13Q1.A2023009.h20v09.061.2023026194807`.
It contains source rows 864–912 and columns 4552–4600, inclusive, delivered by
[NASA LAADS OPeNDAP](https://ladsweb.modaps.eosdis.nasa.gov/learn/using-laads-apis/).
It is public scientific data with no credentials or signed URLs.
Product: [MYD13Q1 v061 DOI](https://doi.org/10.5067/MODIS/MYD13Q1.061).

The fixture exercises the real GDAL NetCDF reader offline. Transport is stubbed;
adjacent-tile tests deliberately reuse its pixel values to test mosaicking.
