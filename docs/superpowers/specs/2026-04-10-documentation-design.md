# evy Documentation Design

**Date:** 2026-04-10
**Status:** Approved (pending user review of this spec)
**Audience:** Implementation plan authors, maintainers

---

## Purpose

Define the structure, scope, and content of evy's documentation site. Replace the near-empty Jupyter Book scaffold (currently: one quickstart notebook + four external links) with a focused doc site that serves researchers running one-shot EVI analyses and the project maintainer returning to the code later.

## Primary reader

**Primary:** A researcher who found evy via a paper or colleague, wants to compute EVI statistics over one country, and will rarely touch the code beyond the top-level API.

**Secondary:** Future-Aldo (the maintainer) coming back after months away and needing to recall how the backends, gotchas, and design decisions fit together.

Everything downstream in this spec is optimized for those two readers. Other audiences are still served, but lose tie-breaks.

## Non-goals

These are stated explicitly so they don't creep in during implementation:

- No auto-generation from the full module tree; only symbols in `src/evy/__init__.py`'s `__all__` get reference pages.
- No "tutorials" section beyond the existing quickstart. The cookbook is how-to-style, not pedagogical.
- No per-function examples inside the design-decisions page; examples live in cookbook recipes.
- No CI notebook execution. `_config.yml` keeps `execute_notebooks: off`; baked outputs ship with notebooks.
- No video walkthroughs, interactive widgets, or gallery-style case studies.
- No literature-review-depth methodology content. A single short page is the cap.

## Framework choice: none (deliberately)

The Diátaxis framework was considered and rejected as a top-level organizing principle. For a ~2000-line library with one maintainer, invoking a four-quadrant framework produces empty folders and cosplays structure that isn't there. Instead, the site is organized by what the researcher is trying to do: **Getting Started → Cookbook → Reference → About**.

Pages may individually correspond to Diátaxis modes (quickstart ≈ tutorial, recipes ≈ how-to, api-reference ≈ reference, design-decisions ≈ explanation), but the vocabulary does not appear in the site and should not shape decisions during implementation.

---

## Site structure (`docs/_toc.yml`)

```yaml
format: jb-book
root: README

parts:
  - caption: Getting Started
    chapters:
      - file: docs/installation
      - file: notebooks/quickstart

  - caption: Cookbook
    chapters:
      - file: notebooks/recipes/monthly-aggregation
      - file: notebooks/recipes/cropland-masking
      - file: notebooks/recipes/multi-country-comparison
      - file: notebooks/recipes/phenology-extraction
      - file: notebooks/recipes/local-backend

  - caption: Reference
    chapters:
      - file: docs/api-reference
      - file: docs/design-decisions
      - file: docs/troubleshooting

  - caption: About
    chapters:
      - file: docs/contributing
      - file: docs/code-of-conduct
      - file: docs/citation
```

### Structural notes

