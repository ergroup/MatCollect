"""Functions for rendering streamlit sliders."""

import pandas as pd
import streamlit as st


def make_range_slider(df: pd.DataFrame,
                      column: str,
                      step: float | None = None) -> tuple:
    """Render a range slider with fallbacks for empty or uniform data."""
    valid = df[column].dropna()
    column_display_name = column.replace("_", " ").title()

    with st.container():
        slider_col, toggle_col = st.columns([3, 1], vertical_alignment="bottom")

        if valid.empty:
            with slider_col:
                st.info(f"No {column_display_name} data available")
            return (None, None), False

        cast = float if step is not None else int
        vmin, vmax = cast(valid.min()), cast(valid.max())

        with slider_col:
            if vmin == vmax:
                st.info(f"{column_display_name} values are identical")
                selected = (vmin, vmax)
            else:
                selected = st.slider(
                    f"{column_display_name} Range:",
                    min_value=vmin,
                    max_value=vmax,
                    value=(vmin, vmax),
                    **({"step": step} if step is not None else {})
                )

        with toggle_col:
            include_nan = st.toggle(
                "Include NaN",
                value=True,
                key=f"include_nan_{column}"
            )

    return selected, include_nan

def filter_numeric_with_nan(df: pd.DataFrame,
                            column: str,
                            range_tuple: tuple | None,
                            include_nan: bool=False) -> pd.DataFrame:
    """Filter a numeric column by range, optionally retaining NaN rows."""
    if range_tuple is None or range_tuple == (None, None):
        return df
    in_range = df[column].between(*range_tuple)
    if include_nan:
        return df[in_range | df[column].isna()]
    return df[in_range]
