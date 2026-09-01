"""Utility functions for pymatgen."""

from pymatgen.analysis.phase_diagram import PDEntry
from pymatgen.core import Composition, Structure
from pymatgen.core.lattice import Lattice
from pymatgen.core.units import Energy
from pymatgen.entries.computed_entries import ComputedEntry


def convert_to_structure(entry: dict) -> Structure:
    """
    Convert a dictionary containing structure information into a PyMatGen Structure object.

    Parameters
    ----------
    entry : dict
        A dictionary containing the following keys:
            - "lattice_vectors": A 3x3 list of lists containing the lattice vectors.
            - "species_at_sites": A list of the species at each site.
            - "cartesian_site_positions": A list of lists containing the
                                    Cartesian coordinates of each site.

    Returns
    -------
    Structure
        A PyMatGen Structure object created from the input dictionary.
    """
    lattice = Lattice(entry["lattice_vectors"])
    return Structure(lattice=lattice,
                       species=entry["species_at_sites"],
                       coords=entry["cartesian_site_positions"],
                       coords_are_cartesian=True)


def convert_to_pymatgen_entry(entry: dict,
                              material_id: str,
                              data:dict | None = None) -> ComputedEntry:
    """
    Convert a dictionary containing structure information and a material ID
    into a PyMatGen ComputedEntry object.

    Parameters
    ----------
    entry : dict
        A dictionary containing the following keys:
            - "lattice_vectors": A 3x3 list of lists containing the lattice vectors.
            - "species_at_sites": A list of the species at each site.
            - "cartesian_site_positions": A list of lists containing the
                                    Cartesian coordinates of each site.
    material_id : str
        The material ID to associate with the ComputedEntry.
    data : dict | None, optional
        Optional additional data to associate with the ComputedEntry.

    Returns
    -------
    ComputedEntry
        A PyMatGen ComputedEntry object created from the input dictionary.
    """
    struct = convert_to_structure(entry)

    # Get the formation energy
    energy_per_atom = Energy(entry["formation_energy_per_atom"],
                             unit="eV")
    n_atoms = entry["nsites"]
    formation_energy = energy_per_atom * n_atoms

    return ComputedEntry(struct.composition, formation_energy, entry_id=material_id, data=data)


class FormationEnergyEntry(PDEntry):
    """PDEntry subclass that exposes entry_id for PDPlotter compatibility."""

    def __init__(self,
                 composition: Composition,
                 formation_energy: float,
                 entry_id: str,
                 data: dict | None = None) -> None:
        """
        Initialize a FormationEnergyEntry object.

        Parameters
        ----------
        composition : Composition
            The composition of the material.
        formation_energy : float
            The formation energy of the material (in eV/atom).
        entry_id : str
            The material ID to associate with the FormationEnergyEntry.
        data : dict | None, optional
            Optional additional data to associate with the FormationEnergyEntry.

        Attributes
        ----------
        entry_id : str
            The material ID to associate with the FormationEnergyEntry.
        """
        super().__init__(composition, formation_energy, name=entry_id, attribute=data)
        self.entry_id = entry_id  # PDPlotter checks for this attribute explicitly

def convert_to_pd_entry(entry: dict,
                        material_id: str,
                        data: dict | None = None) -> FormationEnergyEntry:
    """
    Convert a dictionary representing a material into a FormationEnergyEntry object.

    Parameters
    ----------
    entry : dict
        A dictionary containing the material's chemical formula,
        formation energy per atom, and number of sites.
    material_id : str
        The material ID to associate with the FormationEnergyEntry.
    data : dict | None, optional
        Optional additional data to associate with the FormationEnergyEntry.

    Returns
    -------
    FormationEnergyEntry
        A FormationEnergyEntry object representing the material.

    """
    composition = Composition(entry["chemical_formula"])
    formation_energy_per_atom = entry["formation_energy_per_atom"]
    n_atoms = entry["nsites"]
    return FormationEnergyEntry(
        composition,
        formation_energy_per_atom * n_atoms,
        entry_id=material_id,
        data=data
    )
