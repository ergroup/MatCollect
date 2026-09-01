"""Streamlit page responsible for retrieving and filtering materials from OPTIMADE Databases."""

import re
import time
from pathlib import Path

import streamlit as st

from matcollect.components.download import render_download
from matcollect.components.optimade_providers import load_providers
from matcollect.components.session_state import initialize_session_state, reset_result_states
from matcollect.components.sidebar import render_sidebar
from matcollect.components.value_sliders import filter_numeric_with_nan, make_range_slider
from matcollect.core.database_search.optimade_extractor import OptimadeExtractor
from matcollect.core.utils.misc import update_filtered_materials
from matcollect.core.utils.modal_ase_viewer import show_material
from matcollect.core.utils.summarizer import summarize_materials_dict

# Base directory of the current file
BASE_DIR = Path(__file__).resolve().parent

pages = [
    BASE_DIR / "duplicate_removal.py",
    BASE_DIR / "stability_analysis.py"
]

st.set_page_config(layout="wide", page_icon="assets/images/matcollect.ico")

# Logo
st.logo("assets/images/matcollect_logo_with_text.png", icon_image="assets/images/matcollect.ico")

st.title("Database Search")

# Initialize the session state
initialize_session_state()

# Selected providers
if "selected_providers" not in st.session_state:
    st.session_state.selected_providers = []

# Sidebar
render_sidebar()

# Data Provider Container
data_provider_container = st.container(border=True, key="data_provider_container")
with data_provider_container:
    # Fetch the available providers
    providers = load_providers()
    provider_names = list(providers.keys())

    st.header("Select Data Providers")

    # Remove any providers from state that no longer exist in the current provider list
    st.session_state.selected_providers = [
        p for p in st.session_state.selected_providers if p in provider_names
    ]

    # Buttons (must come before multiselect)
    select_col1, select_col2, select_col3 = st.columns([1, 1, 6], vertical_alignment="bottom")
    with select_col1:
        if st.button("✅ Select All"):
            st.session_state.selected_providers = provider_names
    with select_col2:
        if st.button("🚫 Clear All"):
            st.session_state.selected_providers = []
    with select_col3:
        # Multiselect widget is bound directly to session state
        selected_names = st.multiselect(
            label="Select Materials",
            label_visibility="hidden",
            placeholder="Select one or more providers",
            options=provider_names,
            key="selected_providers",
        )
    st.divider()

    # Display selected providers
    if not selected_names:
        st.info("Select one or more providers above to view details.")
    else:
        rows = []
        for name in selected_names:
            info = providers[name]
            homepage = info.get("homepage", "")
            rows.append({
                "Name": name,
                "ID": info.get("id", "N/A"),
                "Description": info.get("description", "N/A"),
                "Homepage": homepage if homepage and homepage != "NULL" else "",
            })
        st.dataframe(
            rows,
            width="stretch",
            hide_index=True,
            column_config={
                "Homepage": st.column_config.LinkColumn("Homepage"),
            }
        )

    if "nmd" in [providers[name]["id"] for name in st.session_state.selected_providers]:
        st.warning(
            "**NOMAD** database is user-submitted and may vary in quality, completeness, and reproducibility.",  # noqa: E501
            icon="⚠️"
            )
    if "jarvis" in [providers[name]["id"] for name in st.session_state.selected_providers]:
        st.warning(
            "**JARVIS** is a *very large* database and requires material per provider limit to be set.",  # noqa: E501
            icon="⚠️"
            )

