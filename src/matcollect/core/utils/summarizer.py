"""This module contains functions for summarizing the materials dictionary."""

import pandas as pd


def material_counter(materials_dict: dict, sort_columns: bool = True) -> pd.DataFrame:
    """
    Generate a summary DataFrame of the materials dictionary.

    Parameters
    ----------
    materials_dict : dict
        A nested dictionary of materials, where the keys are the chemistry systems,
        the values are dictionaries of databases and materials ids, and the values of
        each material id is a dictionary with the following keys:
        - "id": the material id
        - "database": the database the material is from
        - "chemsys": the chemistry system the material is from
    sort_columns : bool
        If True, the columns of the summary DataFrame are sorted. Defaults to True.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the summary of the materials dictionary.
    """
    # Get the available databases in the materials dictionary
    available_databases = []
    chemsys_list = materials_dict.keys()

    if sort_columns:
        # Sort the chemsys list if sort_columns is True
        chemsys_list = sorted(chemsys_list)

    for chemsys in chemsys_list:
        # Add the databases to the available databases list
        available_databases.extend(materials_dict[chemsys].keys())

    # Remove duplicates from the list of available databases
    available_databases = list(set(available_databases))

    # Sort the list of available databases
    available_databases.sort()

    # Initialize a dictionary to store the summary
    summary_dict = {}

    # Iterate over the chemsys in the materials dictionary
    for chemsys in chemsys_list:
        # Initialize a dictionary for the current chemsys
        summary_dict[chemsys] = {}
        # Iterate over the available databases
        for database in available_databases:
            # Initialize the count of materials in the current database to 0
            summary_dict[chemsys][database] = 0

    # Iterate over the chemsys in the materials dictionary
    for chemsys in chemsys_list:
        # Iterate over the databases in the current chemsys
        for database in materials_dict[chemsys]:
            # Add the count of materials in the current database to the summary dictionary
            summary_dict[chemsys][database] += len(materials_dict[chemsys][database])

    # Convert the summary dictionary to a DataFrame
    summary_df = pd.DataFrame(summary_dict)

    # Sum on both axis
    summary_df["Total"] = summary_df.sum(axis=1)
    summary_df = summary_df.transpose()
    summary_df["Total"] = summary_df.sum(axis=1)
    return summary_df.transpose()



def summarize_materials_dict(materials_dict: dict,
                             attributes: list = ["material_id", "database", "chemsys",
                                                 "reduced_formula", "nsites",
                                                 "formation_energy_per_atom", "total_energy",
                                                 "band_gap", "space_group_symbol",
                                                 "nelements", "elements_ratios",
                                                 "nperiodic_dimensions"],
                             attribute_type:str = "normalized_attributes") -> pd.DataFrame:
    """
    Summarize the materials dictionary into a pandas DataFrame.

    Parameters
    ----------
    materials_dict : dict
        A nested dictionary of materials, where the keys are the chemistry systems,
        the values are dictionaries of databases and materials ids, and the values of
        each material id is a dictionary with the following keys:
        - "id": the material id
        - "database": the database the material is from
        - "chemsys": the chemistry system the material is from
        - "reduced_formula": the reduced formula of the material
        - "nsites": the number of sites in the material
        - "formation_energy_per_atom": the formation energy per atom
        - "total_energy": the total energy of the material
        - "band_gap": the band gap of the material
        - "space_group_symbol": the space group symbol of the material
        - "nelements": the number of elements in the material
        - "elements_ratios": the element ratios of the material
        - "nperiodic_dimensions": the number of periodic dimensions in the material
    attributes : list
        The attributes of the materials dictionary to include in the summary.

    Returns
    -------
    pd.DataFrame
        A pandas DataFrame containing the summary of the materials dictionary.
    """
    if not isinstance(materials_dict, dict):
        raise TypeError("materials_dict must be a dictionary")
    if not isinstance(attributes, list):
        raise TypeError("attributes must be a list")

    # Generate the summary dictionary
    summary = {}
    for attribute in attributes:
        summary[attribute] = []

    # Add the values to the summary
    for chemsys_dict in materials_dict.values():
        for database_dict in chemsys_dict.values():
            for material in database_dict.values():
                material_properties = material.get(attribute_type, {})
                for attribute in attributes:
                    summary[attribute].append(material_properties.get(attribute))
    return pd.DataFrame.from_dict(summary)
