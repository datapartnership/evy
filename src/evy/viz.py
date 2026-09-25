"""Visualization functions using Altair."""

import logging

import pandas as pd
import geopandas as gpd

try:
    import altair as alt

    HAS_ALTAIR = True
except ImportError:
    HAS_ALTAIR = False

logger = logging.getLogger(__name__)

# Month name mapping
MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


def _check_altair():
    """Check if altair is available."""
    if not HAS_ALTAIR:
        raise ImportError(
            "altair is required for visualization. Install it with: pip install altair"
        )


def plot_seasonality(
    df: pd.DataFrame,
    value_col: str = "value",
    smoothed_col: str = "smoothed",
    month_col: str = "month",
    sos_col: str = "sos",
    mos_col: str = "mos",
    eos_col: str = "eos",
    title: str = "Crop Seasonality based on EVI",
    width: int = 600,
    height: int = 400,
) -> "alt.Chart":
    """
    Create a seasonality chart showing EVI throughout the year.

    Displays raw values as points, smoothed values as a line,
    and phenology markers (SOS, MOS, EOS) as vertical dashed lines.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame from calculate_phenology() with monthly aggregated data
    value_col : str, default 'value'
        Column with raw/mean values
    smoothed_col : str, default 'smoothed'
        Column with smoothed values
    month_col : str, default 'month'
        Column with month numbers (1-12)
    sos_col : str, default 'sos'
        Column with start of season month
    mos_col : str, default 'mos'
        Column with middle of season month
    eos_col : str, default 'eos'
        Column with end of season month
    title : str, default 'Crop Seasonality based on EVI'
        Chart title
    width : int, default 600
        Chart width in pixels
    height : int, default 400
        Chart height in pixels

    Returns
    -------
    alt.Chart
        Altair chart object

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('SYR', admin_level=1)
    >>> df = evy.zonal_stats(gdf, zone_col='shapeName', freq='Original')
    >>> phenology = evy.calculate_phenology(df)
    >>> chart = evy.plot_seasonality(phenology)
    >>> chart.display()  # or chart.save('seasonality.html')
    """
    _check_altair()

    base = alt.Chart(df)

    # Points for raw values
    points = base.mark_circle(color="steelblue", size=60).encode(
        x=alt.X(
            f"{month_col}:O",
            scale=alt.Scale(domain=list(range(1, 13))),
            axis=alt.Axis(
                labelExpr="['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][datum.value-1]",
                title="",
            ),
        ),
        y=alt.Y(f"{value_col}:Q", title="EVI"),
        tooltip=[
            alt.Tooltip(f"{month_col}:O", title="Month"),
            alt.Tooltip(f"{value_col}:Q", title="EVI", format=".3f"),
        ],
    )

    # Line for smoothed values
    line = base.mark_line(color="black").encode(
        x=f"{month_col}:O",
        y=f"{smoothed_col}:Q",
        tooltip=[
            alt.Tooltip(f"{month_col}:O", title="Month"),
            alt.Tooltip(f"{smoothed_col}:Q", title="Smoothed EVI", format=".3f"),
        ],
    )

    # Vertical lines for SOS, MOS, EOS
    sos_line = (
        base.mark_rule(strokeDash=[5, 5], color="green")
        .encode(x=f"{sos_col}:O")
        .transform_filter(alt.expr.isValid(alt.datum[sos_col]))
    )

    mos_line = (
        base.mark_rule(strokeDash=[5, 5], color="orange")
        .encode(x=f"{mos_col}:O")
        .transform_filter(alt.expr.isValid(alt.datum[mos_col]))
    )

    eos_line = (
        base.mark_rule(strokeDash=[5, 5], color="red")
        .encode(x=f"{eos_col}:O")
        .transform_filter(alt.expr.isValid(alt.datum[eos_col]))
    )

    chart = (points + line + sos_line + mos_line + eos_line).properties(
        title=title, width=width, height=height
    )

    return chart