- `README.md` remains the `root` — no separate Home page.
- New recipes live under `notebooks/recipes/` to keep them visually separated from the canonical `notebooks/quickstart.ipynb`.
- `docs/contributing` and `docs/code-of-conduct` are MyST stubs that `include` the root `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` to keep a single source of truth.
- The "Additional Resources" external links from the current `_toc.yml` move into the README footer or a fifth "About" chapter (maintainer's choice during implementation).

---

## Page-by-page content

### Getting Started

#### `docs/installation.md`

A single ~250-line markdown page covering setup for both backends. Sections:

1. **Install the package** — `uv pip install` and `pip install` commands from GitHub, matching the current README.
2. **Backend prerequisites** — an explicit table:
   - **GEE:** Google account → request Earth Engine access → `evy.authenticate()` or `GEE_PROJECT` env var.
   - **Local (Planetary Computer):** no authentication required (default).
   - **Local (NASA earthaccess):** `earthaccess.login(persist=True)` plus a note on NASA Earthdata account creation.
3. **Verify the install** — a 3-line snippet that imports `evy` and runs `list_collections()`. If that works, the install is done.
4. **Optional dependencies** — only included if `scipy` and `altair` are not core dependencies. Implementation must check `pyproject.toml` before writing this section. If they are core, this section is cut.

#### `notebooks/quickstart.ipynb`

Already exists. No changes required by this spec. If minor updates are desired during the doc pass (e.g., linking out to the cookbook from the final cell), they are optional and not part of the documented deliverables.

---

### Cookbook

Five runnable notebooks. Each recipe follows the heuristic **one recipe = one axis of variation from the quickstart**. No recipe re-explains boundaries from scratch; they link back to the quickstart for shared setup.

All recipes are stored in `notebooks/recipes/` and ship with baked outputs.

#### 1. `monthly-aggregation.ipynb`

- **Goal:** Compute monthly mean EVI for a single country over a multi-year window.
- **Flow:** `get_boundaries` → `zonal_stats(freq="ME", stats=["mean", "std"])` → `plot_time_series`.
- **Teaches:** The `freq` parameter (`D`, `W`, `ME`, `QE`, `YE`) and the `stats` list. Links to Design Decisions for *why* `ME` is a sensible default.
- **Excludes:** Masking, phenology, multi-country comparison.

#### 2. `cropland-masking.ipynb`

- **Goal:** Same analysis as recipe 1, restricted to cropland pixels.
- **Flow:** Side-by-side comparison of `zonal_stats(mask_cropland=True)` vs `False`.
- **Teaches:** The cropland mask parameter and — critically — that GEE uses Dynamic World (class 4) while local uses ESA WorldCover (class 40). Researchers defending methodology in a paper need to know which mask ran.
- **Excludes:** Custom land-cover masks (out of scope; would require an API change).

#### 3. `multi-country-comparison.ipynb`

- **Goal:** Compare EVI seasonality across 3–4 neighboring countries.
- **Flow:** Loop or concatenate `get_boundaries` calls → `zonal_stats` → `plot_time_series_by_region` and `plot_choropleth`.
- **Teaches:** The `_by_region` plot variants, which are in the public API but invisible in the quickstart.
- **Excludes:** Cross-border mosaicking. Each country is compared independently.

#### 4. `phenology-extraction.ipynb`

- **Goal:** Extract SOS/MOS/EOS for a specific region and visualize the growing season.
- **Flow:** `zonal_stats(freq="D")` → `calculate_phenology` → `plot_seasonality`. Brief prose on TIMESAT-style smoothing and the amplitude-threshold parameter.
- **Teaches:** The phenology module — touches `preprocess_series`, `extract_phenology`, `calculate_phenology`, `get_growing_season`, `filter_growing_season`.
- **Excludes:** Multi-season years (double cropping). Flag as a known limitation in the notebook.

#### 5. `local-backend.ipynb`

- **Goal:** Run the quickstart analysis with `backend="local"` via Planetary Computer.
- **Flow:** `zonal_stats(backend="local", source="modis")`. Brief mention of the `earthaccess` backend with a link to Troubleshooting for auth setup.
- **Teaches:** Backend switching, runtime characteristics (local is slower for big regions, faster for small ones).
- **Excludes:** Caching internals, HDF4 driver gotchas — those belong in Troubleshooting.

### Coverage check

Between the quickstart and these five recipes, every symbol in `__all__` appears at least once except `clear_cache`, `list_collections`, `is_authenticated`, and `check_task_status` — all utility functions better served by the API reference than a recipe. This is intentional.

### Not included: anomaly detection

The README currently advertises "Anomaly Detection" as a feature, but there is no `calculate_anomaly` function in `__all__`. A recipe for this was considered and removed. **Action item outside the scope of this spec:** update the README to either remove the anomaly detection feature claim or add the function. Either resolution is acceptable; this spec does not choose between them.

---

### Reference

#### `docs/api-reference.md`

Generated by **sphinx-autodoc2** with a thin MyST wrapper page. All 21 public functions from `evy/__init__.py`'s `__all__` are listed explicitly, grouped to match the sectioning comments in that file:

- **Boundaries:** `get_boundaries`, `load_boundaries`, `clear_cache`
- **Collections & Authentication:** `list_collections`, `authenticate`, `is_authenticated`, `check_task_status`
- **Zonal Statistics:** `zonal_stats`, `load_modis`, `load_landcover`, `compute_zonal_stats`
- **Phenology:** `calculate_phenology`, `extract_phenology`, `preprocess_series`, `get_growing_season`, `filter_growing_season`
- **Visualization:** `plot_seasonality`, `plot_seasonality_by_region`, `plot_time_series`, `plot_time_series_by_region`, `plot_choropleth`
- **Constants:** `DAILY`, `WEEKLY`, `MONTHLY`, `QUARTERLY`, `YEARLY`, `CRS` — documented inline on the page (not via autodoc2, which does not render module-level string constants cleanly).

Each symbol is rendered via an explicit `{autodoc2-object}` directive. This inverts autodoc2's default: nothing is auto-crawled; only the listed symbols appear. Underscored helpers (`_auth`, `_convert`, `_process`, `_zonal_local`) never render.

#### `docs/design-decisions.md`

A single short methodology page. **Hard cap: 1000 words. Target: ~800.** One tight paragraph per topic, each ending with a citable anchor (*"If you're writing a paper, cite X as the primary source for this choice"*).

Topics, in order:

1. **Why EVI (not NDVI)** — saturation at high biomass, atmospheric and soil-background corrections. Cite the MODIS MOD13 user guide.
2. **Which MODIS product** — MOD13Q1 (Terra, 16-day, 250m) as default. Note MYD13Q1 (Aqua) exists; Terra chosen for the longer continuous record.
3. **Quality masking** — what the pixel reliability band contains. Retain values 0 (good) and 1 (marginal); drop 2 and 3. Link to MODIS QA documentation.
4. **Cropland masking** — on by default. GEE uses Dynamic World (class 4); local uses ESA WorldCover (class 40). What the user loses by disabling it.
5. **Temporal aggregation defaults** — why `ME` (end of month) is the default. Alignment with agricultural calendars and signal-to-noise trade-off.
6. **Phenology method** — TIMESAT-style with Savitzky-Golay smoothing, amplitude-threshold SOS/EOS detection. Cite Jönsson & Eklundh (original TIMESAT paper). This paper is added to `docs/bibliography.bib` if not already present.
7. **Coordinate reference system** — EPSG:4326 for inputs/outputs, EPSG:3857 used internally for some operations. Brief rationale.

#### `docs/troubleshooting.md`

Organized by the verbatim error message a user sees, not by topic. Each entry = symptom → cause → fix. Page should be fully searchable (default Jupyter Book behavior).

Planned entries:

1. **"Not signed in to Earth Engine"** → run `evy.authenticate()` or set `GEE_PROJECT`.
2. **"Project is not registered for Earth Engine"** → register at code.earthengine.google.com.
3. **"Quota exceeded" / timeouts on large queries** → use `export_to_drive=True` or switch to `backend="local"`.
4. **"HDF4 driver not found" (local backend, macOS)** → explain that pip-installed GDAL lacks HDF4; evy's earthaccess backend works around this using OPeNDAP; Planetary Computer path is the no-install-drama default.
5. **`earthaccess` login loop** — how to persist credentials via `earthaccess.login(persist=True)`.
6. **"Cache seems stale"** → `clear_cache()` or delete `~/.evy/boundaries/`.
7. **GeoBoundaries API returns 404** → check ISO3 code and admin level availability.
8. **Memory blow-up on large regions (local backend)** → chunk size guidance, use smaller bounding box.

Entries may be added or reworded during implementation as real issues surface, but this spec's baseline is these eight.

---

### About

Three pages, all thin:

- `docs/contributing.md` — MyST stub that `include`s the root `CONTRIBUTING.md`.
- `docs/code-of-conduct.md` — MyST stub that `include`s the root `CODE_OF_CONDUCT.md`.
- `docs/citation.md` — short page pointing at `CITATION.cff` and showing the preferred citation format inline.

---

## Build configuration

### `docs/_config.yml` additions

```yaml
sphinx:
  extra_extensions:
    - autodoc2
  config:
    autodoc2_packages:
      - path: ../src/evy
        auto_mode: false
    autodoc2_render_plugin: myst
    autodoc2_hidden_regexes:
      - ".*\\._.*"
    # existing config preserved:
    html_show_copyright: false
    html_last_updated_fmt: "%b %d, %Y"
```

**Key setting: `auto_mode: false`.** Without this, autodoc2 crawls every submodule and auto-generates pages for everything, including private helpers. With `auto_mode: false`, nothing renders unless explicitly listed on the reference page via `{autodoc2-object}`. This is the mechanism that keeps the reference page limited to `__all__`.

### `pyproject.toml` additions

Add `sphinx-autodoc2` to the `[docs]` optional-dependency extra. No other dependency changes.

### Execution settings

`execute_notebooks: off` is preserved. Recipes ship with baked outputs. Trade-off acknowledged: when the underlying API changes, recipes must be manually re-run. This is acceptable for a 5-recipe cookbook; it would not scale past ~20.

---

## Docstring polish (prerequisite for autodoc2 quality)

Audit result (conducted during brainstorming): docstrings across the public API are in good shape — consistent NumPy style with `Parameters` / `Returns` / sometimes `Raises`. `zonal_stats` is a model docstring. `plot_seasonality` includes a `>>>` doctest-style `Examples` block.

Minor polish required before the API reference page renders cleanly:

- `load_modis` and `load_landcover` (in `src/evy/load.py`) are functional but thinner. Add `Examples` and `Raises` sections; fix the run-on sentence in `load_landcover`.
- `preprocess_series` (in `src/evy/phenology.py`) raises `ImportError` in the body but does not document it. Add a `Raises` section.

These touch-ups are a prerequisite for Phase 1 to produce a clean reference page.

---

## Implementation ordering

Ordered by cost-to-value. After Phase 1 the site is already deployable and better than what ships today, even if later phases slip.

### Phase 1 — Foundation

1. Add `sphinx-autodoc2` to `[docs]` extra in `pyproject.toml`.
2. Update `docs/_config.yml` with autodoc2 configuration.
3. Create `docs/installation.md`.
4. Create `docs/api-reference.md` with `{autodoc2-object}` directives for all 21 public functions, plus inline documentation for the 6 constants.
5. Create stub pages: `docs/design-decisions.md`, `docs/troubleshooting.md`, `docs/contributing.md`, `docs/code-of-conduct.md`, `docs/citation.md`. Headers only at this stage.
6. Create the `notebooks/recipes/` directory (empty for now; populated in Phase 3).
7. Update `docs/_toc.yml` to the new structure.
8. Verify the book builds locally with `jupyter-book build docs/`.

**Exit criterion:** The site renders end-to-end. API reference page shows all 21 public functions with their current docstrings. No broken links in `_toc.yml`. Stub pages exist so the TOC doesn't 404.

### Phase 2 — Content for existing functionality

9. Docstring polish on `load_modis`, `load_landcover`, `preprocess_series` (add `Examples`, `Raises` sections; fix the run-on sentence in `load_landcover`).
10. Fill in `docs/troubleshooting.md` with the eight entries.
11. Fill in `docs/design-decisions.md` with the seven topics (~800 words total, hard cap 1000).

**Exit criterion:** Reference tier is fully populated. A user hitting a GEE auth error can find the fix via Troubleshooting. A researcher defending methodology can cite Design Decisions.

### Phase 3 — Cookbook

Build recipes in order, easiest first:

12. `monthly-aggregation.ipynb`
13. `cropland-masking.ipynb`
14. `multi-country-comparison.ipynb`
15. `phenology-extraction.ipynb`
16. `local-backend.ipynb` — requires testing on a clean environment to catch setup issues.

**Exit criterion:** All five recipes render with baked outputs. Every non-utility symbol in `__all__` is exercised at least once across quickstart + recipes.

### Phase 4 — Housekeeping (non-blocking)

17. Update `README.md`: either remove "Anomaly Detection" from the features list or add a `calculate_anomaly` function. Not decided in this spec.
18. Fix stale `CLAUDE.md` reference to `src/evy/local/` subdirectory (actual layout is flat).

Phases 2 and 3 are independent and can be parallelized or reordered based on urgency. Phase 1 blocks everything; Phase 4 blocks nothing.

---

## Risks and open questions

- **Docstring drift.** Because autodoc2 reads `src/evy/`, any docstring regression instantly degrades the API reference. No CI check is proposed in this spec; docstring quality is a maintainer responsibility.
- **Notebook output drift.** With `execute_notebooks: off`, recipe outputs become stale when the API changes. Mitigation is manual re-running; formalizing this is out of scope for this spec.
- **Anomaly detection.** The README/API mismatch is flagged in Phase 4 but not resolved here. Surfacing it in the spec is intentional: docs work exposed the gap, but this spec is about docs, not API design.
- **Optional-deps section in installation.** Depends on whether `scipy` and `altair` are core or optional in `pyproject.toml`. Implementation must check before writing that section.
