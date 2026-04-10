"""evy - Vegetation Index Zonal Statistics"""

from evy.zonal import zonal_stats
from evy.boundaries import clear_cache, get_boundaries, load_boundaries

from evy.collections import list_collections
from evy._auth import authenticate, is_authenticated
from evy._convert import check_task_status
from evy.load import load_modis, load_landcover
from evy._zonal_local import compute_zonal_stats

from evy.phenology import (
    calculate_phenology,
    extract_phenology,
    filter_growing_season,
    get_growing_season,
    preprocess_series,
)

from evy.viz import (
    plot_choropleth,
    plot_seasonality,
    plot_seasonality_by_region,
    plot_time_series,
    plot_time_series_by_region,
)


DAILY = "D"
WEEKLY = "W"
MONTHLY = "ME"
QUARTERLY = "QE"
YEARLY = "YE"
ANNUAL = "YE"
CRS = "EPSG:4326"

__all__ = [
    # Main function
    "zonal_stats",
    "load_modis",
    "load_landcover",
    "compute_zonal_stats",
    # Boundary functions
    "get_boundaries",
    "load_boundaries",
    "clear_cache",
    # Collections and authentication functions
    "list_collections",
    "authenticate",
    "is_authenticated",
    "check_task_status",
    # Phenology functions
    "calculate_phenology",
    "extract_phenology",
    "preprocess_series",
    "get_growing_season",
    "filter_growing_season",
    # Visualization functions
    "plot_seasonality",
    "plot_seasonality_by_region",
    "plot_time_series",
    "plot_time_series_by_region",
    "plot_choropleth",
    # Constants
    "DAILY",
    "WEEKLY",
    "MONTHLY",
    "QUARTERLY",
    "YEARLY",
    "CRS",
]