def plot_seasonality_by_region(
    df: pd.DataFrame,
    region_col: str = "shapeName",
    value_col: str = "value",
    smoothed_col: str = "smoothed",
    month_col: str = "month",
    sos_col: str = "sos",
    mos_col: str = "mos",
    eos_col: str = "eos",
    columns: int = 4,
    width: int = 150,
    height: int = 100,
    title: str = "EVI Seasonality by Region",
) -> "alt.Chart":
    """
    Create faceted seasonality charts for multiple regions.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame from calculate_phenology() with group_col specified
    region_col : str, default 'shapeName'
        Column with region names for faceting
    value_col : str, default 'value'
        Column with raw/mean values
    smoothed_col : str, default 'smoothed'
        Column with smoothed values
    month_col : str, default 'month'
        Column with month numbers (1-12)
    sos_col : str, default 'sos'
        Column with start of season month
    mos_col : str, default 'mos'
        Column with middle of season month
    eos_col : str, default 'eos'
        Column with end of season month
    columns : int, default 4
        Number of columns in faceted grid
    width : int, default 150
        Width of each facet
    height : int, default 100
        Height of each facet
    title : str, default 'EVI Seasonality by Region'
        Chart title

    Returns
    -------
    alt.Chart
        Altair faceted chart object

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('SYR', admin_level=1)
    >>> df = evy.zonal_stats(gdf, zone_col='shapeName', freq='Original')
    >>> phenology = evy.calculate_phenology(df, group_col='shapeName')
    >>> chart = evy.plot_seasonality_by_region(phenology)
    >>> chart.display()
    """
    _check_altair()

    # Add month name for tooltip
    df = df.copy()
    df["month_name"] = df[month_col].map(MONTH_NAMES)

    nearest = alt.selection_point(
        nearest=True, on="pointerover", fields=[month_col], empty=False
    )
    when_near = alt.when(nearest)

    # Line chart
    line = (
        alt.Chart(df)
        .mark_line(color="black")
        .encode(
            x=alt.X(
                f"{month_col}:O",
                axis=alt.Axis(
                    labelExpr="['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][datum.value-1]",
                    title="",
                ),
            ),
            y=alt.Y(f"{smoothed_col}:Q", axis=alt.Axis(title="")),
        )
        .properties(width=width, height=height)
    )

    # Points
    points = (
        alt.Chart(df)
        .mark_circle(color="steelblue", size=30)
        .encode(
            x=f"{month_col}:O",
            y=f"{value_col}:Q",
        )
    )

    # Vertical lines for phenology markers
    vertical_lines = (
        (
            alt.Chart(df)
            .mark_rule(strokeDash=[5, 5], color="gray")
            .encode(x=f"{sos_col}:O")
            .transform_filter(alt.expr.isValid(alt.datum[sos_col]))
        )
        + (
            alt.Chart(df)
            .mark_rule(strokeDash=[5, 5], color="gray")
            .encode(x=f"{mos_col}:O")
            .transform_filter(alt.expr.isValid(alt.datum[mos_col]))
        )
        + (
            alt.Chart(df)
            .mark_rule(strokeDash=[5, 5], color="gray")
            .encode(x=f"{eos_col}:O")
            .transform_filter(alt.expr.isValid(alt.datum[eos_col]))
        )
    )

    # Tooltip
    tooltip = (
        alt.Chart(df)
        .mark_rule(color="gray")
        .encode(
            x=f"{month_col}:O",
            opacity=when_near.then(alt.value(0.3)).otherwise(alt.value(0)),
            tooltip=[
                alt.Tooltip("month_name:N", title="Month"),
                alt.Tooltip(f"{smoothed_col}:Q", title="Smoothed EVI", format=".3f"),
                alt.Tooltip(f"{value_col}:Q", title="Average EVI", format=".3f"),
            ],
        )
        .add_params(nearest)
    )

    chart = (
        alt.layer(line, points, vertical_lines, tooltip)
        .facet(
            facet=alt.Facet(f"{region_col}:N", header=alt.Header(title=None)),
            columns=columns,
        )
        .resolve_scale(y="independent")
        .configure_title(anchor="start", subtitleFontSize=10, subtitleColor="gray")
        .properties(
            title={
                "text": title,
                "subtitle": "Smoothed lines represent seasonal trends; points represent average EVI values",
            }
        )
    )

    return chart


def plot_time_series(
    df: pd.DataFrame,
    value_col: str = "mean",
    date_col: str = "date",
    title: str = "EVI Time Series",
    width: int = 600,
    height: int = 300,
    y_domain: tuple[float, float] | None = None,
) -> "alt.Chart":
    """
    Create a time series line chart.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with time series data
    value_col : str, default 'mean'
        Column with values to plot
    date_col : str, default 'date'
        Column with dates
    title : str, default 'EVI Time Series'
        Chart title
    width : int, default 600
        Chart width in pixels
    height : int, default 300
        Chart height in pixels
    y_domain : tuple[float, float], optional
        Y-axis domain (min, max). If None, auto-scaled.

    Returns
    -------
    alt.Chart
        Altair chart object

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('SYR', admin_level=1)
    >>> df = evy.zonal_stats(gdf, zone_col='shapeName', freq='ME')
    >>> chart = evy.plot_time_series(df)
    >>> chart.display()
    """
    _check_altair()

    nearest = alt.selection_point(
        nearest=True, on="pointerover", fields=[date_col], empty=False
    )
    when_near = alt.when(nearest)

    y_encoding = alt.Y(f"{value_col}:Q", title="EVI")
    if y_domain is not None:
        y_encoding = alt.Y(
            f"{value_col}:Q", title="EVI", scale=alt.Scale(domain=list(y_domain))
        )

    line = (
        alt.Chart(df, title=title)
        .mark_line(point=True)
        .encode(
            x=alt.X(f"{date_col}:T", title=""),
            y=y_encoding,
        )
    )

    tooltip = (
        alt.Chart(df)
        .mark_rule(color="gray")
        .encode(
            x=alt.X(f"{date_col}:T", axis=alt.Axis(grid=False)),
            opacity=when_near.then(alt.value(0.3)).otherwise(alt.value(0)),
            tooltip=[
                alt.Tooltip(date_col, title="Date", timeUnit="yearmonth"),
                alt.Tooltip(value_col, title="EVI", format=".3f"),
            ],
        )
        .add_params(nearest)
    )

    chart = alt.layer(line, tooltip).properties(width=width, height=height)

    return chart


