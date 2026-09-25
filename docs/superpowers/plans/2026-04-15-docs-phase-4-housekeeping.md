# Documentation Site — Phase 4 (Housekeeping) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two long-standing inaccuracies surfaced by the docs work: a feature claim in `README.md` that has no implementation, and a stale architecture block in `CLAUDE.md` that describes a directory layout that doesn't exist.

**Architecture:** Two small text edits + one verification build. No code changes, no dependency changes, no notebook changes.

**Tech Stack:** Markdown only.

**Scope note:** This plan implements Phase 4 of the design spec at `docs/superpowers/specs/2026-04-10-documentation-design.md`. Phases 1–3 (foundation, content, cookbook) are complete on this branch.

**Decision recorded during planning:** The README "Anomaly Detection" claim is **removed**, not replaced with a real implementation. Adding a `calculate_anomaly` function would be a feature addition that deserves its own brainstorm (z-score vs. difference vs. percentage, baseline period semantics, etc.) — it is out of scope for documentation housekeeping.

**Pre-flight:**
- Confirm you are on branch `update-quickstart` and that Phase 1–3 commits exist in `git log` (most recent should be the local-backend recipe at `a46b70b` or later).
- The working tree has unrelated in-progress changes in `.gitignore`, `notebooks/quickstart.ipynb`, `src/evy/_process.py`, `src/evy/load.py`, `uv.lock`, and deleted `docs/*.md` template files — **these must not be bundled into any commits in this plan**. Both tasks stage files by explicit path. Neither `README.md` nor `CLAUDE.md` is in the unstaged set, so both are clean edits.

---

## Task 1: Remove the unsupported "Anomaly Detection" claim from README

**Files:**
- Modify: `README.md:17`

**Background:** `README.md` currently lists "Anomaly Detection" as a feature, but no `calculate_anomaly` function exists in `src/evy/__init__.py`'s `__all__`. This was flagged during Phase 3 spec review. We are removing the claim rather than implementing the function.

- [ ] **Step 1: Inspect the current Features list**

Run:
```bash
sed -n '11,20p' README.md
```

Expected: lines 11–20 contain a `## Features` header followed by a bullet list including the "Anomaly Detection" line at line 17.

- [ ] **Step 2: Delete the Anomaly Detection bullet**

Find this line in `README.md` (currently line 17):

```markdown
- **Anomaly Detection**: Calculate vegetation anomalies using z-scores, differences, or percentages
```

Delete the entire line, including its trailing newline. The surrounding bullets (`Phenology Analysis` above and `Land Cover Masking` below) should now sit consecutively with no blank line between them.

After the edit, lines 13–18 should read:

```markdown
- **Easy Data Access**: Fetch MODIS EVI data from Planetary Computer with automatic quality masking
- **Zonal Statistics**: Compute statistics (mean, median, max, etc.) for specific geometries
- **Temporal Aggregation**: Aggregate data at various temporal frequencies (monthly, yearly, quarterly)
- **Phenology Analysis**: Extract and visualize vegetation growing seasons and phenological patterns
- **Land Cover Masking**: Filter EVI data by land cover classification (e.g., cropland-only analysis)
- **Visualization**: Built-in plotting functions for time series and phenology
```

- [ ] **Step 3: Verify the edit**

Run:
```bash
git diff README.md
```

Expected: a single `-` line removing the Anomaly Detection bullet, with no other changes.

Also run:
```bash
grep -i 'anomal' README.md
```

Expected: no output (zero matches). If any "anomaly" reference remains anywhere in the README, decide whether it is a legitimate prose mention of the concept or a stale feature pointer; the spec only commits to removing the unsupported feature claim.

- [ ] **Step 4: Stage and commit**

```bash
git add README.md
git commit -m "Remove unsupported Anomaly Detection feature claim from README"
```

---

## Task 2: Rewrite the stale architecture block in `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md:35-58`

