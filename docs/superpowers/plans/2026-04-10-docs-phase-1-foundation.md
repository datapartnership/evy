# Documentation Site — Phase 1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Jupyter Book scaffold so the docs site builds end-to-end with a working autodoc2-based API reference page and stub pages for all Phase 2 content. After this plan, the site is deployable even though Phases 2–4 haven't started.

**Architecture:** Jupyter Book (v1) renders `docs/_toc.yml` into a static site. `sphinx-autodoc2` provides a MyST-native API reference limited to `evy/__init__.py`'s `__all__`. The build runs through `uvx`, so `sphinx-autodoc2` is injected via `--with` rather than installed into the project environment.

**Tech Stack:** Jupyter Book 1, MyST Markdown, Sphinx, `sphinx-autodoc2`, `uv` / `uvx`.

**Scope note:** This plan only covers Phase 1 of the design spec at `docs/superpowers/specs/2026-04-10-documentation-design.md`. Phase 2 (troubleshooting and design-decisions content), Phase 3 (cookbook recipes), and Phase 4 (README + CLAUDE.md housekeeping) will each get their own plans once Phase 1 is shipped and reviewed.

**Pre-flight:** Confirm you are on branch `update-quickstart` and that the spec file `docs/superpowers/specs/2026-04-10-documentation-design.md` is committed and visible in `git log`. All tasks should stage files explicitly by path — never use `git add -A` or `git add .`, because the branch has unrelated in-progress changes (`notebooks/quickstart.ipynb`, `src/evy/load.py`, `src/evy/_process.py`, `docs/_toc.yml`, etc.) that must NOT be bundled into these commits.

---

## Task 1: Add `sphinx-autodoc2` to `[docs]` extra in `pyproject.toml`

**Files:**
- Modify: `pyproject.toml:41-45`

- [ ] **Step 1: Inspect the current `[docs]` extra**

Run:
```bash
sed -n '41,46p' pyproject.toml
```

Expected output:
```toml
[project.optional-dependencies]
docs = [
	"docutils==0.17.1", # pinned to docutils==0.17.1 due to https://github.com/worldbank/template/issues/60. See also: https://jupyterbook.org/en/stable/content/citations.html?highlight=docutils#citations-and-bibliographies
	"jupyter-book>=1,<2",
]
```

Note: the `docs` block uses **tabs** for indentation. Match that when editing.

- [ ] **Step 2: Add `sphinx-autodoc2` to the list**

Edit `pyproject.toml` so the `[docs]` block reads:

```toml
[project.optional-dependencies]
docs = [
	"docutils==0.17.1", # pinned to docutils==0.17.1 due to https://github.com/worldbank/template/issues/60. See also: https://jupyterbook.org/en/stable/content/citations.html?highlight=docutils#citations-and-bibliographies
	"jupyter-book>=1,<2",
	"sphinx-autodoc2>=0.5.0",
]
```

- [ ] **Step 3: Verify the edit**

Run:
```bash
sed -n '41,47p' pyproject.toml
```

Expected: the three dependencies appear in order, all using tab indentation.

- [ ] **Step 4: Stage and commit**

```bash
git add pyproject.toml
git commit -m "Add sphinx-autodoc2 to docs extra"
```

---

## Task 2: Add `--with sphinx-autodoc2` to the `make build` command

**Why this exists:** `make build` uses `uvx --from "jupyter-book>1,<2"`, which runs Jupyter Book in an isolated environment. Adding `sphinx-autodoc2` to `[docs]` is not sufficient on its own — the isolated `uvx` env also needs it, injected via `--with`.

**Files:**
- Modify: `Makefile:49-50`

- [ ] **Step 1: Inspect the current build target**

Run:
```bash
sed -n '48,51p' Makefile
```

Expected output:
```makefile
# Build documentation
build:
	uvx --from "jupyter-book>1,<2" jupyter-book build . --config docs/_config.yml --toc docs/_toc.yml
```

- [ ] **Step 2: Edit the build command**

Replace line 50 so the target reads:

