"""Modal viewer for ASE Atoms. Used in the material details dialog."""

import io

import numpy as np
import pandas as pd
import py3Dmol
import streamlit as st
from ase.io import write
from pymatgen.core.periodic_table import Element
from pymatgen.io.ase import AseAtomsAdaptor, Lattice

from matcollect.core.utils.pymatgen_helper import convert_to_structure


def draw_unit_cell(viewer: py3Dmol.view,
                   lattice: Lattice,
                   color: str = "black",
                   radius: float = 0.015):
    """
    Draw the unit cell of a lattice in a 3Dmol view.

    Parameters
    ----------
    viewer : py3Dmol.view
        The 3Dmol view to draw the unit cell in.
    lattice : Lattice
        The lattice whose unit cell is to be drawn.
    color : str, optional
        The color of the unit cell. Defaults to "black".
    radius : float, optional
        The radius of the cylinders representing the unit cell edges. Defaults to 0.015.

    Notes
    -----
    The unit cell is represented by cylinders connecting the 8 corners of the unit cell.

    """
    # lattice.matrix gives 3x3 array: rows = a,b,c vectors
    a_vec, b_vec, c_vec = lattice.matrix
    origin = np.array([0, 0, 0])

    # Compute the 8 corners
    corners = np.array([
        origin,
        a_vec,
        b_vec,
        c_vec,
        a_vec + b_vec,
        a_vec + c_vec,
        b_vec + c_vec,
        a_vec + b_vec + c_vec
    ])

    # Define edges as pairs of corner indices
    edges = [
        (0, 1), (0, 2), (0, 3),
        (1, 4), (1, 5),
        (2, 4), (2, 6),
        (3, 5), (3, 6),
        (4, 7), (5, 7), (6, 7)
    ]

    # Draw edges
    for start, end in edges:
        viewer.addCylinder({
            "start": {"x": float(corners[start][0]),
                      "y": float(corners[start][1]),
                      "z": float(corners[start][2])},
            "end":   {"x": float(corners[end][0]),
                      "y": float(corners[end][1]),
                      "z": float(corners[end][2])},
            "radius": radius,
            "color": color
        })


@st.dialog("🔬 Material Viewer", width="large")
def show_material(selection: dict | None, df: pd.DataFrame, materials_dict: dict):
    """
    Render a 3D molecular viewer for a material dict.

    Parameters
    ----------
    selection : dict | None
        Selection returned by Streamlit's `st.dataframe` with `on_select` enabled.
    df : pd.DataFrame
        DataFrame with material data.
    materials_dict : dict
        Dictionary containing material data.

    Notes
    -----
    This function will display a 3D molecular viewer for a material dict.
    The viewer will be embedded in a Streamlit dialog box.
    The function will only render the viewer if the selection is not None
    and the selection contains at least one row.
    """
    if selection and "rows" in selection and len(selection["rows"]) > 0:
        idx = selection["rows"][0]
        selected_row = df.iloc[idx]
        chemsys = selected_row["chemsys"]
        database = selected_row["database"]
        material_id = selected_row["material_id"]

        # Load material as ASE Atoms
        material = materials_dict[chemsys][database][material_id]
        struct = convert_to_structure(material["normalized_attributes"])
        ase_atoms = AseAtomsAdaptor.get_atoms(struct)

        # Export ASE Atoms to XYZ format (string)
        xyz_buf = io.StringIO()
        write(xyz_buf, ase_atoms, format="xyz")
        xyz_str = xyz_buf.getvalue()

        # py3Dmol viewer
        viewer = py3Dmol.view(width=720, height=480)
        viewer.addModel(xyz_str, "xyz")

        # Set style for different elements
        elements = {site.specie.symbol for site in struct}
        for element in elements:
            radius = Element(element).van_der_waals_radius or 1.5
            viewer.addStyle({"elem": element},
                            {"sphere": {"radius": float(radius), "colorscheme": "CPK"}})

        # Add unit cell
        draw_unit_cell(viewer, struct.lattice, color="black", radius=0.015)

        # JS callback as a string — THIS should match 3Dmol's callback signature:
        js_callback = """
function(atom, _viewer, event, container) {
    // toggle label on click
    if (!atom) return;
    if (!atom._myLabel) {
        atom._myLabel = _viewer.addLabel(
            atom.elem + ' (' + (atom.serial || '') + ')\\n' +
            'x=' + atom.x.toFixed(2) + ', y=' + atom.y.toFixed(2) + ', z=' + atom.z.toFixed(2),
            { position: atom, backgroundColor: 'white', fontColor: 'black', fontSize: 12, inFront: true }
        );
    } else {
        _viewer.removeLabel(atom._myLabel);
        delete atom._myLabel;
    }
}
"""  # noqa: E501
        # Attach callback using the 3Dmol call; pass an empty selection {} to select all atoms
        viewer.setClickable({}, True, js_callback)  # noqa: FBT003

        # Display
        col1, col2 = st.columns(
            [1, 2], vertical_alignment="center", gap="medium")
        with col1:
            st.subheader("Material Data")
            record = selected_row.to_dict()
            # Key-value table
            def _pretty(v: None | list | tuple | dict) -> str:
                if v is None:
                    return ""
                if isinstance(v, (list, tuple)):
                    return ", ".join(map(str, v))
                if isinstance(v, dict):
                    return ", ".join(f"{k}: {v}" for k, v in v.items())
                return str(v)

            st.table(
                [{"Field": k, "Value": _pretty(v)} for k, v in record.items()]
            )
        with col2:
            viewer.zoomTo()
            html_str = str(viewer._make_html())  # noqa: SLF001
            st.components.v1.html(html_str, width=720, height=480)
    else:
        pass