# Material Search Container
chem_search_container = st.container(border=True, key="chem_search_container")
with chem_search_container:
    st.header("Search for Materials")

    # Detect multi-chemsys mode
    raw_input = st.session_state.get("chemsys_raw_input", "")
    multi_chemsys_mode = "," in raw_input

    chemsys_col, max_provider_col, toggle_col, nelem_col = st.columns(
        spec=[1, 1, 1, 1],
        vertical_alignment="bottom",
        gap="medium")
    # Chemsys Input
    with chemsys_col:
        chemsys_input = st.text_input(
            "Enter the chemical system(s)",
            placeholder="e.g. Fe-O or Ir-Ru-O, Li-Fe-P-O, ...",
            disabled=st.session_state.selected_providers == [],
            key="chemsys_raw_input",
        )

    # Max materials per database
    with max_provider_col:
        max_per_provider_input = st.text_input(
            "Max materials per database",
            placeholder="Leave empty for no limit",
            disabled=st.session_state.selected_providers == [],
        )

    # Get the length of chemsys input (single-system only)
    if chemsys_input and not multi_chemsys_mode:
        elements_list = chemsys_input.split("-")
        while "" in elements_list:
            elements_list.remove("")
        num_elements_entered = len(elements_list)
    else:
        num_elements_entered = 0

    # Chemsys logic toggle
    with toggle_col:
        only_elements_input = st.toggle(
            "Exact system only",
            value=True,
            disabled=multi_chemsys_mode or st.session_state.selected_providers == [])
        if multi_chemsys_mode:
            only_elements_input = True

    # nelements input
    with nelem_col:
        max_value = 6
        if multi_chemsys_mode:
            st.info("Not available in multi-system mode.")
            nelements_input = None
        elif num_elements_entered == max_value:
            st.info("Number of elements are identical")
            nelements_input = (num_elements_entered, max_value)
        elif num_elements_entered > max_value:
            st.error("Number of elements is too large")
            nelements_input = num_elements_entered
        else:
            nelements_input = st.slider(
                "Select number of elements in the system:",
                min_value=num_elements_entered,
                max_value=max_value,
                value=(num_elements_entered, max_value),
                disabled=only_elements_input or st.session_state.selected_providers == [],
            )

    if not only_elements_input and not multi_chemsys_mode:
        st.warning(
            "**Broad search enabled:** Results will include *all* materials containing any of "
            "these elements, not just this exact system. This can be slow and resource-intensive. "
            "Enable 'Exact system only' for faster, targeted results.",
            icon="⚠️")

    if not max_per_provider_input:
        st.warning(
            "**Limit not set:** Simple systems (e.g. Fe-O) can return thousands of materials. "
            "Setting a per-provider limit is strongly recommended to avoid long load times.",
            icon="⚠️")

    submitted = st.button(
        "Search Materials",
        width="stretch",
        disabled=st.session_state.selected_providers == [] or not chemsys_input,
        type="primary")

    # Button
    if submitted and chemsys_input and chemsys_input.strip():
        # Reset previous results
        reset_result_states()
        max_per_provider = int(max_per_provider_input) if max_per_provider_input else None
        included_provider_ids = [providers[name]["id"]
                                 for name in st.session_state.selected_providers]

        # Show spinner while loading
        with st.spinner("Connecting to Optimade API... please wait.", show_time=True):
            extractor = OptimadeExtractor(include_providers=included_provider_ids,
                                          use_async=True,
                                          max_results_per_provider=max_per_provider)
        st.success("Optimade API loaded successfully!", icon="✅")

        start_time = time.time()

        if multi_chemsys_mode:
            # Parse comma-separated systems
            chemsys_list = [
                s.strip().split("-")
                for s in chemsys_input.split(",")
                if s.strip()
            ]
            with st.spinner(
                f"Retrieving {len(chemsys_list)} systems in parallel... please wait.",
                show_time=True
            ):
                raw = extractor.extract_many(
                    chemsys_list=chemsys_list,
                    only_elements=True,
                )
                errors = extractor.parse_errors()
                st.session_state.extracted_materials = raw
                st.session_state.extracted_materials_summary = summarize_materials_dict(
                    materials_dict=st.session_state.extracted_materials)
        else:
            # Single-system path (unchanged)
            elements_list = chemsys_input.split("-")
            while "" in elements_list:
                elements_list.remove("")
            with st.spinner("Retrieving materials... please wait...", show_time=True):
                extractor.generate_elements_filter(
                    elements=elements_list,
                    only_elements=only_elements_input,
                    min_elements=nelements_input[0] if nelements_input else None,
                    max_elements=nelements_input[1] if nelements_input else None)
                extractor.extract(flush=True)
                errors = extractor.parse_errors()
                st.session_state.extracted_materials = extractor.dump()
                st.session_state.extracted_materials_summary = summarize_materials_dict(
                    materials_dict=st.session_state.extracted_materials)

        end_time = time.time()

        # Display the errors in query
        if errors != []:
            for e in errors:
                st.error(f"**{e['provider']}** -- `{e['status']}`: {e['friendly']}", icon="⚠️")

        # Display the success message
        if st.session_state.extracted_materials == {}:
            st.error("No materials found.", icon="⚠️")
        else:
            st.success(
                f"**{st.session_state.extracted_materials_summary.shape[0]}** "
                f"materials retrieved in **{end_time - start_time:.2f} seconds**",
                icon="✅")