def plot_time_series_by_region(
    df: pd.DataFrame,
    region_col: str = "shapeName",
    value_col: str = "mean",
    date_col: str = "date",
    columns: int = 4,
    width: int = 160,
    height: int = 100,
    title: str = "EVI Time Series by Region",
) -> "alt.Chart":
    """
    Create faceted time series charts for multiple regions.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with time series data
    region_col : str, default 'shapeName'
        Column with region names for faceting
    value_col : str, default 'mean'
        Column with values to plot
    date_col : str, default 'date'
        Column with dates
    columns : int, default 4
        Number of columns in faceted grid
    width : int, default 160
        Width of each facet
    height : int, default 100
        Height of each facet
    title : str, default 'EVI Time Series by Region'
        Chart title

    Returns
    -------
    alt.Chart
        Altair faceted chart object

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('SYR', admin_level=1)
    >>> df = evy.zonal_stats(gdf, zone_col='shapeName', freq='YE')
    >>> chart = evy.plot_time_series_by_region(df)
    >>> chart.display()
    """
    _check_altair()

    nearest = alt.selection_point(
        nearest=True, on="pointerover", fields=[date_col], empty=False
    )
    when_near = alt.when(nearest)

    line = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X(f"{date_col}:T", title=""),
            y=alt.Y(f"{value_col}:Q", title=""),
        )
        .properties(width=width, height=height)
    )

    tooltip = (
        alt.Chart(df)
        .mark_rule(color="gray")
        .encode(
            x=f"{date_col}:T",
            opacity=when_near.then(alt.value(0.3)).otherwise(alt.value(0)),
            tooltip=[
                alt.Tooltip(f"{date_col}:T", title="Date", timeUnit="yearmonth"),
                alt.Tooltip(f"{value_col}:Q", format=".3f", title="EVI"),
            ],
        )
        .add_params(nearest)
    )

    chart = (
        alt.layer(line, tooltip)
        .facet(
            facet=alt.Facet(f"{region_col}:N", header=alt.Header(title=None)),
            columns=columns,
        )
        .configure_title(anchor="start", subtitleFontSize=10, subtitleColor="gray")
        .properties(title=title)
    )

    return chart


def plot_choropleth(
    df: pd.DataFrame,
    geodata: gpd.GeoDataFrame,
    value_col: str = "mean",
    region_col: str = "shapeName",
    geo_key: str = "PCODE",
    df_key: str = "PCODE",
    title: str = "EVI by Region",
    width: int = 400,
    height: int = 400,
    color_scheme: str = "greens",
) -> "alt.Chart":
    """
    Create a choropleth map colored by vegetation index values.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with aggregated values per region
    geodata : gpd.GeoDataFrame
        GeoDataFrame with region geometries
    value_col : str, default 'mean'
        Column with values for coloring
    region_col : str, default 'shapeName'
        Column with region names for tooltip
    geo_key : str, default 'PCODE'
        Column in geodata to join on
    df_key : str, default 'PCODE'
        Column in df to join on
    title : str, default 'EVI by Region'
        Chart title
    width : int, default 400
        Chart width in pixels
    height : int, default 400
        Chart height in pixels
    color_scheme : str, default 'greens'
        Altair color scheme name

    Returns
    -------
    alt.Chart
        Altair chart object

    Examples
    --------
    >>> import evy
    >>> gdf = evy.get_boundaries('SYR', admin_level=1)
    >>> df = evy.zonal_stats(
    ...     gdf, zone_col='shapeName', freq='YE', include_geometry=True
    ... )
    >>> chart = evy.plot_choropleth(df, gdf)
    >>> chart.display()
    """
    _check_altair()

    chart = (
        alt.Chart(df, title=title)
        .mark_geoshape(stroke="white", strokeWidth=1.5)
        .encode(
            shape="geo:G",
            color=alt.Color(
                f"{value_col}:Q", scale=alt.Scale(scheme=color_scheme), title="EVI"
            ),
            tooltip=[
                alt.Tooltip(f"{region_col}:N", title="Region"),
                alt.Tooltip(f"{value_col}:Q", title="EVI", format=".3f"),
            ],
        )
        .transform_lookup(
            lookup=df_key,
            from_=alt.LookupData(data=geodata, key=geo_key),
            as_="geo",
        )
        .properties(width=width, height=height)
    )

    return chart
