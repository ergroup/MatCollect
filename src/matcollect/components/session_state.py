"""Function for initializing and resetting the session state."""

import streamlit as st


def initialize_session_state():  # noqa: C901, PLR0912
    """
    Initialize the session state by setting default values for various
    session state variables.

    This function is called when the app is first loaded and when the
    user resets the session state.

    The session state variables that are reset include:

    - Selected providers
    - Materials extracted from providers
    - Materials after retrieval and filtering
    - Materials after deduplication
    - Stability dataset selection
    - Materials after stability analysis
    - Stable materials after stability filtering
    - Duplicative graph figures
    - Stability figures
    - Figure zip files
    """
    # Selected providers
    if "selected_providers" not in st.session_state:
        st.session_state.selected_providers = []

    # Materials extracted from providers
    if "extracted_materials" not in st.session_state:
        st.session_state.extracted_materials = {}
    if "extracted_materials_summary" not in st.session_state:
        st.session_state.extracted_materials_summary = None

    # Materials after retrieval and filtering
    if "filtered_materials" not in st.session_state:
        st.session_state.filtered_materials = {}
    if "filtered_materials_summary" not in st.session_state:
        st.session_state.filtered_materials_summary = None

    # Materials after deduplication
    if "unique_materials" not in st.session_state:
        st.session_state.unique_materials = {}
    if "unique_materials_summary" not in st.session_state:
        st.session_state.unique_materials_summary = None

    # Stability dataset selection
    if "stability_selected_materials" not in st.session_state:
        st.session_state.stability_selected_materials = {}
    if "stability_selected_materials_summary" not in st.session_state:
        st.session_state.stability_selected_materials_summary = None

    # Materials after stability analysis
    if "stability_candidate_materials" not in st.session_state:
        st.session_state.stability_candidate_materials = {}
    if "stability_candidate_materials_summary" not in st.session_state:
        st.session_state.stability_candidate_materials_summary = None

    # Stable materials after stability filtering
    if "stable_materials" not in st.session_state:
        st.session_state.stable_materials = {}
    if "stable_materials_summary" not in st.session_state:
        st.session_state.stable_materials_summary = None

    # Duplicaate graph figures
    if "duplicate_graphs" not in st.session_state:
        st.session_state.duplicate_graphs = None
    # Stability figures
    if "pourbaix_figures" not in st.session_state:
        st.session_state.pourbaix_figures = None
    if "e_above_hull_figures" not in st.session_state:
        st.session_state.e_above_hull_figures = None

    # Figure zip files
    if "duplicate_graphs_zip" not in st.session_state:
        st.session_state.duplicate_graphs_zip = None
    if "e_above_hull_figures_zip" not in st.session_state:
        st.session_state.e_above_hull_figures_zip = None
    if "pourbaix_figures_zip" not in st.session_state:
        st.session_state.pourbaix_figures_zip = None


def reset_session_state():
    """Reset the session state by clearing all session state variables to their default values."""
    st.session_state.selected_providers = []
    st.session_state.extracted_materials = {}
    st.session_state.extracted_materials_summary = None
    st.session_state.filtered_materials = {}
    st.session_state.filtered_materials_summary = None
    st.session_state.unique_materials = {}
    st.session_state.unique_materials_summary = None
    st.session_state.stability_selected_materials = {}
    st.session_state.stability_selected_materials_summary = None
    st.session_state.stability_candidate_materials = {}
    st.session_state.stability_candidate_materials_summary = None
    st.session_state.stable_materials = {}
    st.session_state.stable_materials_summary = None
    st.session_state.pourbaix_figures = None
    st.session_state.e_above_hull_figures = None
    st.session_state.duplicate_graphs = None
    st.session_state.calibration_report = None
    st.session_state.duplicate_graphs_zip = None
    st.session_state.e_above_hull_figures_zip = None
    st.session_state.pourbaix_figures_zip = None

def reset_result_states():
    """
    Reset only the session state variables related to results,
    keeping selected providers intact.
    """
    st.session_state.extracted_materials = {}
    st.session_state.extracted_materials_summary = None
    st.session_state.filtered_materials = {}
    st.session_state.filtered_materials_summary = None
    st.session_state.unique_materials = {}
    st.session_state.unique_materials_summary = None
    st.session_state.stability_selected_materials = {}
    st.session_state.stability_selected_materials_summary = None
    st.session_state.stability_candidate_materials = {}
    st.session_state.stability_candidate_materials_summary = None
    st.session_state.stable_materials = {}
    st.session_state.stable_materials_summary = None
    st.session_state.pourbaix_figures = None
    st.session_state.e_above_hull_figures = None
    st.session_state.duplicate_graphs = None
    st.session_state.calibration_report = None
    st.session_state.duplicate_graphs_zip = None
    st.session_state.e_above_hull_figures_zip = None
    st.session_state.pourbaix_figures_zip = None
