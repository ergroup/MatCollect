"""Utility functions."""

import io
import json
import pickle
import re
import zipfile
from collections import defaultdict

import pandas as pd
import plotly.io as pio
from matplotlib.figure import Figure
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.io.cif import CifWriter
from pymatgen.io.vasp import Poscar

from matcollect.core.utils.pymatgen_helper import convert_to_structure


# Define globally so pickle can find it
def nested_defaultdict() -> defaultdict:
    """
    Return a defaultdict of defaultdicts, i.e. a nested dictionary
    where each key maps to another defaultdict.
    Useful for creating hierarchical dictionaries with default values.
    """
    return defaultdict(dict)

def format_database_name(database: str) -> str:
    """
    Format a database name by removing the "https://" or "http://" prefix and
    trailing slash.

    Args:
        database (str): The database name to format.

    Returns:
        str: The formatted database name.
    """
    return re.sub(r"https?://", "", database).strip("/")

def update_filtered_materials(df: pd.DataFrame, materials_dict: dict) -> dict:
    """
    Update the filtered materials dictionary with the materials from the given DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        A DataFrame containing the materials to update the filtered materials dictionary with.
    materials_dict : dict
        A dictionary containing the original materials.

    Returns
    -------
    dict
        The updated filtered materials dictionary.
    """
    filtered_materials_dict = {}
    for _, row in df.iterrows():
        db = str(row["database"])
        mat_id = str(row["material_id"])
        chemsys = str(row["chemsys"])

        # Check if this material exists in the original dictionary
        if materials_dict.get(chemsys, {}).get(db, {}).get(mat_id):
            if chemsys not in filtered_materials_dict:
                filtered_materials_dict[chemsys] = {}
            if db not in filtered_materials_dict[chemsys]:
                filtered_materials_dict[chemsys][db] = {}
            filtered_materials_dict[chemsys][db][mat_id] = materials_dict[chemsys][db][mat_id]
    return filtered_materials_dict


def format_chemical_label(label: str) -> str:
    """
    Convert chemical strings to Matplotlib mathtext with proper subscripts/superscripts.
    Examples:
      IrO4[-2] → IrO₄²⁻
      H2RuO2[+2] → H₂RuO₂²⁺
      Ir(RuO4)2(s) → Ir(RuO₄)₂(s).
    """
    # --- handle ionic charges like [-2], [+3] ---
    def _charge_repl(match: re.Match) -> str:
        sign = match.group(1)
        num = match.group(2)
        return f"^{{{num}{sign}}}"

    label = re.sub(r'\[([+-])(\d+)\]', _charge_repl, label)

    # --- element counts (H2O → H_2O) ---
    label = re.sub(r'([A-Za-z])(\d+)', r'\1_{\2}', label)
    # --- parenthesis groups (RuO4)2 → (RuO₄)_2 ---
    label = re.sub(r'(\))(\d+)', r'\1_{\2}', label)
    # --- final wrap in a single $...$ ---
    return f"${label}$"


def create_poscar_from_materials(optimade_materials: dict) -> io.BytesIO:
    """
    Create a POSCAR file from the materials dictionary.

    This function takes a dictionary of materials where the keys are the chemical
    system and the values are dictionaries of databases and materials.
    It returns a BytesIO object containing a ZIP file where each material is
    stored as a separate POSCAR file.

    The format of the ZIP file is as follows:

    - Each material is stored in a separate file with the name
      `<chemsys>/<database_name>/<material_id>.POSCAR`
    - The contents of each file are the POSCAR string for the material

    :param optimade_materials: A dictionary of materials where the keys are the chemical
                                system and the values are dictionaries of databases and materials
    :return: A BytesIO object containing a ZIP file with the materials as separate POSCAR files
    :rtype: BytesIO
    """
    # Create an in-memory ZIP buffer
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for chemsys, chemsys_dict in optimade_materials.items():
            for database, database_dict in chemsys_dict.items():
                for material_id, material_data in database_dict.items():
                    data = material_data["normalized_attributes"]
                    database_name = format_database_name(database)
                    try:
                        structure = convert_to_structure(data)
                        poscar = Poscar(structure)
                        poscar_str = poscar.get_string()
                        # Folder path inside the zip
                        zip_path = f"{chemsys}/{database_name}/{material_id}.POSCAR"
                        # Write the POSCAR text file into the zip
                        zip_file.writestr(zip_path, poscar_str)
                    except Exception as e:
                        print(
                            f"⚠️ Skipping {chemsys}/{database_name}/{material_id}: {e}")
    zip_buffer.seek(0)
    return zip_buffer


