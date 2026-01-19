"""Conversion utilities for GEE to pandas/geopandas."""

import logging

import ee
import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)

CRS = "EPSG:4326"


def fc_to_dataframe(
    fc: ee.FeatureCollection,
    include_geometry: bool = False,
    date_column: str = "date",
) -> pd.DataFrame | gpd.GeoDataFrame:
    """
    Convert GEE FeatureCollection to pandas DataFrame or GeoDataFrame.

    Parameters
    ----------
    fc:
        Earth Engine FeatureCollection with zonal statistics
    include_geometry:
        If True, return GeoDataFrame with geometry column.
        If False, return pandas DataFrame (smaller, faster).
    date_column:
        Name of the date column in the output

    Returns
    -------
    pd.DataFrame or gpd.GeoDataFrame
        Zonal statistics as tabular data

    Raises
    ------
    RuntimeError
        If conversion fails
    """
    try:
        fc_info = fc.getInfo()

        if not fc_info or "features" not in fc_info:
            logger.warning("Empty FeatureCollection returned")
            if include_geometry:
                return gpd.GeoDataFrame(columns=[date_column], crs=CRS)
            return pd.DataFrame(columns=[date_column])

        features = fc_info["features"]

        if not features:
            logger.warning("No features in FeatureCollection")
            if include_geometry:
                return gpd.GeoDataFrame(columns=[date_column], crs=CRS)
            return pd.DataFrame(columns=[date_column])

        if include_geometry:
            gdf = gpd.GeoDataFrame.from_features(features, crs=CRS)
            if date_column in gdf.columns:
                gdf[date_column] = pd.to_datetime(gdf[date_column])
            return gdf
        else:
            records = [f["properties"] for f in features]
            df = pd.DataFrame(records)
            if date_column in df.columns:
                df[date_column] = pd.to_datetime(df[date_column])
            return df

    except Exception as e:
        raise RuntimeError(f"Failed to convert FeatureCollection: {e}") from e


def export_to_drive(
    fc: ee.FeatureCollection,
    filename: str,
    folder: str = "evy_exports",
    file_format: str = "CSV",
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

    Returns
    -------
    str
        Task ID for the export task
    """
    import ee

    task = ee.batch.Export.table.toDrive(
        collection=fc,
        description=filename,
        folder=folder,
        fileFormat=file_format,
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
    import ee

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
