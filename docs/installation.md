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
