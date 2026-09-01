"""Streamlit page responsible for removing duplicate materials."""

import time
from pathlib import Path

import streamlit as st
from streamlit_sortables import sort_items

from matcollect.components.download import render_download, show_download_button
from matcollect.components.session_state import initialize_session_state
from matcollect.components.sidebar import render_sidebar
from matcollect.core.duplicate_removal.duplicate_remover import DuplicateRemover
from matcollect.core.utils.misc import download_duplicate_figures
from matcollect.core.utils.modal_ase_viewer import show_material
from matcollect.core.utils.summarizer import summarize_materials_dict

# Base directory of the current file
BASE_DIR = Path(__file__).resolve().parent

pages = [
    BASE_DIR / "database_search.py",
    BASE_DIR / "stability_analysis.py"
]


st.set_page_config(layout="wide", page_icon="assets/images/matcollect.ico")

# Logo
st.logo("assets/images/matcollect_logo_with_text.png", icon_image="assets/images/matcollect.ico")

st.title("Duplicate Removal")

# Initialize the session state
initialize_session_state()

# Sidebar
render_sidebar()

if (st.session_state.filtered_materials == {} or
    st.session_state.filtered_materials_summary is None):
    st.error("Please search for materials first.", icon="⚠️")
else:
    duplicate_priority_container = st.container(
        border=True, key="duplicate_priority_container")
    with duplicate_priority_container:
        database_col, tolerance_col = st.columns(2, gap="medium")
        with database_col:
            st.subheader("Set the priority for the databases")
            st.write("The databases with higher priority will be used first for duplicate removal,"
                     " meaning ***duplicate materials from lower priority"
                     " databases will be removed first.***")
            database_list = sorted(
                st.session_state.filtered_materials_summary["database"].unique().tolist())
            st.session_state.database_priority_list = sort_items(
                database_list, direction="vertical", key="database_sorter")
        with tolerance_col:
            st.subheader("Set the tolerances for the duplicate removal")
            tolerance_text = "".join(["The tolerances used by [PyMatGen StructureMatcher]"  # noqa: FLY002
                                    "(https://pymatgen.org/pymatgen.analysis.html#pymatgen.analysis.structure_matcher.StructureMatcher)"
                                    " for duplicate removal. If unsure, use the default values."])
            st.write(tolerance_text)
            tolerances = {}
            tolerances["ltol"] = st.slider(
                "Fractional length tolerance",
                min_value=0.0,
                max_value=0.5,
                value=0.2,
                step=0.05,
                key="ltol",
                help="Fractional tolerance in lattice vector lengths. "
                "It determines how much the lattice vectors of two "
                "structures can differ and still be considered 'the same.')")
            tolerances["stol"] = st.slider(
                "Site tolerance",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.05,
                key="stol",
                help="Maximum allowed site displacement "
                "(normalized to average free length per atom) "
                "for atoms to be considered equivalent.")
            tolerances["angle_tol"] = st.slider(
                "Angle tolerance",
                min_value=0,
                max_value=45,
                value=5,
                step=1,
                key="angle_tol",
                help="Maximum allowed difference between lattice angles "
                "for two structures to be considered similar.")

        duplicate_button = st.button(
            "Remove Duplicates", key="duplicate_button", type="primary", width="stretch")

        if duplicate_button:
            # Start time
            start_time = time.time()
            with st.spinner("Removing duplicates... please wait.", show_time=True):
                deduplicator = DuplicateRemover(st.session_state.filtered_materials,
                                                st.session_state.database_priority_list,
                                                tolerances)
                mat, graph = deduplicator.deduplicate()
                st.session_state.unique_materials = mat
                st.session_state.duplicate_graphs = graph

                # Summarize the unique materials
                st.session_state.unique_materials_summary = summarize_materials_dict(
                    st.session_state.unique_materials)

                # Create a zip file of the duplicate graphs
                st.session_state.duplicate_graphs_zip = None
                st.session_state.duplicate_graphs_zip = download_duplicate_figures(
                    st.session_state.duplicate_graphs)
            # End time
            end_time = time.time()
            st.success(f"Duplicate removal completed in **{end_time - start_time:.2f} seconds**",
                       icon="✅")

@st.fragment
def show_duplicate_graph() -> None:
    """Create and display the duplicate graphs."""
    truth_chemsys = st.selectbox(
        "Select a chemical system:",
        list(st.session_state.duplicate_graphs.keys()),
        key="unique_materials_select"
    )
    fig = st.session_state.duplicate_graphs[truth_chemsys]
    st.plotly_chart(fig, config={"width": "content"})

@st.fragment
def show_unique_materials() -> None:
    """Create and display the dataframe for the unique materials."""
    with st.expander("Show all unique materials", expanded=False):
        n_unique = len(st.session_state.unique_materials_summary)
        n_total = len(st.session_state.filtered_materials_summary)
        st.caption(f"Showing **{n_unique}** of **{n_total}** materials")
        display_df = st.session_state.unique_materials_summary.copy()
        display_df["elements_ratios"] = display_df["elements_ratios"].apply(
            lambda x: [round(a, 2) for a in x] if x is not None else None
        )
        selection = st.dataframe(
            display_df,
            on_select="rerun",
            selection_mode="single-row",
            width="stretch"
        )["selection"]
    if selection and "rows" in selection and selection["rows"]:
        show_material(selection, display_df, st.session_state.unique_materials)

# Visualize Unique Materials
if st.session_state.unique_materials != {}:
    uniques_visualize_container = st.container(
        border=True, key="uniques_visualize_container")
    with uniques_visualize_container:
        st.header("Visualize")

        with st.expander("Show duplicate graphs"):
            show_duplicate_graph()
            show_download_button(st.session_state.duplicate_graphs_zip, "duplicate_graphs.zip")

        show_unique_materials()

        # Page Navigation and Download
        dl_col, _, stab_col = st.columns(3, vertical_alignment="top", gap="medium")
        with dl_col:
            render_download(st.session_state.unique_materials, label="Unique Materials")
        with stab_col:
            if st.button(
                "Stability Analysis",
                type="secondary",
                icon="📈",
                width="stretch",
                help="⚠️ Removing duplicate materials first is highly encouraged!"
            ):
                st.switch_page(pages[1])
