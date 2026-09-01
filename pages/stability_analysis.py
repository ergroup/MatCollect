"""Stability Analysis Page."""

import time
from copy import deepcopy

import pandas as pd
import plotly
import streamlit as st

from matcollect.components.download import render_download, show_download_button
from matcollect.components.session_state import initialize_session_state
from matcollect.components.sidebar import render_sidebar
from matcollect.core.stability_analysis.e_above_hull_analyzer import (
    HullAnalyzer,
    TerminalEnergyFetchError,
)
from matcollect.core.stability_analysis.energy_calibrator import EnergyCalibrator
from matcollect.core.stability_analysis.pourbaix_analyzer import PourbaixAnalyzer
from matcollect.core.utils.misc import (
    download_hull_figures,
    download_pourbaix_figures,
    update_filtered_materials,
)
from matcollect.core.utils.modal_ase_viewer import show_material
from matcollect.core.utils.summarizer import summarize_materials_dict

st.set_page_config(layout="wide", page_icon="assets/images/matcollect.ico")

# Logo
st.logo("assets/images/matcollect_logo_with_text.png", icon_image="assets/images/matcollect.ico")

st.title("Stability Analysis")

# Initialize the session state
initialize_session_state()

# Sidebar
render_sidebar()

DISPLAY_PROPERTIES_LIST = ["material_id", "database", "chemsys", "reduced_formula", "nsites",
                           "formation_energy_per_atom",
                           "total_energy", "band_gap",
                           "space_group_symbol", "nelements",
                           "elements_ratios", "nperiodic_dimensions"]

def _mark_terminal_db_overridden():
    """User manually touched the hull terminal-db dropdown — stop auto-following calibration."""
    st.session_state.terminal_energy_db_user_override = True

def _sync_terminal_db_with_calibration():
    """Calibration reference db changed — always re-follow it in the hull dropdown.
    Changing the calibration dropdown is an explicit signal to resume auto-following,
    so it clears any prior manual override on the hull dropdown.
    """
    new_ref = st.session_state.get("calibration_ref_db")
    if new_ref:
        st.session_state.terminal_energy_db = new_ref
        st.session_state.terminal_energy_db_user_override = False


stability_selection_container = st.container(border=True, key="stability_selection_container")
with stability_selection_container:
    st.header("Stability Analysis Selection")
    # Select materials to analyze
    no_filtered_materials = False
    no_unique_materials = False
    if st.session_state.filtered_materials == {}:
        no_filtered_materials = True
    if st.session_state.unique_materials == {}:
        no_unique_materials = True

    if no_unique_materials and not no_filtered_materials:
        st.session_state.stability_selected_materials = st.session_state.filtered_materials
        st.session_state.stability_selected_materials_summary = st.session_state.filtered_materials_summary  # noqa: E501
        st.write("All **post-processed materials** will be analyzed")
        st.write()
    elif not no_unique_materials and no_filtered_materials:
        st.session_state.stability_selected_materials = st.session_state.unique_materials
        st.session_state.stability_selected_materials_summary = st.session_state.unique_materials_summary  # noqa: E501
        st.write("Only **unique materials** will be analyzed")
    elif no_filtered_materials and no_unique_materials:
        st.error("Please search for materials first.", icon="⚠️")
    else:
        toggle_col, text_col = st.columns(
            2, vertical_alignment="center", gap="medium")
        with toggle_col:
            materials_toggle = st.toggle("Unique materials only", value=True)
        with text_col:
            if materials_toggle:
                st.session_state.stability_selected_materials = st.session_state.unique_materials
                st.session_state.stability_selected_materials_summary = st.session_state.unique_materials_summary  # noqa: E501
                st.write("*Only **unique materials** will be analyzed")
            else:
                st.session_state.stability_selected_materials = st.session_state.filtered_materials
                st.session_state.stability_selected_materials_summary = st.session_state.filtered_materials_summary  # noqa: E501
                st.write("*All **post-processed materials** will be analyzed")

    # Buttons
    if st.session_state.stability_selected_materials != {}:
        # Cross-database calibration toggle
        calibration_col, calibration_text_col = st.columns(2,
                                                           vertical_alignment="center",
                                                           gap="medium")
        with calibration_col:
            calibration_toggle = st.toggle("Cross-Database Energy Calibration", True)  # noqa: FBT003
        with calibration_text_col:
            if calibration_toggle:
                st.write("*Formation energies **will** be harmonized across databases")
            else:
                st.write("*Formation energies **will not** be harmonized across databases")

        pourbaix_col, pourbaix_text_col = st.columns(2, vertical_alignment="center", gap="medium")
        with pourbaix_col:
            pourbaix_toggle = st.toggle("Pourbaix Analysis", True)  # noqa: FBT003
        with pourbaix_text_col:
            if pourbaix_toggle:
                st.write("*Pourbaix stability **will** be analyzed")
            else:
                st.write("*Pourbaix stability **will not** be analyzed")

        e_above_hull_col, e_above_text_col = st.columns(2,
                                                        vertical_alignment="center",
                                                        gap="medium")
        with e_above_hull_col:
            e_above_hull_toggle = st.toggle("Energy Above Hull Analysis", True)  # noqa: FBT003
        with e_above_text_col:
            if e_above_hull_toggle:
                st.write("*Energy above hull stability **will** be analyzed")
            else:
                st.write("*Energy above hull stability **will not** be analyzed")


