# Documentation Site — Phase 3 (Cookbook) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the five cookbook recipe notebooks specified in the design spec. Each recipe = one axis of variation from the quickstart. After this plan, every non-utility symbol in `__all__` is exercised at least once across the quickstart + recipes. The Cookbook section in the sidebar becomes live.

**Architecture:** Jupyter notebooks (`.ipynb`) with baked outputs, plus a one-line edit to `docs/_toc.yml` to uncomment the Cookbook section.

**Tech Stack:** Python, Jupyter, evy API, Altair (for visualizations).

**Scope note:** This plan implements Phase 3 of the design spec at `docs/superpowers/specs/2026-04-10-documentation-design.md`. Phases 1 (foundation) and 2 (content) are complete on branch `update-quickstart`. Phase 4 (housekeeping) will get its own plan.

**Pre-flight:**
- Confirm you are on branch `update-quickstart` and that Phase 1+2 commits exist in `git log`.
- The working tree has unrelated in-progress changes in `.gitignore`, `notebooks/quickstart.ipynb`, `src/evy/_process.py`, `src/evy/load.py`, and deleted `docs/*.md` template files — **these must not be bundled into any commits**. All tasks stage files by explicit path.
- Notebooks must be **executed and saved with baked outputs** before committing. The build uses `execute_notebooks: off`, so the outputs you save are the outputs readers see. If a GEE-authenticated environment is not available, use the local backend for recipes 1–4 wherever possible. Recipe 5 specifically targets the local backend.
- The quickstart uses San Marino (`SMR`) as its demo country. Recipes should use **different countries** so they feel like new analyses, not reruns. Suggested countries below are chosen for being small (fast GEE queries) with good MODIS coverage.

**Country choices for recipes:**

| Recipe | Country | Why |
|--------|---------|-----|
| 1. Monthly aggregation | Rwanda (`RWA`) | Small, equatorial, clear seasonal signal |
| 2. Cropland masking | Kenya (`KEN`, ADM1) | Varied land cover, good cropland contrast |
| 3. Multi-country comparison | Rwanda, Burundi, Uganda (`RWA`, `BDI`, `UGA`) | Neighbors, same latitude band |
| 4. Phenology extraction | Rwanda (`RWA`) | Reuses recipe 1 data, two growing seasons |
| 5. Local backend | Rwanda (`RWA`) | Small enough for local pipeline |

The implementer may substitute countries if GEE queries fail or if the outputs look uninteresting. The plan trusts the implementer's judgment on country choice.

---

## Task 1: Uncomment the Cookbook section in `_toc.yml`

**Files:**
- Modify: `docs/_toc.yml`

- [ ] **Step 1: Replace the commented-out Cookbook block**

In `docs/_toc.yml`, find:

```yaml
  # Cookbook section is empty until Phase 3 — commented out because Jupyter Book
  # rejects empty chapters lists. Uncomment and add recipe notebooks in Phase 3.
  # - caption: Cookbook
  #   chapters:
  #     - file: notebooks/recipes/...
```

Replace it with:

```yaml
  - caption: Cookbook
    chapters:
      - file: notebooks/recipes/monthly-aggregation
      - file: notebooks/recipes/cropland-masking
      - file: notebooks/recipes/multi-country-comparison
      - file: notebooks/recipes/phenology-extraction
      - file: notebooks/recipes/local-backend
```

The Cookbook section must appear between "Getting Started" and "Reference" in the `parts` list.

- [ ] **Step 2: Remove the `.gitkeep` placeholder**

```bash
rm notebooks/recipes/.gitkeep
```

This file was a placeholder from Phase 1. It is no longer needed once real notebooks exist. (Complete this step after Task 2, once the first notebook is in place, so the directory is never empty.)

- [ ] **Step 3: Do not commit yet**

