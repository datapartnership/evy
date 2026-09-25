"""Tests for the STAC-backed local-backend loaders in evy.load."""

from unittest.mock import MagicMock, patch

import pytest
from pystac_client.exceptions import APIError

from evy.load import EmptyStacResultError, load_landcover, load_modis


@patch("evy.load.pystac_client.Client.open")
def test_load_modis_raises_on_empty_stac_result(mock_open, small_boundaries):
    """Empty STAC result must fail loudly, not silently return empty data."""
    fake_search = MagicMock()
    fake_search.items.return_value = iter([])
    fake_catalog = MagicMock()
    fake_catalog.search.return_value = fake_search
    mock_open.return_value = fake_catalog

    with pytest.raises(EmptyStacResultError) as excinfo:
        load_modis(small_boundaries, "2023-01-01", "2023-01-31")

    message = str(excinfo.value)
    assert "modis-13Q1-061" in message
    assert "2023-01-01/2023-01-31" in message


@patch("evy.load.pystac_client.Client.open")
def test_load_landcover_raises_on_empty_stac_result(mock_open, small_boundaries):
    """load_landcover must also guard against empty STAC results."""
    ds_evi = MagicMock()
    fake_search = MagicMock()
    fake_search.items.return_value = iter([])
    fake_catalog = MagicMock()
    fake_catalog.search.return_value = fake_search
    mock_open.return_value = fake_catalog

    with pytest.raises(EmptyStacResultError) as excinfo:
        load_landcover(small_boundaries, ds_evi)

    assert "esa-worldcover" in str(excinfo.value)


@patch("evy.load.odc_stac.load")
@patch("evy.load.pystac_client.Client.open")
def test_load_modis_passes_items_to_odc(
    mock_open, mock_odc_load, small_boundaries, fake_stac_item
):
    """When the STAC search returns items, they should be forwarded to odc-stac.load."""
    fake_search = MagicMock()
    fake_search.items.return_value = iter([fake_stac_item])
    fake_catalog = MagicMock()
    fake_catalog.search.return_value = fake_search
    mock_open.return_value = fake_catalog

    # Build a minimal fake Dataset that supports the .rename call we make.
    fake_ds = MagicMock()
    fake_ds.rename.return_value = fake_ds
    fake_ds.sel.return_value = fake_ds
    mock_odc_load.return_value = fake_ds

    result = load_modis(small_boundaries, "2023-01-01", "2023-01-31")

    assert result is fake_ds
    # Items were materialized to a list (not an iterator) when passed downstream.
    _, kwargs = mock_odc_load.call_args
    items_arg = mock_odc_load.call_args[0][0]
    assert isinstance(items_arg, list)
    assert len(items_arg) == 1
    assert items_arg[0] is fake_stac_item
    assert kwargs["bands"] == [
        "250m_16_days_EVI",
        "250m_16_days_pixel_reliability",
    ]


@patch("evy.load._stac_search.retry.sleep", lambda _: None)
@patch("evy.load.pystac_client.Client.open")
def test_load_modis_retries_on_network_error(mock_open, small_boundaries):
    """pystac-client wraps network failures in APIError; those must be retried."""
    success_search = MagicMock()
    success_search.items.return_value = iter(
        []
    )  # empty -> raises EmptyStacResultError, not the connection error
    success_catalog = MagicMock()
    success_catalog.search.return_value = success_search

    # Two network failures (no HTTP status), then success.
    mock_open.side_effect = [
        APIError("Connection aborted"),
        APIError("Read timed out"),
        success_catalog,
    ]

    with pytest.raises(EmptyStacResultError):
        load_modis(small_boundaries, "2023-01-01", "2023-01-31")

    # Three open attempts confirm retry behavior.
    assert mock_open.call_count == 3


@patch("evy.load.pystac_client.Client.open")
def test_stac_search_does_not_retry_client_errors(mock_open, small_boundaries):
    """A 4xx error will fail the same way again, so it must not be retried."""
    not_found = APIError("Not Found")
    not_found.status_code = 404
    mock_open.side_effect = not_found

    with pytest.raises(APIError):
        load_modis(small_boundaries, "2023-01-01", "2023-01-31")
    assert mock_open.call_count == 1
