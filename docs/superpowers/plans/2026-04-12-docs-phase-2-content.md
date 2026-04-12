# Documentation Site — Phase 2 (Content) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the three content-bearing pages deferred from Phase 1: two fully-written reference pages (`docs/troubleshooting.md`, `docs/design-decisions.md`) and docstring polish for three public functions that render thin in the API reference (`load_modis`, `load_landcover`, `preprocess_series`). After this plan, the site's Reference tier is complete.

**Architecture:** Prose + code edits only. No new dependencies, no build configuration changes. The Jupyter Book scaffold from Phase 1 renders these pages automatically.

**Tech Stack:** MyST Markdown, NumPy-style docstrings.

**Scope note:** This plan implements Phase 2 of the design spec at `docs/superpowers/specs/2026-04-10-documentation-design.md`. Phase 1 (foundation) is already complete on this branch (see commits `d3c17f4` through `c0c0881`). Phase 3 (5 cookbook recipes) and Phase 4 (README + CLAUDE.md housekeeping) will get their own plans.

**Pre-flight:** Confirm you are on branch `update-quickstart` and that the Phase 1 commits exist in `git log`. The working tree has unrelated in-progress changes in `.gitignore`, `notebooks/quickstart.ipynb`, `src/evy/_process.py`, `src/evy/load.py`, and deleted `docs/*.md` template files — **these must not be bundled into any commits**. All tasks stage files by explicit path. Note that `src/evy/load.py` is already in the "modified but not staged" set; Task 1 modifies the same file, so be careful to commit only the docstring diff in Task 1 without accidentally grabbing whatever is in the current unstaged diff.

**Content authority note:** Aldo is the domain expert. The troubleshooting and design-decisions content in this plan is a *best-effort draft* written by the controller agent. Commit it as-written, then invite Aldo to review and request edits in a follow-up pass. Do not improvise alternative content.

---

## Task 1: Polish `load_modis` and `load_landcover` docstrings

**Files:**
- Modify: `src/evy/load.py:16-33` (for `load_modis`)
- Modify: `src/evy/load.py:71-86` (for `load_landcover`)

**Handling the pre-existing working-tree change to `load.py`:**

`src/evy/load.py` already has unstaged modifications in the working tree. Your edit will be layered on top of whatever those changes are. You must commit only the lines you add, not the pre-existing modifications.

Approach:
1. Before editing, run `git diff src/evy/load.py` and make a note of which lines are already modified.
2. Apply your docstring edits.
3. Use `git add -p src/evy/load.py` (or equivalently `git add --patch`) to interactively stage ONLY your docstring hunks, not the pre-existing ones.
4. Verify with `git diff --cached src/evy/load.py` that the staged diff contains only docstring lines.

If `git add -p` is unavailable or confusing, an alternative is:
1. Stash the pre-existing changes: `git stash push -- src/evy/load.py`
2. Apply your docstring edit to the clean file
3. Stage and commit normally: `git add src/evy/load.py && git commit ...`
4. Restore the pre-existing changes: `git stash pop`

Either approach works. Pick the one you're comfortable with.

- [ ] **Step 1: Inspect the current state of the file**

Run:
```bash
git diff src/evy/load.py
```

Note what is already modified so you don't bundle it into your commit.

- [ ] **Step 2: Replace the `load_modis` docstring**

Find the current docstring (lines 16–33 of the committed file, possibly shifted by the unstaged diff). It currently reads:

```python
"""
Load MODIS EVI and quality bands from STAC items.

Parameters
----------
boundaries : gpd.GeoDataFrame
    GeoDataFrame containing zone boundaries, used to determine
    the bounding box for the STAC search.
start_date : str
    Start date in ISO format (YYYY-MM-DD).
end_date : str
    End date in ISO format (YYYY-MM-DD).

Returns
-------
xr.Dataset
    Lazy Dataset with 'evi_raw' and 'qa' variables.
"""
```

Replace it with:

```python
"""
Load MODIS EVI and quality bands from a STAC catalog.

Searches the Microsoft Planetary Computer STAC endpoint for MOD13Q1
(MODIS Terra 16-day, 250m) items intersecting the boundary bounding
box and opens them lazily via ``odc-stac``. The returned Dataset is
Dask-backed; no pixels are materialized until you call ``.compute()``
or reduce over the data.

Parameters
----------
boundaries : gpd.GeoDataFrame
    Zone boundaries used to derive the STAC search bounding box. Any
    CRS is accepted; only the total bounds are used.
start_date : str
    Inclusive start date as an ISO string (YYYY-MM-DD).
end_date : str
    Inclusive end date as an ISO string (YYYY-MM-DD).

Returns
-------
xr.Dataset
    Lazy Dataset with two variables:

    - ``evi_raw`` : int16 EVI values (scaled ×10000 per MODIS convention)
    - ``qa`` : pixel reliability (0=good, 1=marginal, 2=snow/ice, 3=cloudy)

    Both are indexed by ``(time, y, x)`` with chunks of ``{x: 2048,
    y: 2048, time: 1}``.

Raises
------
RuntimeError
    If the STAC catalog is unreachable or returns no items for the
    requested bbox and date range.

Examples
--------
>>> import evy
>>> gdf = evy.get_boundaries('KEN', admin_level=1)
>>> ds = evy.load_modis(gdf, '2023-01-01', '2023-12-31')
>>> ds.evi_raw.sizes
{'time': 23, 'y': ..., 'x': ...}
"""
```

- [ ] **Step 3: Replace the `load_landcover` docstring**

Find the current docstring. It currently reads:

```python
"""
Load MODIS land cover band from STAC items. The package currently only supports loading land cover for a single period,
so the start and end dates are fixed to a single time.

Parameters
----------
boundaries : gpd.GeoDataFrame
    GeoDataFrame containing the zone boundaries, used to determine the bounding box for loading land cover data.
ds_evi : xr.Dataset
    Dataset containing the EVI data, used to align the land cover data.

Returns
-------
xr.Dataset
    Lazy Dataset with 'land_cover' variable.
"""
```

Replace it with:

```python
"""
Load an ESA WorldCover land cover raster aligned to an EVI dataset.

Searches the Microsoft Planetary Computer STAC endpoint for the
``esa-worldcover`` collection over the boundary bounding box and
reprojects the result to match the grid of ``ds_evi`` using nearest-
neighbor (mode) resampling. Only a single timestep is loaded, because
WorldCover is a static (annual) product.

Parameters
----------
boundaries : gpd.GeoDataFrame
    Zone boundaries used to derive the STAC search bounding box.
ds_evi : xr.Dataset
    An EVI Dataset (typically from :func:`load_modis`) whose grid the
    land cover layer should be aligned to.

Returns
-------
xr.DataArray
    Eager (computed) DataArray of WorldCover class codes, indexed by
    ``(y, x)``. Class code 40 is cropland; see the ESA WorldCover
    documentation for the full legend.

Examples
--------
>>> import evy
>>> gdf = evy.get_boundaries('KEN', admin_level=1)
>>> ds = evy.load_modis(gdf, '2023-01-01', '2023-12-31')
>>> lc = evy.load_landcover(gdf, ds)
>>> cropland_mask = (lc == 40)
"""
```

Note: the original return type in the body was `xr.Dataset` but the actual return is `wc["map"].isel(time=0).compute()` which is an `xr.DataArray`. The new docstring corrects this.

- [ ] **Step 4: Verify only docstring lines are modified**

Run:
```bash
git diff src/evy/load.py
```

The diff should show your docstring changes plus whatever pre-existing modifications were already in the file. That's expected — the next step isolates your changes from the existing ones.

- [ ] **Step 5: Stage only the docstring hunks**

Run one of the two approaches described in the pre-flight notes:

**Approach A (interactive patch):**
```bash
git add -p src/evy/load.py
```
Press `y` to stage docstring hunks, `n` to skip pre-existing hunks.