```makefile
# Build documentation
build:
	uvx --with sphinx-autodoc2 --from "jupyter-book>1,<2" jupyter-book build . --config docs/_config.yml --toc docs/_toc.yml
```

Note: the line must start with a **tab character**, not spaces, or `make` will error.

- [ ] **Step 3: Verify make still parses the file**

Run:
```bash
make -n build
```

Expected: the build command is echoed (dry run) without a `make:` error. The output should contain `uvx --with sphinx-autodoc2 --from "jupyter-book>1,<2"`.

- [ ] **Step 4: Stage and commit**

```bash
git add Makefile
git commit -m "Inject sphinx-autodoc2 into docs build via uvx --with"
```

---

## Task 3: Add `sphinx-autodoc2` configuration to `docs/_config.yml`

**Files:**
- Modify: `docs/_config.yml:40-45`

- [ ] **Step 1: Inspect the current `sphinx` block**

Run:
```bash
sed -n '40,46p' docs/_config.yml
```

Expected output:
```yaml
# Sphinx settings
sphinx:
  config:
    html_show_copyright: false
    html_last_updated_fmt: "%b %d, %Y"
```

- [ ] **Step 2: Add the `extra_extensions` and autodoc2 config**

Replace the `sphinx` block with:

```yaml
# Sphinx settings
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
    html_show_copyright: false
    html_last_updated_fmt: "%b %d, %Y"
```