**Background:** The current `## Architecture` block describes a `src/evy/local/` subdirectory with 11 files (`_zonal.py`, `_loader.py`, `_backends.py`, `_stac.py`, `_planetary.py`, `_earthaccess.py`, `_evi.py`, `_quality.py`, `_landcover.py`, `_temporal.py`, `_config.py`). That subdirectory does not exist. The actual layout is **flat** — the local-backend functionality lives in `_zonal_local.py`, `_process.py`, and `load.py` at the top level of `src/evy/`.

The actual files in `src/evy/` (verify with `ls src/evy/`):

```
__init__.py       _auth.py      _convert.py    _process.py    _zonal_local.py
boundaries.py     collections.py    load.py    phenology.py    viz.py    zonal.py
```

- [ ] **Step 1: Confirm the actual layout matches the assumption**

Run:
```bash
ls src/evy/
```

Expected: the eleven files listed above. If a `local/` subdirectory **does** exist, **stop and ask** — the plan's premise is wrong and the rewrite below would be incorrect.

- [ ] **Step 2: Inspect the current architecture block**

Run:
```bash
sed -n '35,62p' CLAUDE.md
```

Expected: the `## Architecture` heading, a fenced code block containing the fictional tree, and the two `**Data Flow**` paragraphs that follow it. The `**Data Flow**` paragraphs are still accurate and should be preserved.

- [ ] **Step 3: Replace the architecture block**

Find this block (currently lines 35–58):

```markdown
## Architecture

​```
src/evy/
├── zonal.py        # Core: zonal_stats() - main entry point, routes to GEE or local backend
├── collections.py  # Data sources: MODIS (MOD13Q1, MYD13Q1) and Sentinel-2 (GEE)
├── boundaries.py   # Spatial: GeoBoundaries API fetch, caching (~/.evy/boundaries)
├── phenology.py    # Analysis: TIMESAT-style SOS/MOS/EOS extraction
├── viz.py          # Visualization: Altair-based charts (seasonality, time series, choropleth)
├── _auth.py        # GEE authentication helpers
├── _convert.py     # GEE FeatureCollection → pandas/geopandas conversion
└── local/          # Local computation backend (STAC-based)
    ├── _zonal.py       # Local zonal statistics computation
    ├── _loader.py      # Data loading orchestration
    ├── _backends.py    # MODIS backend configuration
    ├── _stac.py        # STAC catalog search and interaction
    ├── _planetary.py   # Microsoft Planetary Computer access
    ├── _earthaccess.py # NASA Earthdata access
    ├── _evi.py         # EVI calculation from bands
    ├── _quality.py     # Quality masking (MODIS QA, Sentinel-2 SCL)
    ├── _landcover.py   # Land cover filtering (cropland masking)
    ├── _temporal.py    # Temporal aggregation
    └── _config.py      # Configuration management
​```
```

(Note: the `​` characters before the fence above are zero-width markers used to keep this plan readable as MyST. The real `CLAUDE.md` block uses plain triple-backticks.)

Replace it with this corrected block:

````markdown
## Architecture

```
src/evy/
├── __init__.py       # Public API: re-exports the 21 functions + 6 constants in __all__
├── zonal.py          # Core: zonal_stats() - main entry point, routes to GEE or local backend
├── collections.py    # GEE data source registry: MODIS (MOD13Q1, MYD13Q1) and Sentinel-2
├── boundaries.py     # GeoBoundaries fetch + caching (~/.evy/boundaries), load_boundaries()
├── phenology.py      # TIMESAT-style SOS/MOS/EOS extraction (Savitzky-Golay smoothing)
├── viz.py            # Altair-based charts (seasonality, time series, choropleth)
├── load.py           # Local backend STAC loaders: load_modis(), load_landcover()
├── _auth.py          # GEE authentication helpers (authenticate, is_authenticated)
├── _convert.py       # GEE FeatureCollection → pandas/geopandas conversion
├── _process.py       # Local backend processing: quality masking, EVI scaling, temporal agg
└── _zonal_local.py   # Local backend orchestrator: compute_zonal_stats() pipeline
```

