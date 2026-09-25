"""Conversion utilities for GEE to pandas/geopandas."""

import logging

import ee
import pandas as pd

logger = logging.getLogger(__name__)


def fc_to_dataframe(
    fc: ee.FeatureCollection,
    date_column: str = "date",
) -> pd.DataFrame:
    """
    Convert a GEE FeatureCollection of zonal statistics to a DataFrame.

    Fetches every page of results through ``ee.data.computeFeatures``, so
    results larger than the 5,000-element limit of ``getInfo()`` are
    returned in full (for example, 300 zones x 24 months = 7,200 rows).

    Parameters
    ----------
    fc:
        Earth Engine FeatureCollection with zonal statistics. Geometries
        are expected to be stripped already; only properties are returned.
    date_column:
        Name of the date column in the output

    Returns
    -------
    pd.DataFrame
        One row per feature, one column per feature property.

    Raises
    ------
    RuntimeError
        If conversion fails
    """
    try:
        df = ee.data.computeFeatures(
            {"expression": fc, "fileFormat": "PANDAS_DATAFRAME"}
        )
    except Exception as e:
        raise RuntimeError(f"Failed to convert FeatureCollection: {e}") from e

    # The pandas converter adds a "geo" column for geometry, which is null here.
    df = df.drop(columns="geo", errors="ignore")

    if df.empty:
        logger.warning("No features in FeatureCollection")
        return pd.DataFrame(columns=[date_column])

    if date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column])
    return df


def export_to_drive(
    fc: ee.FeatureCollection,
    filename: str,
    folder: str = "evy_exports",
    file_format: str = "CSV",
    selectors: list[str] | None = None,
) -> str:
    """
    Export FeatureCollection to Google Drive.

    Parameters
    ----------
    fc:
        Earth Engine FeatureCollection to export
    filename:
        Name for the exported file (without extension)
    folder:
        Google Drive folder name
    file_format:
        Export format ('CSV', 'GeoJSON', 'KML', etc.)
    selectors:
        Columns to write, in order. Without it, GEE also writes its
        internal ``system:index`` and ``.geo`` columns.

    Returns
    -------
    str
        Task ID for the export task
    """
    task = ee.batch.Export.table.toDrive(
        collection=fc,
        description=filename,
        folder=folder,
        fileFormat=file_format,
        selectors=selectors,
    )
    task.start()

    logger.info(f"Export task started: {task.id}")
    logger.info(
        f"File will be saved to Google Drive/{folder}/{filename}.{file_format.lower()}"
    )

    return task.id


def check_task_status(task_id: str) -> dict:
    """
    Check the status of an Earth Engine export task.

    Parameters
    ----------
    task_id : str
        Task ID returned from export_to_drive

    Returns
    -------
    dict
        Task status with keys:
        - 'state': Task state ('READY', 'RUNNING', 'COMPLETED', 'FAILED')
        - 'description': Task description
        - 'progress': Progress percentage (if available)
    """
    tasks = ee.batch.Task.list()

    for task in tasks:
        if task.id == task_id:
            status = task.status()
            return {
                "state": status.get("state"),
                "description": status.get("description"),
                "progress": status.get("progress", 0),
            }

    return {"state": "NOT_FOUND", "description": "Task not found", "progress": 0}