# Cross-Database Calibration
if st.session_state.stability_selected_materials != {} and calibration_toggle:
    calibration_container = st.container(border=True, key="calibration_container")
    with calibration_container:
        st.header("Cross-Database Energy Calibration")
        st.write(
            "Formation energies from different databases use different DFT settings and "
            "elemental references. Calibration fits per-element offsets from structurally "
            "matched compounds (found in the **pre-deduplication** data) to place all "
            "materials on the same energy scale."
        )
        # Get available databases from PRE-DEDUP data (filtered_materials)
        # This is critical: after dedup, some databases may be entirely removed
        # We need all databases for calibration pairs
        calibration_source = st.session_state.filtered_materials
        available_dbs_calibration = set()
        for chemsys_dict in calibration_source.values():
            available_dbs_calibration.update(chemsys_dict.keys())
        available_dbs_calibration = sorted(available_dbs_calibration)

        # Databases in the analysis set (post-dedup)
        available_dbs = set()
        for chemsys_dict in st.session_state.stability_selected_materials.values():
            available_dbs.update(chemsys_dict.keys())
        available_dbs = sorted(available_dbs)

        if len(available_dbs_calibration) < 2:  # noqa: PLR2004
            st.info("Only one database present in the data — calibration not needed.")
            calibration_toggle = False
        elif len(available_dbs) < 2:  # noqa: PLR2004
            st.info(
                "Only one database remains after deduplication. Calibration will use "
                "pre-deduplication data to find matched compounds and fit offsets."
            )

        if calibration_toggle and len(available_dbs_calibration) >= 2:  # noqa: PLR2004
            # Default to MP if available
            default_idx = 0
            for i, db in enumerate(available_dbs_calibration):
                if "materialsproject" in db.lower() or "mp" in db.lower():
                    default_idx = i
                    break
            reference_db = st.selectbox(
                "Reference database (all others will be corrected to this scale):",
                options=available_dbs_calibration,
                index=default_idx,
                key="calibration_ref_db",
                on_change=_sync_terminal_db_with_calibration,
            )

# Pourbaix Analysis
if st.session_state.stability_selected_materials != {} and pourbaix_toggle:
    pourbaix_container = st.container(border=True, key="pourbaix_container")
    with pourbaix_container:
        st.header("Pourbaix Analysis")
        st.markdown("""
        **How it works:** Maps thermodynamically stable phases across pH and potential using `pymatgen`.
        Requires a valid **Materials Project API key** to fetch aqueous ion references.

        ⚠️ **Reliability Warning:**
        *   Results depend on the accuracy of formation energies in the source databases.
        *   Materials lacking valid `formation_energy_per_atom` will be skipped.
        *   Cross-database energy scale differences (~0.1 eV/atom) may affect precision,
            consider performing the energy calibration.
        *   Treat results as a screening tool; validate promising candidates with high-fidelity methods.
        """)  # noqa: E501
        api_col, ph_col, U_col = st.columns([2, 1, 1],
                                            vertical_alignment="bottom",
                                            gap="medium")
        with api_col:
            api_input = st.text_input("The Material Project API",
                                    placeholder="Enter API key here",
                                    type="password")
        with ph_col:
            ph_input = st.number_input("pH", value=7.0)
        with U_col:
            U_input = st.number_input("Overpotential", value=0.0)

