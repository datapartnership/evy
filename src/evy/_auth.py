"""Google Earth Engine authentication utilities."""

import logging
import os

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

    try:
        import ee
    except ImportError as e:
        raise RuntimeError(
            "earthengine-api is not installed. "
            "Install it with: pip install earthengine-api"
        ) from e

    if project is None:
        project = os.environ.get("GEE_PROJECT")

    try:
        if not force:
            try:
                ee.Initialize(project=project)
                _initialized = True
                logger.info("Earth Engine initialized successfully")
                return
            except ee.EEException:
                pass

        ee.Initialize(project=project)
        _initialized = True
        logger.info("Earth Engine initialized successfully")

    except Exception as e:
        error_msg = str(e)
        if "credentials" in error_msg.lower() or "authenticate" in error_msg.lower():
            raise RuntimeError(
                "Earth Engine authentication required. "
                "Please run 'earthengine authenticate' in your terminal first."
            ) from e
        raise RuntimeError(f"Failed to initialize Earth Engine: {e}") from e


def is_authenticated() -> bool:
    """
    Check if Earth Engine is authenticated and initialized.

    Returns
    -------
    bool
        True if authenticated and initialized, False otherwise
    """
    global _initialized

    if _initialized:
        return True

    try:
        import ee

        # Try a simple operation to verify authentication
        ee.Initialize()
        _initialized = True
        return True
    except Exception:
        return False


def _ensure_initialized(project: str | None = None) -> None:
    """
    Internal function to ensure GEE is initialized.

    Called by other modules before performing GEE operations.
    """
    if not _initialized:
        authenticate(project=project)
