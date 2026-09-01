"""Functions for rendering the download button of the app across pages."""

import streamlit as st

from matcollect.core.utils.misc import download_materials


def render_download(materials: dict,
                    label: str = "Materials"):
    """
    Render a download button for the given materials.

    Args:
        materials (dict): A dictionary of materials to download.
        label (str, optional): The label for the download button. Defaults to "Materials".
    """
    with st.expander("Download Materials", icon="💾"):
        # Select data format to download
        selected_format = st.selectbox(
            "Select format",
            ["JSON", "POSCAR", "ASE Atoms", "CIF"])
        selected_data = materials
        selected_label = label
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
            type="tertiary"
            )

@st.fragment
def show_download_button(data: bytes, filename: str = "materials.zip") -> None:
    """Create and display the download button for the duplicate graphs."""
    st.download_button(
        label="Download Figures",
        data=data,
        file_name=filename,
        mime="application/zip",
        type="tertiary",
        width="stretch",
    )