# Energy Above Hull Analysis
if st.session_state.stability_selected_materials != {} and e_above_hull_toggle:
    e_above_hull_container = st.container(border=True, key="e_above_hull_container")
    with e_above_hull_container:
        st.header("Energy Above Hull Analysis")
        st.markdown("""
        **How it works:** Calculates the energy difference (eV/atom) between a material and the convex hull of stable phases.
        *   **0.0 eV/atom**: Thermodynamically stable.
        *   **> 0.0 eV/atom**: Unstable (likely to decompose).

        **Terminal (elemental) reference energies:** To build the convex hull, each element's
        reference energy (e.g. energy of pure Ir, pure O) is needed as an "anchor point."
        These are fetched fresh via OPTIMADE from the database you select below. Materials
        Project is always available as an option, even if your current dataset doesn't
        happen to contain any MP materials.
        *   If you calibrated cross-database energies above, this defaults to that same
            reference database, keeping the hull on a consistent scale.
        *   Otherwise it defaults to **Materials Project (mp)**, the most widely used
            reference scale and the one most other databases are typically calibrated against.
        *   Mixing uncalibrated formation energies with a mismatched reference database can
            introduce a systematic offset, making energy above hull values look more or less
            stable than they really are.

        ⚠️ **Reliability & Scope Warning:**
        *   All chemical systems are analyzed. However, only systems with **1, 2, or 3 distinct elements** can be visualized on a convex hull plot.
        *   Materials without valid `formation_energy_per_atom` are automatically excluded.
        *   Formation energies from different databases may not be perfectly aligned.
        *   Treat results as a screening tool; validate promising candidates with high-fidelity methods.
        *   Consider using a wider threshold (e.g., 0.2-0.3 eV/atom)** during initial screening.
            This helps capture potentially synthesizable metastable materials while filtering out clearly unstable candidates.
        """)  # noqa: E501

        # Databases available for terminal (elemental) reference energies.
        # Sourced from the post-dedup analysis set, same as the calibration widget above.
        available_dbs_terminal = set()
        for chemsys_dict in st.session_state.stability_selected_materials.values():
            available_dbs_terminal.update(chemsys_dict.keys())

        # Always offer MP — fetched fresh via OPTIMADE regardless of local dataset contents.
        # Always offer the calibration reference db too, even if dedup removed it locally,
        # so syncing to it never raises a "value not in options" error.
        forced_inclusions = {"https://optimade.materialsproject.org/"}
        calibration_ref_db = st.session_state.get("calibration_ref_db")
        if calibration_ref_db:
            forced_inclusions.add(calibration_ref_db)

        forced_inclusions = set(forced_inclusions)
        available_dbs_terminal = sorted(available_dbs_terminal | forced_inclusions)

        default_terminal_idx = None
        if calibration_ref_db is not None:
            for i, db in enumerate(available_dbs_terminal):
                if db == calibration_ref_db:
                    default_terminal_idx = i
                    break
        if default_terminal_idx is None:
            for i, db in enumerate(available_dbs_terminal):
                if "materialsproject" in db.lower() or "mp" in db.lower():
                    default_terminal_idx = i
                    break
        if default_terminal_idx is None:
            default_terminal_idx = 0

        terminal_energy_db = st.selectbox(
            "Database for terminal (elemental) reference energies:",
            options=available_dbs_terminal,
            index=default_terminal_idx,
            key="terminal_energy_db",
            on_change=_mark_terminal_db_overridden,
            help=(
                "Elemental reference energies used to build the convex hull are fetched "
                "from this database via OPTIMADE. Defaults to your calibration reference "
                "database if one was selected, otherwise Materials Project (mp)."
            )
        )
        help_text = """Set the energy above hull threshold for visualizing unstable materials
        in the convex hull plot. Materials with energy above hull below this threshold will be
        shown as unstable points on the plot. Adjusting this can help focus on near-stable
        materials, but does not affect filtering.
        """
        e_above_hull_visibility_threshold = st.number_input("Energy Above Hull Visibility Threshold (eV/atom)",  # noqa: E501
                                                            value=0.2,
                                                            help=help_text)