**Explanation of each setting:**
- `extra_extensions: [autodoc2]` — loads the sphinx-autodoc2 extension.
- `autodoc2_packages` — points autodoc2 at `src/evy` (path is relative to the `docs/` directory because that's where Jupyter Book executes the build).
- `auto_mode: false` — the critical setting. Prevents autodoc2 from auto-crawling submodules. Nothing renders unless explicitly listed on `docs/api-reference.md` via `{autodoc2-object}` directives.
- `autodoc2_render_plugin: myst` — emit MyST (not rST) so the page plays nicely with Jupyter Book.
- `autodoc2_hidden_regexes: [".*\\._.*"]` — second layer of defense; any symbol path containing `._` is hidden. Belt and braces.

- [ ] **Step 3: Verify the YAML is still valid**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('docs/_config.yml'))" && echo "YAML OK"
```

Expected output: `YAML OK`. If this errors, check indentation (YAML is whitespace-sensitive; use spaces, not tabs, in this file).

- [ ] **Step 4: Stage and commit**

```bash
git add docs/_config.yml
git commit -m "Configure sphinx-autodoc2 for evy public API"
```

---

## Task 4: Create `docs/installation.md`

**Files:**
- Create: `docs/installation.md`

**Reasoning on content:** The spec's conditional about "Optional dependencies" resolves to **cut that section**, because `scipy` and `altair` are both listed as core dependencies in `pyproject.toml:25,31`. The page has three sections instead of four.

- [ ] **Step 1: Create the file with full content**

Create `docs/installation.md` with this exact content:

````markdown
# Installation

## Install the package

**Using [uv](https://docs.astral.sh/uv/) (recommended):**

```bash
uv pip install git+https://github.com/datapartnership/evy.git
```

**Using pip:**

```bash
pip install git+https://github.com/datapartnership/evy.git
```

## Backend prerequisites

evy supports two computation backends. You only need to set up the backend you plan to use.

| Backend | Authentication | Best for |
|---|---|---|
| **Google Earth Engine (default)** | Google account + Earth Engine access | Large regions, many years, server-side compute |
| **Local (Planetary Computer)** | None | Small regions, full control over runtime, no account setup |
| **Local (NASA earthaccess)** | NASA Earthdata account | Access to granules not on Planetary Computer |

### Google Earth Engine

1. Sign in at [code.earthengine.google.com](https://code.earthengine.google.com) with a Google account and request access if you don't already have it.
2. Authenticate from Python the first time you use evy:

   ```python
   import evy
   evy.authenticate()
   ```

3. Alternatively, set the `GEE_PROJECT` environment variable to your project ID before running Python. This skips the interactive prompt.

### Planetary Computer (default local backend)

No authentication required. evy uses the public STAC endpoint automatically.

### NASA earthaccess (optional local backend)

1. Create a free NASA Earthdata account at [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov).
2. Persist your credentials once:

   ```python
   import earthaccess
   earthaccess.login(persist=True)
   ```

   Credentials are stored in `~/.netrc` and reused automatically thereafter.

## Verify the install

Run this in Python. If it prints a table of collections without errors, you're set up.

```python
import evy
evy.list_collections()
```
````

- [ ] **Step 2: Verify the file was created**

Run:
```bash
wc -l docs/installation.md
```

Expected: a number (roughly 50–70 lines). The exact count depends on whitespace.

- [ ] **Step 3: Stage and commit**

```bash
git add docs/installation.md
git commit -m "Add installation guide covering both backends"
```

---

## Task 5: Create `docs/api-reference.md`

**Files:**
- Create: `docs/api-reference.md`

- [ ] **Step 1: Create the file with the full wrapper page**

Create `docs/api-reference.md` with this exact content:

````markdown
# API Reference

This page documents evy's public API — the functions and constants exported from the top-level `evy` module. Everything below is reachable as `evy.<name>` without importing submodules.

Symbols beginning with `_` are internal and not part of the public contract. They are intentionally excluded from this reference.

## Boundaries

```{autodoc2-object} evy.get_boundaries
```

```{autodoc2-object} evy.load_boundaries
```

```{autodoc2-object} evy.clear_cache
```

## Collections & Authentication

```{autodoc2-object} evy.list_collections
```

```{autodoc2-object} evy.authenticate
```

```{autodoc2-object} evy.is_authenticated
```

```{autodoc2-object} evy.check_task_status
```

## Zonal Statistics

```{autodoc2-object} evy.zonal_stats
```

```{autodoc2-object} evy.load_modis
```

```{autodoc2-object} evy.load_landcover
```

```{autodoc2-object} evy.compute_zonal_stats
```

## Phenology

```{autodoc2-object} evy.calculate_phenology
```

```{autodoc2-object} evy.extract_phenology
```

```{autodoc2-object} evy.preprocess_series
```

```{autodoc2-object} evy.get_growing_season
```

```{autodoc2-object} evy.filter_growing_season
```

## Visualization

```{autodoc2-object} evy.plot_seasonality
```

```{autodoc2-object} evy.plot_seasonality_by_region
```

```{autodoc2-object} evy.plot_time_series
```

```{autodoc2-object} evy.plot_time_series_by_region
```

```{autodoc2-object} evy.plot_choropleth
```

## Constants

These module-level constants are convenience aliases for common values. They are documented inline here rather than via autodoc2, which does not render string constants cleanly.

| Name | Value | Meaning |
|---|---|---|
| `evy.DAILY` | `"D"` | Daily frequency (pandas offset alias) |
| `evy.WEEKLY` | `"W"` | Weekly frequency |
| `evy.MONTHLY` | `"ME"` | Month-end frequency (default for `zonal_stats`) |
| `evy.QUARTERLY` | `"QE"` | Quarter-end frequency |
| `evy.YEARLY` | `"YE"` | Year-end frequency |
| `evy.CRS` | `"EPSG:4326"` | Default coordinate reference system for inputs and outputs |
````

- [ ] **Step 2: Verify the directive count**

Run:
```bash
grep -c '{autodoc2-object}' docs/api-reference.md
```

Expected output: `21`

This equals the number of public functions in `evy/__init__.py`'s `__all__` (3 boundaries + 4 collections/auth + 4 zonal + 5 phenology + 5 visualization).

- [ ] **Step 3: Stage and commit**

```bash
git add docs/api-reference.md
git commit -m "Add API reference page listing all public functions"
```

---

## Task 6: Create five stub pages for later phases

**Why stubs now:** `_toc.yml` in Task 8 will reference these pages. If they don't exist, the build errors with "file not found." Stubs also signal to the reader what's coming without misleading them about what's present.

**Files:**
- Create: `docs/design-decisions.md`
- Create: `docs/troubleshooting.md`
- Create: `docs/contributing.md`
- Create: `docs/code-of-conduct.md`
- Create: `docs/citation.md`

- [ ] **Step 1: Create `docs/design-decisions.md`**

```markdown
# Design Decisions

