# evy

[![GitHub Release](https://img.shields.io/github/v/release/datapartnership/evy)](https://github.com/datapartnership/evy/releases)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**evy** is a Python package for fetching, processing, and analyzing Enhanced Vegetation Index (EVI) data from MODIS satellite imagery. It provides a high-level interface to work with vegetation data, enabling researchers and practitioners to monitor vegetation health, compute phenological metrics, and perform zonal statistics with ease.

> **Note:** This package is a work in progress. Features and APIs may change as development continues.

## Features

- **Easy Data Access**: Fetch MODIS EVI data from Planetary Computer with automatic quality masking
- **Zonal Statistics**: Compute statistics (mean, median, max, etc.) for specific geometries
- **Temporal Aggregation**: Aggregate data at various temporal frequencies (monthly, yearly, quarterly)
- **Phenology Analysis**: Extract and visualize vegetation growing seasons and phenological patterns
- **Land Cover Masking**: Filter EVI data by land cover classification (e.g., cropland-only analysis)
- **Visualization**: Built-in plotting functions for time series and phenology

## Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv pip install git+https://github.com/datapartnership/evy.git
```

Or using pip:

```bash
pip install git+https://github.com/datapartnership/evy.git
```

## Examples

For detailed examples, see the [notebooks/](notebooks/) directory:
- [quickstart.ipynb](notebooks/quickstart.ipynb): Comprehensive walkthrough of main features

## Citation

If you use this package in your research or work, please cite it using the information in [CITATION.cff](CITATION.cff).

## License

This project is licensed under the Mozilla Public License 2.0 - see the [LICENSE](LICENSE) file for details.