# Analyze Stability
if st.session_state.stability_selected_materials != {}:
    analysis_container = st.container(border=False, key="analysis_container")
    with analysis_container:
        if any([pourbaix_toggle, e_above_hull_toggle, calibration_toggle]):
            if st.button("Analyze Stability",
                         type="primary",
                         icon="📈",
                         use_container_width=True,
                         key="start_button"):
                if pourbaix_toggle and api_input == "":
                    st.error("Please enter a Material Project API key.", icon="⚠️")
                else:
                    # Reset session state
                    st.session_state.e_above_hull_figures = None
                    st.session_state.pourbaix_figures = None
                    st.session_state.calibration_report = None
                    # Reset hull widget state
                    st.session_state.pop("e_above_hull_select", None)

                    # Cross-database calibration (runs before stability analysis)
                    if calibration_toggle and len(available_dbs_calibration) >= 2:  # noqa: PLR2004
                        # Time
                        calibration_start_time = time.time()
                        with st.spinner("Calibrating cross-database energies...", show_time=True):
                            # Fit offsets from pre-dedup data (all databases present)
                            calibration_data = deepcopy(calibration_source.copy())
                            fitting_calibrator = EnergyCalibrator(
                                materials_dict=calibration_data,
                                reference_database=reference_db)
                            fitting_calibrator.calibrate()
                            st.session_state.calibration_report = fitting_calibrator.calibration_report  # noqa: E501

                            # Apply the fitted offsets to the analysis set
                            calibrated_materials = deepcopy(
                                st.session_state.stability_selected_materials)
                            analysis_calibrator = EnergyCalibrator(
                                materials_dict=calibrated_materials,
                                reference_database=reference_db)
                            # Copy the already-fitted offsets
                            analysis_calibrator.element_offsets = fitting_calibrator.element_offsets  # noqa: E501
                            analysis_calibrator.element_offset_stderr = fitting_calibrator.element_offset_stderr  # noqa: E501
                            # Required for per-material error propagation in _apply_corrections
                            analysis_calibrator._covariances = fitting_calibrator._covariances  # noqa: SLF001
                            analysis_calibrator.calibration_report = fitting_calibrator.calibration_report  # noqa: E501
                            # Apply corrections
                            for db in available_dbs:
                                offsets = {
                                    el: fitting_calibrator.element_offsets.get((db, el), 0.0)
                                    for el in {
                                        e for cd in calibrated_materials.values()
                                        for d in cd.values() for m in d.values()
                                        for e in m["normalized_attributes"].get("composition", {})
                                    }
                                    if (db, el) in fitting_calibrator.element_offsets
                                }
                                if offsets:
                                    analysis_calibrator._apply_corrections(db, offsets)  # noqa: SLF001

                            # Stamp reference-database materials (never corrected)
                            for chemsys_dict in calibrated_materials.values():
                                for material in chemsys_dict.get(reference_db, {}).values():
                                    attrs = material["normalized_attributes"]
                                    ef = attrs.get("formation_energy_per_atom")
                                    if ef is None:
                                        continue
                                    attrs["formation_energy_per_atom_uncorrected"] = ef
                                    attrs["calibration_correction"] = 0.0
                                    attrs["calibration_correction_stderr"] = 0.0
                                    attrs["calibration_reference"] = reference_db

                        st.session_state.stability_candidate_materials = calibrated_materials
                        calibration_end_time = time.time()
                        st.success(f"Cross-database calibration completed in **{calibration_end_time - calibration_start_time:.2f} seconds**",  # noqa: E501
                                   icon="✅")
                    else:
                        calibrated_materials = st.session_state.stability_selected_materials

                    if pourbaix_toggle:
                        # Time
                        pourbaix_start_time = time.time()
                        with st.spinner("Analyzing Pourbaix stability...", show_time=True):
                            pourbaix_analyzer = PourbaixAnalyzer(
                                materials_dict=calibrated_materials,
                                mp_api_key=api_input)

                            start_time = time.time()
                            st.session_state.stability_candidate_materials, st.session_state.pourbaix_figures = pourbaix_analyzer.analyze(  # noqa: E501
                                ph=ph_input,
                                u=U_input)
                            print(f"Pourbaix analysis took {time.time() - start_time:.2f} seconds")

                            figure_start_time = time.time()
                            st.session_state.pourbaix_figures_zip = download_pourbaix_figures(st.session_state.pourbaix_figures)  # noqa: E501
                            print(f"Pourbaix figure zipping took {time.time() - figure_start_time:.2f} seconds")  # noqa: E501
                        # End time
                        pourbaix_end_time = time.time()
                        st.success(f"Pourbaix analysis completed in **{pourbaix_end_time - pourbaix_start_time:.2f} seconds**",  # noqa: E501
                                   icon="✅")

                    if e_above_hull_toggle:
                        e_above_hull_start_time = time.time()
                        try:
                            with st.spinner("Analyzing energy above hull...", show_time=True):
                                hull_analyzer = HullAnalyzer(
                                    calibrated_materials,
                                    terminal_energy_provider=st.session_state.terminal_energy_db,
                                )
                                if hull_analyzer.used_fallback_provider:
                                    st.warning(
                                        f"Could not retrieve one or more elemental reference "
                                        f"energies from **{st.session_state.terminal_energy_db}** "
                                        f"(no response, or missing formation energies). "
                                        f"Automatically used **The Materials Project** for "
                                        f"**all** elemental reference energies instead, to keep "
                                        f"the hull on a consistent scale.",
                                        icon="⚠️"
                                    )
                                st.session_state.stability_candidate_materials, st.session_state.e_above_hull_figures = hull_analyzer.analyze(e_above_hull_visibility_threshold)  # noqa: E501
                                st.session_state.e_above_hull_figures_zip = download_hull_figures(st.session_state.e_above_hull_figures)  # noqa: E501
                            e_above_hull_end_time = time.time()
                            st.success(f"Energy above hull analysis completed in **{e_above_hull_end_time - e_above_hull_start_time:.2f} seconds**",  # noqa: E501
                                       icon="✅")
                        except TerminalEnergyFetchError as e:
                            st.error(str(e), icon="⚠️")

                    if st.session_state.stability_candidate_materials != {}:
                        # Insert
                        selected_properties = DISPLAY_PROPERTIES_LIST.copy()
                        if calibration_toggle:
                            selected_properties.insert(6, "formation_energy_per_atom_uncorrected")
                        if pourbaix_toggle:
                            selected_properties.insert(5, "decomposition_energy_per_atom")
                        if e_above_hull_toggle:
                            selected_properties.insert(5, "energy_above_hull")
                        st.session_state.stability_candidate_materials_summary = summarize_materials_dict(  # noqa: E501
                            materials_dict=st.session_state.stability_candidate_materials,
                            attributes=selected_properties)
        else:
            st.error("Please select at least one stability analysis.", icon="⚠️")