# Homepage example viewer
def show_material_preview():
    """Render a 3D molecular viewer for a material dict."""
    example_material = {
        "nsites": 6,
        "lattice_vectors": [
                [
                3.18985541,
                0.0,
                0.0
                ],
                [
                0.0,
                4.54856304,
                0.0
                ],
                [
                0.0,
                0.0,
                4.54056594
                ]
            ],
        "cartesian_site_positions": [
                [
                0.0,
                0.0,
                0.0
                ],
                [
                1.594927705,
                2.27428152,
                2.27028297
                ],
                [
                0.0,
                1.4047452776771905,
                1.3984138506915431
                ],
                [
                0.0,
                3.1438177623228096,
                3.1421520893084565
                ],
                [
                1.594927705,
                0.8695362423228096,
                3.668696820691543
                ],
                [
                1.594927705,
                3.679026797677191,
                0.8718691193084568
                ]
            ],
        "species_at_sites": [
                "Ir",
                "Ir",
                "O",
                "O",
                "O",
                "O"
            ],
            }
    struct = convert_to_structure(example_material)
    ase_atoms = AseAtomsAdaptor.get_atoms(struct)

    xyz_buf = io.StringIO()
    write(xyz_buf, ase_atoms, format="xyz")
    xyz_str = xyz_buf.getvalue()

    viewer = py3Dmol.view(width="100%", height=470)
    viewer.addModel(xyz_str, "xyz")

    elements = {site.specie.symbol for site in struct}
    for element in elements:
        radius = Element(element).van_der_waals_radius or 1.5
        viewer.addStyle(
            {"elem": element},
            {"sphere": {"radius": float(radius), "colorscheme": "CPK"}}
        )

    draw_unit_cell(viewer, struct.lattice, color="black", radius=0.015)
    viewer.zoomTo()

    raw_html = viewer._make_html()  # noqa: SLF001

    # Wrap in a responsive container that fills its parent column
    responsive_html = f"""
    <div style="width: 100%; height: 480px; overflow: hidden;">
        <style>
            #glviewer_container {{ width: 100% !important; }}
            canvas {{ width: 100% !important; }}
        </style>
        {raw_html}
    </div>
    """

    st.components.v1.html(responsive_html, width=None, height=470)