This page documents the methodological choices baked into evy: why EVI, which MODIS product, how masking works, and which temporal and spatial defaults apply. It is intended to give researchers the justification they need to defend evy's outputs in a paper.

*This page is a stub and will be written as part of Phase 2.*
```

- [ ] **Step 2: Create `docs/troubleshooting.md`**

```markdown
# Troubleshooting

Common errors and their fixes, organized by the symptom a user sees.

*This page is a stub and will be populated as part of Phase 2.*
```

- [ ] **Step 3: Create `docs/contributing.md`**

```markdown
# Contributing

```{include} CONTRIBUTING.md
```
```

**Note on include path:** `CONTRIBUTING.md` lives in `docs/CONTRIBUTING.md`, so from `docs/contributing.md` the relative path is just `CONTRIBUTING.md`.

- [ ] **Step 4: Create `docs/code-of-conduct.md`**

```markdown
# Code of Conduct

```{include} CODE_OF_CONDUCT.md
```
```

- [ ] **Step 5: Create `docs/citation.md`**

```markdown
# Citation

If you use evy in your research or work, please cite it.

The canonical citation metadata lives in [`CITATION.cff`](https://github.com/datapartnership/evy/blob/main/CITATION.cff) in the repository root. Most reference managers (Zotero, Mendeley, citation.js, etc.) can import `.cff` files directly.
```

- [ ] **Step 6: Verify all five files exist**

Run:
```bash
ls -1 docs/design-decisions.md docs/troubleshooting.md docs/contributing.md docs/code-of-conduct.md docs/citation.md
```

Expected: all five paths printed, one per line, no "No such file" errors.

- [ ] **Step 7: Stage and commit**

```bash
git add docs/design-decisions.md docs/troubleshooting.md docs/contributing.md docs/code-of-conduct.md docs/citation.md
git commit -m "Add stub pages for Phase 2 content and About section"
```

---

## Task 7: Create the `notebooks/recipes/` directory placeholder

**Why:** Phase 3 (cookbook) writes five notebooks under `notebooks/recipes/`. The directory needs to exist (and be tracked by git) so future commits don't have to create it fresh, but it has no content yet.

**Files:**
- Create: `notebooks/recipes/.gitkeep`

- [ ] **Step 1: Create the directory and placeholder file**

Run:
```bash
mkdir -p notebooks/recipes
touch notebooks/recipes/.gitkeep
```

- [ ] **Step 2: Verify**

Run:
```bash
ls -la notebooks/recipes/
```

Expected: shows `.` `..` and `.gitkeep`.

- [ ] **Step 3: Stage and commit**

```bash
git add notebooks/recipes/.gitkeep
git commit -m "Create empty notebooks/recipes directory for cookbook"
```

---

## Task 8: Update `docs/_toc.yml` to the new structure

**Important:** `docs/_toc.yml` is already modified in the working tree (per `git status` at the start of this plan). This task **overwrites** that existing modification. If the in-progress modification is something you want to keep, stash it first — but per the spec, the new structure replaces everything in the current `_toc.yml`.

**Files:**
- Modify: `docs/_toc.yml` (full rewrite)

- [ ] **Step 1: Inspect the current state**

Run:
```bash
cat docs/_toc.yml
```

Note what's there so you can confirm the rewrite replaces it entirely.

- [ ] **Step 2: Write the new `_toc.yml`**

Replace the entire file contents with:

```yaml
format: jb-book
root: README

parts:
  - caption: Getting Started
    chapters:
      - file: docs/installation
      - file: notebooks/quickstart

  - caption: Cookbook
    chapters: []

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

**Note 1 — empty Cookbook:** The `Cookbook` section has `chapters: []` (empty list) rather than omitting the chapters key. Jupyter Book requires `chapters` to exist on a part. An empty list renders the caption but no entries, which is the correct intermediate state until Phase 3 populates it. If Jupyter Book rejects empty `chapters`, fall back to commenting the entire `Cookbook` part out and uncommenting it in Phase 3.

**Note 2 — dropped "Additional Resources" links:** The current `_toc.yml` (pre-rewrite) contains four external `url:` links (Development Data Partnership, World Bank Data Lab, World Bank DEC, World Bank DIME). The spec marks these as "maintainer's choice" — move to README footer or keep in TOC. **This plan drops them from `_toc.yml` entirely.** Rationale: external URL entries clutter a small TOC and duplicate what's already linked in the README. If the maintainer wants them resurrected, they belong in the README footer, not the doc site navigation. This is a deliberate editorial choice; if you disagree, add them back as a fifth part named "Related Projects" with four `url:` chapters.

- [ ] **Step 3: Verify YAML validity**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('docs/_toc.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`.

- [ ] **Step 4: Stage and commit**

```bash
git add docs/_toc.yml
git commit -m "Rewrite docs TOC to new four-part structure"
```

---

## Task 9: Build the book end-to-end and verify

**Goal:** Run a full build. Fix any errors before moving on. This is the exit criterion for Phase 1.

- [ ] **Step 1: Clean any stale build artifacts**

Run:
```bash
rm -rf _build docs/_build
```

Expected: no output (or "No such file or directory" if nothing existed).

- [ ] **Step 2: Run the build**

Run:
```bash
make build
```

Expected: the build proceeds to completion. The final lines should include something like `The HTML pages are in _build/html.` There will be warnings, but the build should not exit with an error code.

**If it fails:** Read the error output carefully. Common failure modes:
- `extension autodoc2 not found` → sphinx-autodoc2 was not injected. Check Task 2 was actually committed and `make -n build` shows `--with sphinx-autodoc2`.
- `no module named 'evy'` → the `autodoc2_packages` path is wrong. Confirm `docs/_config.yml` has `path: ../src/evy` and the build is running from the repo root.
- `file not found: docs/X` → a stub page in Task 6 was not created or was named differently. Cross-check filenames exactly.
- `yaml load error` → `_toc.yml` is malformed. Re-run the Python YAML check from Task 8 Step 3.

- [ ] **Step 3: Check that the API reference rendered**

Run:
```bash
grep -l "get_boundaries" _build/html/docs/api-reference.html
```

Expected: `_build/html/docs/api-reference.html` is printed. This confirms autodoc2 actually pulled the `get_boundaries` docstring into the rendered HTML.

- [ ] **Step 4: Check that every stub page rendered**

Run:
```bash
for f in installation api-reference design-decisions troubleshooting contributing code-of-conduct citation; do
  test -f "_build/html/docs/$f.html" && echo "OK: $f" || echo "MISSING: $f"
done
```

Expected: seven lines, all beginning with `OK:`.

- [ ] **Step 5: Spot-check a rendered page manually**

Run:
```bash
open _build/html/index.html
```

Verify in the browser:
- The TOC on the left shows all four captions (Getting Started, Cookbook, Reference, About).
- The Cookbook caption exists but has no children (Phase 3 hasn't started).
- Clicking "API Reference" shows the 21 public functions grouped into 5 sections plus the Constants table.
- `evy.zonal_stats` has its full docstring including parameter descriptions.

If anything is visibly broken, fix it before moving on.

- [ ] **Step 6: Commit build verification checkpoint (no file changes)**

This task does not produce files to commit. Instead, tag the working tree so subsequent phases know Phase 1 is complete:

```bash
git log --oneline -10
```

Expected: the last 8-9 commits correspond to Tasks 1–8 of this plan. No commit from Task 9 is needed because the build output (`_build/`) is already gitignored.

---

## Done

When every task box above is checked and Task 9 passes, Phase 1 is complete. The site builds, renders, and shows the API reference. Next step: review the output with the user, then write the Phase 2 plan (troubleshooting and design-decisions content).

**Deliberately not done in this plan** (goes into later plans):
- Troubleshooting page content
- Design decisions page content
- Docstring polish on `load_modis`, `load_landcover`, `preprocess_series`
- Any cookbook recipe notebook
- README cleanup (anomaly detection feature claim)
- CLAUDE.md stale-path fix