# Results
if st.session_state.stability_candidate_materials != {}:
    results_container = st.container(border=True, key="results_container")
    with results_container:
        st.header("Results")
        if st.session_state.calibration_report and calibration_toggle:
            with st.expander("Cross-Database Energy Calibration", expanded=False):
                for db, report in st.session_state.calibration_report.items():
                    if report["status"] != "success":
                        st.warning(
                            f"**{db}** — calibration failed: "
                            f"{report.get('reason', 'unknown')}", icon="⚠️")
                        continue

                    st.markdown(f"**{db}** → {reference_db}")
                    st.caption(
                        f"{report['n_matches']} matched compounds · "
                        f"RMSE {report['rmse_meV']} meV/atom · "
                        f"{report['dof']} dof")

                    st.dataframe(
                        pd.DataFrame([
                            {"Element": el,
                             "Offset": report["offsets_meV"][el],
                             "± 1σ": report["offset_stderr_meV"][el]}
                            for el in report["elements"]
                        ]),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Offset": st.column_config.NumberColumn(
                                "Offset (meV/atom)", format="%+.1f"),
                            "± 1σ": st.column_config.NumberColumn(format="%.1f"),
                        })

                    for msg in report.get("warnings", []):
                        st.warning(msg, icon="⚠️")

        if st.session_state.pourbaix_figures and pourbaix_toggle:
            with st.expander("Pourbaix Analysis", expanded=False):
                chemsys_col, database_col, material_id_col = st.columns(
                    3, vertical_alignment="center", gap="medium")
                with chemsys_col:
                    st.selectbox(
                        "Select chemical system:",
                        list(st.session_state.pourbaix_figures.keys()),
                        key="pourbaix_chemsys")
                with database_col:
                    st.selectbox(
                        "Select database:",
                        list(st.session_state.pourbaix_figures[st.session_state.pourbaix_chemsys].keys()),
                        key="pourbaix_database_select")
                with material_id_col:
                    st.selectbox(
                        "Select material id:",
                        list(st.session_state.pourbaix_figures[st.session_state.pourbaix_chemsys][st.session_state.pourbaix_database_select].keys()),
                        key="pourbaix_material_select")
                pourbaix_fig = st.session_state.pourbaix_figures[st.session_state.pourbaix_chemsys][st.session_state.pourbaix_database_select][st.session_state.pourbaix_material_select]  # noqa: E501
                st.image(pourbaix_fig)
                # Download Button
                show_download_button(st.session_state.pourbaix_figures_zip, "pourbaix_figures.zip")

        if st.session_state.e_above_hull_figures and e_above_hull_toggle:
            with st.expander("Energy Above Hull Analysis", expanded=False):
                e_above_hull_chemsys = st.selectbox("Select a chemical system:", list(
                    st.session_state.e_above_hull_figures.keys()), key="e_above_hull_select")
                e_above_hull_fig = st.session_state.e_above_hull_figures[e_above_hull_chemsys]
                st.plotly_chart(plotly.io.from_json(e_above_hull_fig), use_container_width=True)
                # Download Button
                show_download_button(st.session_state.e_above_hull_figures_zip, "convex_hull_figures.zip")  # noqa: E501