This task is committed together with the first recipe notebook in Task 2 to avoid a broken intermediate state (TOC referencing files that don't exist).

---

## Task 2: Create `monthly-aggregation.ipynb`

**Files:**
- Create: `notebooks/recipes/monthly-aggregation.ipynb`

**Spec reference:** Recipe 1 — teaches the `freq` parameter and `stats` list.

**API functions exercised:** `get_boundaries`, `zonal_stats` (with `freq` and `stats`), `plot_time_series`.

This recipe departs from the quickstart in one dimension: it explicitly explores temporal frequency options and multiple statistics, whereas the quickstart uses defaults.

### Cell structure

Each cell below is either `markdown` or `code`. The implementer creates the notebook and executes it to bake outputs.

- [ ] **Cell 1 (markdown):**

```markdown
# Monthly Aggregation

This recipe shows how to control **temporal frequency** and **summary statistics** when computing EVI zonal statistics. The quickstart uses evy's defaults (`freq="ME"`, `stats="mean"`); here we vary both parameters to build a richer time series.

For setup instructions, see the [quickstart](../quickstart.ipynb).
```

- [ ] **Cell 2 (code):**

```python
import evy
```

- [ ] **Cell 3 (markdown):**

```markdown
## Load boundaries

We use Rwanda's 5 provinces (ADM1) as our analysis regions.
```

- [ ] **Cell 4 (code):**

```python
gdf = evy.get_boundaries("RWA", admin_level=1)
gdf[["shapeName", "shapeISO"]].head()
```

- [ ] **Cell 5 (markdown):**

```markdown
## Compute monthly statistics

The `freq` parameter accepts pandas offset aliases: `"D"` (daily), `"W"` (weekly), `"ME"` (month-end), `"QE"` (quarter-end), `"YE"` (year-end). evy also provides named constants for these: `evy.DAILY`, `evy.WEEKLY`, `evy.MONTHLY`, `evy.QUARTERLY`, `evy.YEARLY`.

The `stats` parameter takes a string or list: `"mean"`, `"median"`, `"min"`, `"max"`, `"std"`, `"sum"`, `"count"`.

Let's request monthly mean and standard deviation over three years:
```

- [ ] **Cell 6 (code):**

```python
df = evy.zonal_stats(
    gdf,
    zone_col="shapeName",
    start_date="2022-01-01",
    end_date="2024-12-31",
    freq=evy.MONTHLY,
    stats=["mean", "std"],
)
df.head(10)
```

- [ ] **Cell 7 (markdown):**

```markdown
## Visualize the time series

`plot_time_series` shows the EVI signal over time. With 3 years of monthly data, seasonal patterns become visible.
```

- [ ] **Cell 8 (code):**

```python
evy.plot_time_series(df, value_col="mean")
```

- [ ] **Cell 9 (markdown):**

```markdown
## Compare frequencies

To see the effect of temporal resolution, let's compute quarterly aggregation over the same period and plot both side by side.
```

- [ ] **Cell 10 (code):**

```python
df_quarterly = evy.zonal_stats(
    gdf,
    zone_col="shapeName",
    start_date="2022-01-01",
    end_date="2024-12-31",
    freq=evy.QUARTERLY,
    stats=["mean"],
)
df_quarterly.head()
```

- [ ] **Cell 11 (code):**

```python
evy.plot_time_series(df_quarterly, value_col="mean", title="EVI Time Series (Quarterly)")
```

- [ ] **Cell 12 (markdown):**

```markdown
Monthly data preserves the intra-seasonal shape (green-up and senescence), while quarterly data smooths it into broad trends. For agricultural monitoring, monthly (`"ME"`) is usually the best trade-off between resolution and noise — see [Design Decisions](../../docs/design-decisions.md) for the rationale.
```

- [ ] **Step: Execute the notebook and save with baked outputs**

Run the notebook end-to-end in a kernel with `evy` installed and GEE authenticated. Save the notebook with all cell outputs included.

- [ ] **Step: Stage and commit together with the TOC change**

```bash
git add docs/_toc.yml notebooks/recipes/monthly-aggregation.ipynb
git rm notebooks/recipes/.gitkeep
git commit -m "Add monthly-aggregation recipe and enable Cookbook in TOC"
```

---

## Task 3: Create `cropland-masking.ipynb`

**Files:**
- Create: `notebooks/recipes/cropland-masking.ipynb`

**Spec reference:** Recipe 2 — side-by-side comparison of `mask_cropland=True` vs `False`.

**API functions exercised:** `zonal_stats` (with `mask_cropland`), `plot_time_series`.

### Cell structure

- [ ] **Cell 1 (markdown):**

```markdown
# Cropland Masking

By default, evy restricts EVI statistics to cropland pixels (`mask_cropland=True`). This recipe compares masked vs. unmasked results to show the effect of the cropland filter on the EVI signal.

**Important for paper methodology:** The GEE backend uses Dynamic World (class 4) for its cropland mask, while the local backend uses ESA WorldCover (class 40). These products may disagree at the pixel level. When writing up your methodology, state which backend you used. See [Design Decisions](../../docs/design-decisions.md) for details.
```

- [ ] **Cell 2 (code):**

```python
import evy
```

- [ ] **Cell 3 (code):**

```python
gdf = evy.get_boundaries("KEN", admin_level=1)
gdf[["shapeName"]].head()
```

- [ ] **Cell 4 (markdown):**

```markdown
## With cropland masking (default)

This is the default behavior — only cropland pixels contribute to the zonal statistics.
```

- [ ] **Cell 5 (code):**

```python
df_masked = evy.zonal_stats(
    gdf,
    zone_col="shapeName",
    start_date="2023-01-01",
    end_date="2023-12-31",
    freq=evy.MONTHLY,
    stats=["mean"],
    mask_cropland=True,  # default, shown explicitly
)
df_masked.head()
```

- [ ] **Cell 6 (markdown):**

```markdown
## Without cropland masking

All land-cover types contribute — forest, grassland, urban, water, etc.
```

- [ ] **Cell 7 (code):**

```python
df_unmasked = evy.zonal_stats(
    gdf,
    zone_col="shapeName",
    start_date="2023-01-01",
    end_date="2023-12-31",
    freq=evy.MONTHLY,
    stats=["mean"],
    mask_cropland=False,
)
df_unmasked.head()
```

- [ ] **Cell 8 (markdown):**

```markdown
## Side-by-side comparison

Let's plot both series to see how the mask affects the seasonal signal.
```

- [ ] **Cell 9 (code):**

```python
evy.plot_time_series(df_masked, value_col="mean", title="EVI — Cropland Only")
```

- [ ] **Cell 10 (code):**

```python
evy.plot_time_series(df_unmasked, value_col="mean", title="EVI — All Land Cover")
```

- [ ] **Cell 11 (markdown):**

```markdown
In regions with mixed land cover, the unmasked signal typically shows lower amplitude because non-agricultural vegetation (forest, grassland) has different seasonal dynamics than crops. The difference is most pronounced in regions where cropland is a small fraction of total land area.

If you need a **custom** land-cover mask beyond cropland, you can use the low-level pipeline (`load_modis` → `load_landcover` → `compute_zonal_stats`) to inspect and modify the raster directly. See the [quickstart](../quickstart.ipynb) for an example of the low-level pipeline.
```

- [ ] **Step: Execute the notebook and save with baked outputs**

- [ ] **Step: Stage and commit**

```bash
git add notebooks/recipes/cropland-masking.ipynb
git commit -m "Add cropland-masking recipe comparing masked vs unmasked EVI"
```

---

## Task 4: Create `multi-country-comparison.ipynb`

**Files:**
- Create: `notebooks/recipes/multi-country-comparison.ipynb`

**Spec reference:** Recipe 3 — `_by_region` plot variants and `plot_choropleth`.

**API functions exercised:** `get_boundaries`, `zonal_stats`, `plot_time_series_by_region`, `plot_choropleth`.

**Note on `plot_choropleth`:** The function's default join keys are `geo_key="PCODE"` and `df_key="PCODE"`, but GeoBoundaries data does not have a `PCODE` column. The recipe must pass `geo_key="shapeName"` and `df_key="shapeName"` (or another shared column). The implementer should test this carefully — if `plot_choropleth` fails on the join, inspect the available columns and choose the correct key.

### Cell structure

- [ ] **Cell 1 (markdown):**

```markdown
# Multi-Country Comparison

This recipe compares EVI seasonality across neighboring countries. The quickstart analyzes a single country; here we loop over three East African countries to show cross-border patterns.

This recipe demonstrates `plot_time_series_by_region` (faceted time-series charts) and `plot_choropleth` (map colored by EVI values), which are in the public API but not covered in the quickstart.
```

- [ ] **Cell 2 (code):**

```python
import evy
import pandas as pd
```

- [ ] **Cell 3 (markdown):**

```markdown
## Load boundaries for three countries
```

- [ ] **Cell 4 (code):**

```python
countries = ["RWA", "BDI", "UGA"]
gdfs = {iso: evy.get_boundaries(iso, admin_level=1) for iso in countries}

# Add country column for later grouping
for iso, gdf in gdfs.items():
    gdf["country"] = iso
```

- [ ] **Cell 5 (markdown):**

```markdown
## Compute monthly EVI for each country

Each country is processed independently — evy does not mosaic across borders. We concatenate the results into a single DataFrame for visualization.
```

- [ ] **Cell 6 (code):**

```python
dfs = []
for iso, gdf in gdfs.items():
    df = evy.zonal_stats(
        gdf,
        zone_col="shapeName",
        start_date="2023-01-01",
        end_date="2023-12-31",
        freq=evy.MONTHLY,
        stats=["mean"],
    )
    df["country"] = iso
    dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)
df_all.head()
```

- [ ] **Cell 7 (markdown):**

```markdown
## Faceted time series by region

`plot_time_series_by_region` creates a small-multiples chart — one panel per region. Here we show the regions from one country:
```

- [ ] **Cell 8 (code):**

```python
df_rwa = df_all[df_all["country"] == "RWA"]
evy.plot_time_series_by_region(df_rwa, region_col="shapeName")
```

- [ ] **Cell 9 (markdown):**

```markdown
## Choropleth map

`plot_choropleth` colors each administrative unit by its mean EVI for a given period. We compute the annual mean across all months and map it.

**Note:** `plot_choropleth` joins the data DataFrame to the GeoDataFrame using a shared key column. GeoBoundaries data uses `shapeName` for region names — we pass that as both `geo_key` and `df_key`.
```

- [ ] **Cell 10 (code):**

```python
# Annual mean per region for Rwanda
df_rwa_annual = (
    df_rwa.groupby("shapeName", as_index=False)["mean"].mean()
)

evy.plot_choropleth(
    df_rwa_annual,
    gdfs["RWA"],
    value_col="mean",
    region_col="shapeName",
    geo_key="shapeName",
    df_key="shapeName",
    title="Mean EVI by Province — Rwanda 2023",
)
```

- [ ] **Cell 11 (markdown):**

```markdown
Each country is analyzed independently — evy does not stitch rasters or boundaries across borders. This is intentional: cross-border mosaicking introduces CRS alignment issues and complicates the methodology section of your paper. Compare the countries' results by placing their charts side by side, as shown above.
```

- [ ] **Step: Execute the notebook and save with baked outputs**

The implementer should verify that `plot_choropleth` renders correctly. If the join fails (empty map), inspect the column names in `gdfs["RWA"]` and `df_rwa_annual` and adjust `geo_key` / `df_key` accordingly.

- [ ] **Step: Stage and commit**

```bash
git add notebooks/recipes/multi-country-comparison.ipynb
git commit -m "Add multi-country comparison recipe with choropleth and faceted plots"
```

---

## Task 5: Create `phenology-extraction.ipynb`

**Files:**
- Create: `notebooks/recipes/phenology-extraction.ipynb`

**Spec reference:** Recipe 4 — the full phenology module.

**API functions exercised:** `zonal_stats`, `calculate_phenology`, `extract_phenology`, `preprocess_series`, `get_growing_season`, `filter_growing_season`, `plot_seasonality`, `plot_seasonality_by_region`.

This is the most function-dense recipe. It exercises the entire phenology pipeline that the quickstart only touches lightly (quickstart calls `calculate_phenology` and the visualization functions, but skips the lower-level `preprocess_series`, `extract_phenology`, and `get_growing_season`).

### Cell structure

- [ ] **Cell 1 (markdown):**

```markdown
# Phenology Extraction

This recipe walks through evy's **phenology module** — tools for identifying the Start of Season (SOS), Middle of Season (MOS), and End of Season (EOS) from EVI time series. The quickstart demonstrates `calculate_phenology` as a one-liner; here we unpack the full pipeline.

evy's phenology approach is based on [TIMESAT](https://web.nateko.lu.se/timesat/timesat.asp) (Jönsson & Eklundh 2004): Savitzky-Golay smoothing followed by amplitude-threshold detection. See [Design Decisions](../../docs/design-decisions.md) for the methodological rationale.

**Known limitation:** The current implementation assumes a single growing season per year. Regions with double cropping (e.g., irrigated rice) will show only the dominant season.
```

- [ ] **Cell 2 (code):**

```python
import evy
import numpy as np
```

- [ ] **Cell 3 (markdown):**

```markdown
## Step 1: Compute daily EVI

Phenology extraction works best with high-frequency data. We request daily interpolation (`freq="D"`) so that the smoothing step has enough data points to resolve the seasonal curve.
```

- [ ] **Cell 4 (code):**

```python
gdf = evy.get_boundaries("RWA", admin_level=1)
df = evy.zonal_stats(
    gdf,
    zone_col="shapeName",
    start_date="2023-01-01",
    end_date="2023-12-31",
    freq=evy.DAILY,
    stats=["mean"],
)
print(f"{len(df)} rows, {df['shapeName'].nunique()} regions")
df.head()
```

- [ ] **Cell 5 (markdown):**

```markdown
## Step 2: High-level phenology — `calculate_phenology`

The simplest path. One call aggregates to monthly values, smooths them, and extracts SOS/MOS/EOS.
```

- [ ] **Cell 6 (code):**

```python
phenology = evy.calculate_phenology(df, value_col="mean")
phenology
```

- [ ] **Cell 7 (code):**

```python
evy.plot_seasonality(phenology)
```

- [ ] **Cell 8 (markdown):**

```markdown
## Step 3: Per-region phenology

Pass `group_col` to compute phenology per administrative unit. Regions with different climates or cropping calendars will show different season timing.
```

- [ ] **Cell 9 (code):**

```python
phenology_by_region = evy.calculate_phenology(
    df, value_col="mean", group_col="shapeName"
)
phenology_by_region.head(12)
```

- [ ] **Cell 10 (code):**

```python
evy.plot_seasonality_by_region(phenology_by_region, region_col="shapeName")
```

- [ ] **Cell 11 (markdown):**

```markdown
## Step 4: Under the hood — `preprocess_series` and `extract_phenology`

`calculate_phenology` is a convenience wrapper. Under the hood it calls:

1. **`preprocess_series`** — outlier removal, interpolation, Savitzky-Golay smoothing
2. **`extract_phenology`** — amplitude-threshold SOS/MOS/EOS detection

Let's run them manually on one region's monthly averages to see the intermediate steps.
```

- [ ] **Cell 12 (code):**

```python
import pandas as pd

# Pick one region's monthly data
region = phenology_by_region["shapeName"].iloc[0]
region_data = phenology_by_region[phenology_by_region["shapeName"] == region]

# preprocess_series expects a pd.Series indexed by month
series = pd.Series(
    region_data["value"].values,
    index=region_data["month"].values,
)

smoothed = evy.preprocess_series(series)
print(f"Region: {region}")
print(f"Raw values:    {np.round(series.values, 3)}")
print(f"Smoothed:      {np.round(smoothed, 3)}")
```

- [ ] **Cell 13 (code):**

```python
# Extract SOS, MOS, EOS from the smoothed series
metrics = evy.extract_phenology(smoothed, dates=series.index)
print(metrics)
```

- [ ] **Cell 14 (markdown):**

```markdown
## Step 5: Determine and filter the growing season

`get_growing_season` returns the start and end months. `filter_growing_season` subsets a DataFrame to that window.
```

- [ ] **Cell 15 (code):**

```python
start_month, end_month = evy.get_growing_season(df, value_col="mean")
print(f"Growing season: month {start_month} to month {end_month}")
```

- [ ] **Cell 16 (code):**

```python
df_growing = evy.filter_growing_season(
    df, start_month=start_month, end_month=end_month
)
print(f"Full dataset:    {len(df)} rows")
print(f"Growing season:  {len(df_growing)} rows")
df_growing.head()
```

- [ ] **Cell 17 (markdown):**

```markdown
## Summary

| Function | Purpose |
|----------|---------|
| `calculate_phenology` | One-call phenology extraction (aggregates, smooths, extracts) |
| `preprocess_series` | TIMESAT-style outlier removal + Savitzky-Golay smoothing |
| `extract_phenology` | Amplitude-threshold SOS/MOS/EOS detection on a smoothed series |
| `get_growing_season` | Returns (start_month, end_month) tuple |
| `filter_growing_season` | Subsets a DataFrame to the growing season window |
| `plot_seasonality` | Seasonality chart with raw + smoothed values and SOS/MOS/EOS markers |
| `plot_seasonality_by_region` | Faceted version of the above, one panel per region |

For the methodological background behind these choices, see [Design Decisions](../../docs/design-decisions.md).
```

- [ ] **Step: Execute the notebook and save with baked outputs**

- [ ] **Step: Stage and commit**

```bash
git add notebooks/recipes/phenology-extraction.ipynb
git commit -m "Add phenology-extraction recipe covering full phenology pipeline"
```

---

## Task 6: Create `local-backend.ipynb`

**Files:**
- Create: `notebooks/recipes/local-backend.ipynb`

**Spec reference:** Recipe 5 — `backend="local"` via Planetary Computer.

**API functions exercised:** `zonal_stats` (with `backend="local"`), `load_modis`, `load_landcover`, `compute_zonal_stats`, `plot_time_series`.

**Environment note:** This notebook uses only the Planetary Computer backend (no authentication required). It should run in any environment with `evy` installed, no GEE or NASA credentials needed. The implementer should test this on a clean environment if possible.

### Cell structure

- [ ] **Cell 1 (markdown):**

```markdown
# Local Backend

evy's default backend is Google Earth Engine (`backend="gee"`), which runs computations on Google's servers. This recipe demonstrates the **local backend** (`backend="local"`), which downloads MODIS rasters from Microsoft's Planetary Computer and computes statistics on your machine.

**When to use the local backend:**
- You don't have a GEE account or can't authenticate
- You're working with small regions where download + local compute is fast enough
- You need access to the raw rasters (e.g., for custom masking or debugging)

**Trade-offs:**
- Local is **slower** for large countries or long date ranges (downloads full tiles)
- Local is **faster** for very small regions (no round-trip to GEE servers)
- Local uses ESA WorldCover for cropland masking (class 40), while GEE uses Dynamic World (class 4)
- No authentication required for the default Planetary Computer path

See [Troubleshooting](../../docs/troubleshooting.md) if you hit HDF4 driver errors or memory issues.
```

- [ ] **Cell 2 (code):**

```python
import evy
```

- [ ] **Cell 3 (markdown):**

```markdown
## One-line local computation

The simplest switch: pass `backend="local"` to `zonal_stats`. Everything else stays the same.

**Note:** Local-backend output columns are prefixed with `evi_` (e.g., `evi_mean`) instead of the GEE backend's bare names (`mean`).
```

- [ ] **Cell 4 (code):**

```python
gdf = evy.get_boundaries("RWA", admin_level=1)
df_local = evy.zonal_stats(
    gdf,
    zone_col="shapeName",
    backend="local",
    source="modis",
    start_date="2023-01-01",
    end_date="2023-12-31",
    freq=evy.MONTHLY,
    stats=["mean", "std"],
)
df_local.head()
```

- [ ] **Cell 5 (code):**

```python
evy.plot_time_series(df_local, value_col="evi_mean", title="EVI (Local Backend)")
```

- [ ] **Cell 6 (markdown):**

```markdown
## The low-level pipeline

For full control, call the three steps separately:

1. **`load_modis`** — STAC search → lazy `xarray.Dataset` with `evi_raw` and `qa` bands
2. **`load_landcover`** — aligned ESA WorldCover raster
3. **`compute_zonal_stats`** — quality mask → scale → temporal aggregation → cropland mask → extraction

This is equivalent to `zonal_stats(backend="local")` but lets you inspect intermediate rasters.
```

- [ ] **Cell 7 (code):**

```python
ds = evy.load_modis(gdf, start_date="2023-01-01", end_date="2023-12-31")
print(ds)
```

- [ ] **Cell 8 (code):**

```python
lc = evy.load_landcover(gdf, ds)
print(f"Land cover shape: {lc.shape}")
print(f"Unique classes: {lc.values.flatten()[~np.isnan(lc.values.flatten())].astype(int)}")
```

Note: add `import numpy as np` to Cell 2 if needed, or use a separate import cell before Cell 8.

- [ ] **Cell 9 (code):**

```python
df_pipeline = evy.compute_zonal_stats(
    ds,
    gdf,
    zone_col="shapeName",
    land_cover=lc,
    freq=evy.MONTHLY,
    stats=["mean", "median"],
)
df_pipeline.head()
```

- [ ] **Cell 10 (markdown):**

```markdown
## NASA Earthdata backend

If you need MODIS data not available on Planetary Computer, evy also supports NASA Earthdata via the `earthaccess` library. This requires authentication:

```python
import earthaccess
earthaccess.login(persist=True)
```

Once authenticated, the `earthaccess` backend streams MODIS bands via OPeNDAP (as NetCDF4), which avoids the HDF4 driver issues common on macOS. See [Troubleshooting](../../docs/troubleshooting.md) for details.

The Planetary Computer path is the recommended default — it requires no authentication and serves Cloud-Optimized GeoTIFFs for fast partial reads.
```

- [ ] **Cell 11 (markdown):**

```markdown
## Output column naming

A practical difference to be aware of:

| Backend | Mean column | Std column |
|---------|------------|------------|
| GEE (`backend="gee"`) | `mean` | `stdDev` |
| Local (`backend="local"`) | `evi_mean` | `evi_std` |

If you pass local-backend output to `calculate_phenology`, use `value_col="evi_mean"` instead of the default `"mean"`.
```

- [ ] **Step: Execute the notebook and save with baked outputs**

This notebook requires no GEE authentication — only Planetary Computer (no auth). Verify that `load_modis` and `load_landcover` complete without errors. If `pystac_client` warnings appear (e.g., `numberMatched not in response`), that is normal and expected.

- [ ] **Step: Stage and commit**

```bash
git add notebooks/recipes/local-backend.ipynb
git commit -m "Add local-backend recipe demonstrating Planetary Computer pipeline"
```

---

## Task 7: Build and verify the full site

**Goal:** Rebuild the Jupyter Book and confirm all five recipes render in the Cookbook section.

- [ ] **Step 1: Clean stale build artifacts**

```bash
rm -rf _build docs/_build
```

- [ ] **Step 2: Run the build**

```bash
make build
```

Expected: `build succeeded` in final output. The warning count will increase because of the new notebooks, but there should be no ERROR-level messages about the recipe files.

- [ ] **Step 3: Verify the Cookbook section exists in the sidebar**

```bash
grep -c 'Cookbook' _build/html/index.html || grep -c 'Cookbook' _build/html/README.html
```

Expected: at least `1` — confirms the Cookbook caption rendered in the navigation.

- [ ] **Step 4: Verify each recipe page exists**

```bash
ls _build/html/notebooks/recipes/
```

Expected: five `.html` files:
- `monthly-aggregation.html`
- `cropland-masking.html`
- `multi-country-comparison.html`
- `phenology-extraction.html`
- `local-backend.html`

- [ ] **Step 5: Spot-check recipe content rendered**

```bash
grep -c 'freq' _build/html/notebooks/recipes/monthly-aggregation.html
grep -c 'mask_cropland' _build/html/notebooks/recipes/cropland-masking.html
grep -c 'plot_choropleth' _build/html/notebooks/recipes/multi-country-comparison.html
grep -c 'preprocess_series' _build/html/notebooks/recipes/phenology-extraction.html
grep -c 'backend.*local' _build/html/notebooks/recipes/local-backend.html
```

Expected: each count is at least `1`.

- [ ] **Step 6: No file changes to commit in this task**

Task 7 is verification only. Confirm via `git status` that no new modifications appear (the `_build/` directory is gitignored).

---

## Coverage check

After all five recipes + the quickstart, the following `__all__` symbols are exercised:

| Symbol | Where exercised |
|--------|----------------|
| `zonal_stats` | Quickstart, recipes 1–5 |
| `get_boundaries` | Quickstart, recipes 1–5 |
| `load_boundaries` | Quickstart (commented example) |
| `clear_cache` | API reference only (utility) |
| `list_collections` | Quickstart |
| `authenticate` | API reference only (utility) |
| `is_authenticated` | API reference only (utility) |
| `check_task_status` | Quickstart (commented example) |
| `load_modis` | Quickstart, recipe 5 |
| `load_landcover` | Quickstart, recipe 5 |
| `compute_zonal_stats` | Quickstart, recipe 5 |
| `calculate_phenology` | Quickstart, recipe 4 |
| `extract_phenology` | Recipe 4 |
| `preprocess_series` | Recipe 4 |
| `get_growing_season` | Recipe 4 |
| `filter_growing_season` | Quickstart, recipe 4 |
| `plot_seasonality` | Quickstart, recipe 4 |
| `plot_seasonality_by_region` | Quickstart, recipe 4 |
| `plot_time_series` | Recipes 1, 2, 5 |
| `plot_time_series_by_region` | Recipe 3 |
| `plot_choropleth` | Recipe 3 |

Symbols exercised only in API reference / utilities: `clear_cache`, `list_collections`, `authenticate`, `is_authenticated`, `check_task_status`. This matches the spec's intentional exclusion.

---

## Done

When every task box above is checked and Task 7 passes, Phase 3 is complete. The Cookbook section is live with five recipes covering every non-utility symbol in the public API.

**Deliberately not done in this plan** (goes into Phase 4):

- README cleanup (anomaly detection feature claim)
- CLAUDE.md stale-path fix (`src/evy/local/` → actual flat layout)
- New API surface (e.g., `calculate_anomaly`)
