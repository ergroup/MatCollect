"""Functions for rendering the sidebar of the app across pages."""

import json

import streamlit as st

from matcollect.components.session_state import reset_session_state
from matcollect.core.utils.misc import download_materials
from matcollect.core.utils.summarizer import summarize_materials_dict


def render_sidebar():  # noqa: C901, PLR0912
    """Render the reusable sidebar and return any relevant data."""
    uploaded_file = st.sidebar.file_uploader(
        "Upload JSON file",
        type=["json"],
        key="material_uploader",
        help="Upload a JSON file previously downloaded from this app.",
    )

    if uploaded_file is not None:
        try:
            uploaded_json = json.load(uploaded_file)
            # Verify it looks like a materials dictionary
            if not isinstance(uploaded_json, dict):
                st.sidebar.error(
                    "❌ Uploaded JSON must be a dictionary of materials.")
            else:
                reset_session_state()
                st.session_state.filtered_materials = uploaded_json
                st.session_state.filtered_materials_summary = summarize_materials_dict(
                    uploaded_json)
                st.session_state.extracted_materials = uploaded_json
                st.session_state.extracted_materials_summary = summarize_materials_dict(
                    uploaded_json)
                st.sidebar.success("✅ Materials loaded successfully!")
        except Exception as e:
            st.sidebar.error(f"Failed to load JSON: {e}")

    with st.sidebar.expander("💾 Download Materials"):
        st.write("Choose which dataset to download:")

        # Determine which datasets exist
        available_datasets = {}
        if st.session_state.get("filtered_materials"):
            available_datasets["Extracted Materials"] = st.session_state.filtered_materials
        if st.session_state.get("unique_materials"):
            available_datasets["Unique Materials"] = st.session_state.unique_materials
        if st.session_state.get("stable_materials"):
            available_datasets["Stable Materials"] = st.session_state.stable_materials

        if not available_datasets:
            st.info("No materials available for download yet.")
        else:
            # Select dataset to download
            selected_label = st.selectbox(
                "Select dataset",
                list(available_datasets.keys()),
                key="download_dataset_select"
            )

            # Select data format to download
            selected_format = st.selectbox(
                "Select format",
                ["JSON", "POSCAR", "ASE Atoms", "CIF"],
                key="download_format_select"
            )
            selected_data = available_datasets[selected_label]
            download_data = download_materials(
                selected_data, dtype=selected_format)

            # Prepare File
            mime_type = ""
            filename = selected_label.lower().replace(" ", "_")
            if selected_format == "JSON":
                mime_type = "application/json"
                filename += ".json"
            elif selected_format == "POSCAR":
                mime_type = "application/zip"
                filename += "_poscar.zip"
            elif selected_format == "ASE Atoms":
                mime_type = "application/octet-stream"
                filename += ".pkl"
            elif selected_format == "CIF":
                mime_type = "application/zip"
                filename += "_cif.zip"

            # Download button
            st.download_button(
                label="Download Materials",
                data=download_data,
                file_name=filename,
                mime=mime_type,
                type="tertiary",
            )