# Stability Filtering
if st.session_state.stability_candidate_materials != {}:
    filter_container = st.container(border=True, key="filter_container")
    with filter_container:
        st.header("Filter Stable Materials")
        materials = st.session_state.stability_candidate_materials
        df = st.session_state.stability_candidate_materials_summary
        # --- FILTERS ---
        filter_col1, filter_col2 = st.columns(
            2, vertical_alignment="center", gap="medium")
        with filter_col1:
            # Decomposition Energy Threshold
            decomposition_input = st.number_input("Decomposition Energy Threshold (eV/atom)",
                                                  value=0.5, disabled=not (pourbaix_toggle and
                                                                       "decomposition_energy_per_atom" in df.columns))  # noqa: E501
        with filter_col2:
            # E_above_hull Threshold
            e_above_hull_input = st.number_input("Energy Above Hull Threshold (eV/atom)",
                                                 value=0.1, disabled=not (e_above_hull_toggle and
                                                                      "energy_above_hull" in df.columns))  # noqa: E501

        # Apply filters
        df["chemsys"] = df["chemsys"].fillna("")
        df["material_id"] = df["material_id"].astype(str)
        st.session_state.stable_materials_summary = df.copy()
        if pourbaix_toggle and "decomposition_energy_per_atom" in df.columns:
            st.session_state.stable_materials_summary = st.session_state.stable_materials_summary[
                df["decomposition_energy_per_atom"] <= decomposition_input]
        if e_above_hull_toggle and "energy_above_hull" in df.columns:
            st.session_state.stable_materials_summary = st.session_state.stable_materials_summary[
                df["energy_above_hull"] <= e_above_hull_input]
        # Display
        display_df = st.session_state.stable_materials_summary.copy()
        display_df["elements_ratios"] = display_df["elements_ratios"].apply(
            lambda x: [round(a, 2) for a in x])

        # Format energy columns to 4 decimal places for scientific accuracy
        energy_columns = ["formation_energy_per_atom", "formation_energy_per_atom_uncorrected",
                          "energy_above_hull", "decomposition_energy_per_atom", "total_energy"]
        column_format = {}
        for col in energy_columns:
            if col in display_df.columns:
                column_format[col] = st.column_config.NumberColumn(format="%.4f")
        st.write(f"**Showing {len(display_df)} stable materials**")
        selection = st.dataframe(display_df,
                                 on_select="rerun",
                                 selection_mode="single-row",
                                 column_config=column_format)["selection"]
        if selection and "rows" in selection and len(selection["rows"]) > 0:
            show_material(selection, display_df,
                          st.session_state.stable_materials)

        # Update materials
        st.session_state.stable_materials = update_filtered_materials(st.session_state.stable_materials_summary,  # noqa: E501
                                                                      st.session_state.stability_candidate_materials)
        # Download Materials
        if st.session_state.stable_materials != {}:
            progress_col1, _, _ = st.columns(
                3, vertical_alignment="center", gap="medium")
            with progress_col1:
                render_download(st.session_state.stable_materials, label="Stable Materials")
