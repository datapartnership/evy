"""Google Earth Engine authentication utilities."""

import logging
import os

import ee

logger = logging.getLogger(__name__)

_initialized = False


def authenticate(project: str | None = None, force: bool = False) -> None:
    """
    Initialize Google Earth Engine authentication.

    Called automatically by other functions, but can be called explicitly
    to ensure authentication before starting analysis.

    Parameters
    ----------
    project:
        GEE project ID. If None, uses:
        1. GEE_PROJECT environment variable
        2. Default project from gcloud config
    force:
        Force re-initialization even if already initialized

    Raises
    ------
    RuntimeError
        If authentication fails (prompts user to run 'earthengine authenticate')
    """
    global _initialized

    if _initialized and not force:
        logger.debug("Earth Engine already initialized")
        return

    if project is None:
        project = os.environ.get("GEE_PROJECT")

    try:
        ee.Initialize(project=project)
    except Exception as e:
        error_msg = str(e).lower()
        if "credentials" in error_msg or "authenticate" in error_msg:
            raise RuntimeError(
                "Earth Engine authentication required. "
                "Please run 'earthengine authenticate' in your terminal first."
            ) from e
        raise RuntimeError(f"Failed to initialize Earth Engine: {e}") from e

    _initialized = True
    logger.info("Earth Engine initialized successfully")


def is_authenticated() -> bool:
    """
    Check if Earth Engine is initialized, without initializing it.

    Returns
    -------
    bool
        True if Earth Engine is initialized in this session, False otherwise.
        Call :func:`authenticate` to initialize it.
    """
    return _initialized or ee.data.is_initialized()


def _ensure_initialized(project: str | None = None) -> None:
    """
    Internal function to ensure GEE is initialized.

    Called by other modules before performing GEE operations.
    """
    if not _initialized:
        authenticate(project=project)