**Approach B (stash workaround):**
```bash
git stash push -- src/evy/load.py
# now re-apply your docstring changes to the clean file
# (use your editor)
git add src/evy/load.py
# commit in Step 7; restore the stash after Task 2
```

- [ ] **Step 6: Verify the staged diff contains only docstring changes**

Run:
```bash
git diff --cached src/evy/load.py | head -100
```

Expected: the staged diff should touch only docstring lines (triple-quoted strings inside `load_modis` and `load_landcover`). No code logic should appear.

If code-logic hunks appear in the staged diff, unstage them with `git restore --staged src/evy/load.py` and retry.

- [ ] **Step 7: Commit**

```bash
git commit -m "Expand docstrings for load_modis and load_landcover"
```

- [ ] **Step 8: If Approach B was used, restore the stashed changes**

```bash
git stash pop
```

Confirm `git status` shows the pre-existing `load.py` modifications are back in the working tree.

---

## Task 2: Polish `preprocess_series` docstring

**Files:**
- Modify: `src/evy/phenology.py:19-48` (for `preprocess_series`)

`src/evy/phenology.py` has **no** pre-existing unstaged modifications, so this task is a straight edit and commit.

- [ ] **Step 1: Inspect the current docstring**

Run:
```bash
sed -n '19,48p' src/evy/phenology.py
```

- [ ] **Step 2: Replace the docstring**

Find the current docstring. It starts at line 25 and reads:

```python
"""
TIMESAT-style preprocessing for vegetation index time series.

Applies the following steps:
1. Remove outliers using median filter (values > std * multiplier from rolling median)
2. Interpolate missing values linearly
3. Smooth using Savitzky-Golay filter

Parameters
----------
series:
    Time series of vegetation index values
window_length:
    Window length for Savitzky-Golay filter (must be odd)
polyorder:
    Polynomial order for Savitzky-Golay filter
outlier_std_multiplier:
    Multiplier for standard deviation to identify outliers

Returns
-------
np.ndarray
    Smoothed time series values
"""
```

Replace it with:

```python
"""
TIMESAT-style preprocessing for vegetation index time series.

Applies three sequential steps in the TIMESAT tradition:

1. Outlier removal — values that deviate from the rolling median by
   more than ``outlier_std_multiplier`` times the series standard
   deviation are masked and then interpolated.
2. Linear interpolation to fill remaining gaps in both directions.
3. Savitzky-Golay smoothing of the filled series.

The implementation is a lightweight Python port of the preprocessing
stage of the original TIMESAT software (Jönsson & Eklundh 2004), not
a bit-exact reproduction.

Parameters
----------
series : pd.Series
    Time series of vegetation index values. Missing values (NaN) are
    allowed and will be interpolated.
window_length : int, default 5
    Window length for the Savitzky-Golay filter. Must be odd; if an
    even value is passed, it is decremented internally to the next odd
    number. Clamped to at least 3.
polyorder : int, default 2
    Polynomial order for the Savitzky-Golay filter. Must be less than
    ``window_length``.
outlier_std_multiplier : float, default 2.0
    Threshold (in standard deviations) above which a value is treated
    as an outlier and masked.

Returns
-------
np.ndarray
    Smoothed values as a float array, same length as the input series.

Raises
------
ImportError
    If ``scipy`` is not installed. ``scipy`` is a core dependency of
    evy, so this error should not arise in normal installations, but
    the check is retained for users who have installed evy into an
    environment with stripped dependencies.
"""
```

- [ ] **Step 3: Verify the edit**

Run:
```bash
git diff src/evy/phenology.py
```

Expected: the diff shows only the docstring replacement, nothing else.

- [ ] **Step 4: Stage and commit**

```bash
git add src/evy/phenology.py
git commit -m "Expand preprocess_series docstring with Raises section"
```

---

## Task 3: Write `docs/troubleshooting.md` content

**Files:**
- Modify: `docs/troubleshooting.md` (currently a stub from Phase 1)