def create_cif_from_materials(optimade_materials: dict) -> io.BytesIO:
    """
    Create a CIF file from the materials dictionary.

    This function takes a dictionary of materials where the keys are the chemical
    system and the values are dictionaries of databases and materials.
    It returns a BytesIO object containing a ZIP file where each material is
    stored as a separate CIF file.

    The format of the ZIP file is as follows:

    - Each material is stored in a separate file with the name
      `<chemsys>/<database_name>/<material_id>.cif`
    - The contents of each file are the CIF string for the material

    :param optimade_materials: A dictionary of materials where the keys are the chemical
                                system and the values are dictionaries of databases and materials
    :return: A BytesIO object containing a ZIP file with the materials as separate CIF files
    :rtype: BytesIO
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for chemsys, chemsys_dict in optimade_materials.items():
            for database, database_dict in chemsys_dict.items():
                for material_id, material_data in database_dict.items():
                    data = material_data["normalized_attributes"]
                    database_name = format_database_name(database)
                    try:
                        # Convert OPTIMADE data to a pymatgen Structure
                        structure = convert_to_structure(data)

                        # Use pymatgen's CifWriter to generate CIF string
                        cif_writer = CifWriter(structure)
                        cif_str = cif_writer.__str__()

                        # Define the folder path inside the ZIP
                        zip_path = f"{chemsys}/{database_name}/{material_id}.cif"

                        # Write the CIF text into the ZIP archive
                        zip_file.writestr(zip_path, cif_str)
                    except Exception as e:
                        print(
                            f"⚠️ Skipping {chemsys}/{database_name}/{material_id}: {e}")

    # Reset buffer pointer and return
    zip_buffer.seek(0)
    return zip_buffer


def create_ase_from_materials(optimade_materials: dict) -> bytes:
    """
    Create an ASE atoms object from a dictionary of materials.

    The function takes a dictionary of materials where the keys are the chemical
    system and the values are dictionaries of databases and materials ids, and the
    values of each material id is a dictionary with the following keys:

    - "id": the material id
    - "database": the database the material is from
    - "chemsys": the chemistry system the material is from

    The function returns a bytes object containing the pickled ASE atoms object.

    :param optimade_materials: A dictionary of materials
    :return: A bytes object containing the pickled ASE atoms object
    :rtype: bytes
    """
    # Pickle the materials
    atoms_adaptor = AseAtomsAdaptor()
    # Create a default dict of atoms objects
    atoms_dict = defaultdict(nested_defaultdict)

    for chemsys, chemsys_dict in optimade_materials.items():
        for database, database_dict in chemsys_dict.items():
            for material_id, material_data in database_dict.items():
                data = material_data["normalized_attributes"]
                database_name = format_database_name(database)
                try:
                    structure = convert_to_structure(data)
                    atoms_dict[chemsys][database_name][material_id] = atoms_adaptor.get_atoms(
                        structure)
                except Exception as e:
                    print(f"⚠️ Skipping {chemsys}/{database_name}/{material_id}: {e}")

    # Pickle into memory (not to disk)
    buffer = io.BytesIO()
    pickle.dump(atoms_dict, buffer)
    buffer.seek(0)  # reset pointer for reading
    return buffer.getvalue()

def download_materials(optimade_materials: dict, dtype: str = "POSCAR") -> bytes | io.BytesIO:
    """
    Download materials in the given data type.

    Args:
        optimade_materials (dict): A dictionary of materials where the keys are the chemical
            system and the values are dictionaries of databases and materials ids.
        dtype (str, optional): The data type to download the materials in. Defaults to "POSCAR".

    Returns:
        bytes: The downloaded materials in the given data type.

    Raises:
        ValueError: If the given dtype is not one of "POSCAR", "CIF", "ASE Atoms" or "JSON".
    """
    match dtype:
        case "JSON":
            return json.dumps(optimade_materials, indent=2)
        case "POSCAR":
            return create_poscar_from_materials(optimade_materials)
        case "CIF":
            return create_cif_from_materials(optimade_materials)
        case "ASE Atoms":
            return create_ase_from_materials(optimade_materials)
        case _:
            raise ValueError(
                f"Invalid dtype '{dtype}'. Must be 'POSCAR', 'CIF', 'ASE Atoms' or 'JSON'.")

def download_duplicate_figures(figures: dict) -> io.BytesIO:
    """
    Download figures in the given data type.

    Args:
        figures (dict): A dictionary of figures where the keys are the chemical
            system and the values are plotly figures.

    Returns:
        io.BytesIO: A bytes object containing the downloaded figures.
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for chemsys, fig in figures.items():
            html_str = fig.to_html(full_html=True, include_plotlyjs="cdn")
            zip_file.writestr(chemsys + ".html", html_str)

    zip_buffer.seek(0)
    return zip_buffer

def download_hull_figures(figures: dict) -> io.BytesIO:
    """
    Download figures in the given data type.

    Args:
        figures (dict): A dictionary of figures where the keys are the chemical
            system and the values are plotly figures.

    Returns:
        io.BytesIO: A bytes object containing the downloaded figures.
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for chemsys, fig in figures.items():

            # --- normalize figure type ---
            if isinstance(fig, str):
                fig = pio.from_json(fig)  # noqa: PLW2901

            elif isinstance(fig, Figure):
                pass
            else:
                raise TypeError(f"Unsupported figure type: {type(fig)}")

            html_str = fig.to_html(full_html=True, include_plotlyjs="cdn")
            zip_file.writestr(f"{chemsys}.html", html_str)

    zip_buffer.seek(0)
    return zip_buffer

def download_pourbaix_figures(figures: dict) -> io.BytesIO:
    """
    Download Pourbaix figures in the given data type.

    Args:
        figures (dict): A dictionary of Pourbaix figures where the keys are the chemical
            system and the values are dictionaries of databases and materials ids.

    Returns:
        io.BytesIO: A bytes object containing the downloaded Pourbaix figures.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for chemsys, chemsys_dict in figures.items():
            for database, database_dict in chemsys_dict.items():
                database_name = format_database_name(database)
                for material_id, png_bytes in database_dict.items():
                    zip_file.writestr(
                        f"{chemsys}/{database_name}/{material_id}.png",
                        png_bytes  # already rendered, no savefig here
                    )
    zip_buffer.seek(0)
    return zip_buffer
