# Troubleshooting

This page lists common errors you may hit while using evy, organized by the error message or symptom you see. Each entry has the same three parts: **Symptom**, **Cause**, and **Fix**.

If your issue isn't here, please [open an issue](https://github.com/datapartnership/evy/issues).

---

## "Please authorize access to your Earth Engine account"

**Symptom:** When you call any GEE-backed function, Python raises `ee.EEException: Please authorize access to your Earth Engine account by running: earthengine authenticate`.

**Cause:** The current Python environment has never authenticated with Google Earth Engine, or the stored credentials have expired.

**Fix:**

```python
import evy
evy.authenticate()
```

This opens a browser window where you sign in. The resulting token is cached and reused automatically on subsequent runs. Alternatively, set the `GEE_PROJECT` environment variable to your Earth Engine project ID before starting Python.

---

## "Earth Engine API has not been used in project"

**Symptom:** `ee.EEException: Earth Engine API has not been used in project <your-project> before or it is disabled.`

**Cause:** The Google Cloud project you're authenticated to has not been registered for Earth Engine access.

**Fix:** Go to [code.earthengine.google.com](https://code.earthengine.google.com), sign in with the same Google account, and follow the prompt to register your project for Earth Engine. After registration, rerun `evy.authenticate()`.

---

## "Computation timed out" or "User memory limit exceeded"

**Symptom:** `zonal_stats` hangs or raises an `ee.EEException` mentioning computation timeouts or memory limits, typically for multi-year analyses over large countries.

**Cause:** Synchronous GEE queries are subject to memory and time limits. Large analyses exceed those limits and must be run as export tasks instead.

**Fix:** Add `export_to_drive=True` to the call. evy returns a task ID instead of a DataFrame; the results are written to your Google Drive when the task finishes.

```python
task_id = evy.zonal_stats(
    boundaries=gdf,
    zone_col="shapeName",
    start_date="2000-01-01",
    end_date="2024-12-31",
    export_to_drive=True,
    drive_folder="evy_exports",
)
evy.check_task_status(task_id)
```

---

## "not recognized as a supported file format" (local backend, macOS)

**Symptom:** When using the `earthaccess` local backend on macOS, `rasterio.errors.RasterioIOError: '...hdf' not recognized as a supported file format` on MODIS HDF4 files.

**Cause:** pip-installed `rasterio` / GDAL on macOS does not include the HDF4 driver. Homebrew GDAL also lacks HDF4 support, and `pyhdf` fails to build on recent Python versions.

**Fix:** Use the default Planetary Computer backend, which serves Cloud-Optimized GeoTIFFs instead of HDF4:

```python
evy.zonal_stats(..., backend="local", source="modis")
```

If you specifically need the NASA Earthdata path, evy's `earthaccess` backend streams MODIS bands via OPeNDAP (NetCDF4) rather than downloading HDF4, which sidesteps the driver problem entirely. Use it only if Planetary Computer does not host the data you need.

---

## `earthaccess` login prompts repeatedly

**Symptom:** Every Python session asks for NASA Earthdata credentials again.

**Cause:** Credentials are not persisted to `~/.netrc`.

**Fix:** Log in once with `persist=True`:

```python
import earthaccess
earthaccess.login(persist=True)
```

Subsequent `evy` calls that use the `earthaccess` backend will pick up the persisted credentials automatically.

---

## Stale GeoBoundaries data

**Symptom:** `get_boundaries` returns the same polygons even after GeoBoundaries has published an updated release.

**Cause:** evy caches GeoBoundaries responses under `~/.evy/boundaries/` for faster subsequent access. The cache does not auto-invalidate.

**Fix:**

```python
evy.clear_cache()            # clear all cached countries
evy.clear_cache(iso3="KEN")  # clear a single country
```

Or manually delete `~/.evy/boundaries/` from your filesystem.

---

## Stale cached zonal statistics

**Symptom:** `cached_zonal_stats` returns an older result after upstream data or code has changed.

**Cause:** Results are cached by input parameters and boundary content. The cache cannot detect changes in remote datasets or evy's implementation.

**Fix:** Clear the zonal-statistics cache and run the request again:

```python
evy.clear_zonal_cache()
```

Pass `cache_dir=` to either function if you use a custom cache location.

---

## "No boundaries found for <ISO3> ADM<N>"

**Symptom:** `get_boundaries` raises `ValueError: No boundaries found for XYZ ADM2. Check ISO3 code and admin level.`

**Cause:** Either the ISO3 country code is wrong or the requested admin level is not published for that country. GeoBoundaries coverage varies — not every country has ADM2 or ADM3 data.

**Fix:** Verify the ISO3 code against the [ISO 3166-1 alpha-3 list](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-3). If the code is correct, try a lower `admin_level`:

```python
evy.get_boundaries("KEN", admin_level=1)  # provinces, available for most countries
```

---

## Local backend runs out of memory on large regions

**Symptom:** The Python process is killed by the OS, or you see `dask` memory warnings when running `zonal_stats(backend="local", ...)` over a country-sized region.

**Cause:** The local backend downloads raster tiles covering the full bounding box. For large countries over many years, this can easily exceed the RAM available to Dask.

**Fix:** Pick one of:

- Process smaller admin units in a loop (e.g., iterate over ADM1 polygons instead of passing the whole country at once).
- Shorten the date range and process a few years at a time, concatenating results.
- Switch to the GEE backend, which computes server-side and does not download rasters to your machine.

```python
evy.zonal_stats(..., backend="gee")  # runs on Google's infrastructure
```