# Element Filter Container
if st.session_state.extracted_materials != {}:
    filter_container = st.container(border=True, key="filter_container")
    with filter_container:
        st.header("Filter Materials")
        materials = st.session_state.extracted_materials
        df = st.session_state.extracted_materials_summary

        # FILTERS
        elements_options = []
        database_options = []
        for chemsys in materials:
            for database in materials[chemsys]:
                database_options.append(database)
                for material_id in materials[chemsys][database]:
                    material = materials[chemsys][database][material_id]["normalized_attributes"]
                    elements_options.extend(material["composition"].keys())
        elements_options = sorted(set(elements_options))
        database_options = sorted(set(database_options))

        # First row
        comp_col, database_col = st.columns(2, vertical_alignment="center", gap="medium")
        with comp_col:
            selected_elements = st.multiselect(
                "Contains elements (composition contains any of these):",
                options=elements_options,
                help="Filter materials by their elemental composition"
            )
        with database_col:
            selected_databases = st.multiselect(
                "From these databases:",
                options=database_options,
                help="Filter materials by their database"
            )

        # Second row
        energy_col, bandgap_col = st.columns(2, vertical_alignment="center", gap="medium")
        with energy_col:
            selected_energy, include_nan_energy = make_range_slider(
                df=df,
                column="formation_energy_per_atom",
                step=0.01)
        with bandgap_col:
            selected_bandgap, include_nan_bandgap = make_range_slider(
                df=df,
                column="band_gap",
                step=0.01)

        # Third row
        sites_col, size_col = st.columns(2, vertical_alignment="center", gap="medium")
        with sites_col:
            selected_nsites, include_nan_nsites = make_range_slider(df, "nsites")
        with size_col:
            selected_nelements, include_nan_nelements = make_range_slider(df, "nelements")

        # APPLY FILTERS
        fdf = df.copy()
        fdf["chemsys"] = fdf["chemsys"].fillna("")
        fdf["material_id"] = fdf["material_id"].astype(str)

        if selected_elements:
            fdf = fdf[fdf["chemsys"].apply(
                lambda cs: any(e in re.sub(r'\d+', '', cs) for e in selected_elements)
            )]
        if selected_databases:
            fdf = fdf[fdf["database"].isin(selected_databases)]

        fdf = filter_numeric_with_nan(fdf,
                                      "formation_energy_per_atom",
                                      selected_energy,
                                      include_nan_energy)
        fdf = filter_numeric_with_nan(fdf, "band_gap", selected_bandgap, include_nan_bandgap)
        fdf = filter_numeric_with_nan(fdf, "nsites", selected_nsites, include_nan_nsites)
        fdf = filter_numeric_with_nan(fdf, "nelements", selected_nelements, include_nan_nelements)

        st.session_state.filtered_materials_summary = fdf

        # Display Results
        n_filtered = len(st.session_state.filtered_materials_summary)
        n_total = len(df)
        st.caption(f"Showing **{n_filtered}** of **{n_total}** materials")

        display_df = st.session_state.filtered_materials_summary.copy()
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
            show_material(selection, display_df, st.session_state.filtered_materials)

        st.session_state.filtered_materials = update_filtered_materials(
            st.session_state.filtered_materials_summary,
            st.session_state.extracted_materials
        )

        st.divider()

        dl_col, dup_col, stab_col = st.columns(3, vertical_alignment="top", gap="medium")
        with dl_col:
            render_download(st.session_state.filtered_materials, label="Extracted Materials")
        with dup_col:
            if st.button("Duplicate Removal", type="primary", icon="📄", width="stretch"):
                st.switch_page(pages[0])
        with stab_col:
            if st.button(
                "Stability Analysis",
                type="secondary",
                icon="📈",
                width="stretch",
                help="⚠️ Removing duplicate materials first is highly encouraged!"
            ):
                st.switch_page(pages[1])