- [ ] **Step 1: Replace the stub with full content**

Overwrite `docs/troubleshooting.md` with this exact content:

````markdown
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
````

- [ ] **Step 2: Verify the file was written**

Run:
```bash
wc -l docs/troubleshooting.md
grep -c '^## ' docs/troubleshooting.md
```

Expected: `wc -l` prints a line count around 150–180. `grep -c '^## '` prints `8` (eight top-level entries).

- [ ] **Step 3: Stage and commit**

```bash
git add docs/troubleshooting.md
git commit -m "Write troubleshooting content with eight common errors"
```

---

## Task 4: Write `docs/design-decisions.md` content

**Files:**
- Modify: `docs/design-decisions.md` (currently a stub from Phase 1)

**Word budget:** The spec caps this page at 1000 words hard, targeting ~800. The content below lands in that window. Do not expand it during implementation.

- [ ] **Step 1: Replace the stub with full content**

Overwrite `docs/design-decisions.md` with this exact content:

````markdown
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
````

- [ ] **Step 2: Verify word count is within budget**

Run:
```bash
wc -w docs/design-decisions.md
```

Expected: a number between 700 and 1000. If it's over 1000, the content above exceeds the hard cap — flag this before committing and do not expand further.

- [ ] **Step 3: Verify section structure**

Run:
```bash
grep -c '^## ' docs/design-decisions.md
```

Expected: `7` (seven top-level sections, matching the spec).

- [ ] **Step 4: Stage and commit**

```bash
git add docs/design-decisions.md
git commit -m "Write design decisions page covering seven methodological choices"
```

---

## Task 5: Rebuild the book and verify new content renders

**Goal:** Run a full build and confirm the new Phase 2 content shows up in the rendered HTML.

- [ ] **Step 1: Clean stale build artifacts**

Run:
```bash
rm -rf _build docs/_build
```

- [ ] **Step 2: Run the build**

Run:
```bash
make build
```

Expected: `build succeeded` in the final lines. The warning count may differ from Phase 1 but should not include new ERROR-level messages about the three files this plan changed.

- [ ] **Step 3: Verify troubleshooting content rendered**

Run:
```bash
grep -c 'Earth Engine' _build/html/docs/troubleshooting.html
grep -c 'HDF4' _build/html/docs/troubleshooting.html
```

Expected: both counts are at least `1`. The first confirms the GEE-related entries rendered; the second confirms the HDF4-on-macOS entry rendered.

- [ ] **Step 4: Verify design-decisions content rendered**

Run:
```bash
grep -c 'MOD13Q1' _build/html/docs/design-decisions.html
grep -c 'TIMESAT' _build/html/docs/design-decisions.html
grep -c 'cropland' _build/html/docs/design-decisions.html
```

Expected: each count is at least `1`.

- [ ] **Step 5: Verify the polished docstrings rendered in the API reference**

Run:
```bash
grep -c 'Cloud-Optimized\|MOD13Q1 (MODIS Terra' _build/html/docs/api-reference.html
grep -c 'TIMESAT tradition\|ImportError' _build/html/docs/api-reference.html
```

Expected: the first count is `>= 1` (confirms `load_modis` docstring polish rendered). The second count is `>= 1` (confirms `preprocess_series` polish rendered).

If any verification step fails, inspect the rendered HTML file directly to see what actually rendered and diagnose.

- [ ] **Step 6: No file changes to commit in this task**

Task 5 is verification only. Confirm via `git status` that no new modifications appear. The `_build/` directory is gitignored.

---

## Done

When every task box above is checked and Task 5 passes, Phase 2 is complete. The site's Reference tier is fully populated; the only remaining work for a complete docs site is Phase 3 (cookbook recipes) and Phase 4 (housekeeping).

**Deliberately not done in this plan** (goes into Phase 3 or Phase 4):

- Any cookbook recipe notebook
- README cleanup (anomaly detection feature claim)
- CLAUDE.md stale-path fix
- New API surface (e.g., `calculate_anomaly`)