The local computation backend is **not** a subpackage — it lives in three flat modules
at the top level: `load.py` (STAC loaders), `_process.py` (raster processing), and
`_zonal_local.py` (the pipeline that ties them together with `exactextract`).
````

- [ ] **Step 4: Verify the edit**

Run:
```bash
git diff CLAUDE.md
```

Expected: removal of the fictional `local/` subdirectory tree and addition of the corrected flat-layout tree. The `**Data Flow (GEE):**` and `**Data Flow (Local):**` paragraphs that follow should be **untouched** in the diff.

Also run:
```bash
grep -n 'local/' CLAUDE.md
```

Expected: zero matches in the architecture block. (The string `"local"` may still appear in prose elsewhere — that's fine. The grep above checks for the directory-style `local/` token specifically.)

- [ ] **Step 5: Stage and commit**

```bash
git add CLAUDE.md
git commit -m "Fix stale architecture block in CLAUDE.md to match flat src/evy layout"
```

---

## Task 3: Rebuild the book and confirm nothing regressed

**Goal:** Run a clean build to confirm Tasks 1 and 2 didn't introduce broken cross-references or other rendering issues. Neither file is in the Jupyter Book TOC, but `README.md` is the book's `root`, so changes there are reflected in the home page; `CLAUDE.md` is **not** in the TOC and should not change anything in the rendered site.

- [ ] **Step 1: Clean stale build artifacts**

```bash
rm -rf _build docs/_build
```

- [ ] **Step 2: Run the build**

```bash
make build
```

Expected: `build succeeded` in the final output. The warning count should be **at most** the Phase 3 baseline (104 warnings). A higher count indicates one of the edits introduced a new warning — investigate before claiming success.

- [ ] **Step 3: Confirm the README change rendered**

```bash
grep -i 'anomaly' _build/html/README.html
```

Expected: zero matches. The Anomaly Detection bullet should no longer appear on the home page.

- [ ] **Step 4: Confirm CLAUDE.md was not pulled into the build**

```bash
ls _build/html/CLAUDE.html 2>&1 | head -1
```

Expected: `ls: ... No such file or directory`. `CLAUDE.md` is intentionally not in the TOC, so it must not render. If it does render (e.g., because Sphinx auto-included it), that is a separate issue and out of scope for this plan — flag it but do not address.

- [ ] **Step 5: No file changes to commit in this task**

Confirm via `git status` that the only outstanding modifications are the pre-existing ones flagged in the pre-flight (`.gitignore`, `notebooks/quickstart.ipynb`, `src/evy/_process.py`, `src/evy/load.py`, `uv.lock`, deleted template `docs/*.md` files). The `_build/` directory is gitignored.

---

## Done

When every task box above is checked and Task 3 passes, Phase 4 is complete. The four-phase documentation effort is finished:

- **Phase 1 (Foundation):** Scaffold + autodoc2 wiring + stub pages
- **Phase 2 (Content):** Reference tier — troubleshooting, design decisions, polished docstrings
- **Phase 3 (Cookbook):** Five recipe notebooks covering the public API
- **Phase 4 (Housekeeping):** README + CLAUDE.md cleanup

**Outstanding non-Phase-4 items:**

- **Bake notebook outputs.** Phase 3 shipped recipe `.ipynb` files without executed outputs (Option A from the planning discussion). A separate session needs to execute all five recipes against a working evy environment and commit the outputs.
- **Pre-existing working-tree changes.** The unstaged modifications in `.gitignore`, `notebooks/quickstart.ipynb`, `src/evy/_process.py`, and `src/evy/load.py` are not docs work and need their own decision (commit, discard, or carry forward).
- **`anomaly` API.** If a `calculate_anomaly` function is wanted later, it gets its own brainstorm + spec + plan. This phase only removed the README claim; the API surface is unchanged.
