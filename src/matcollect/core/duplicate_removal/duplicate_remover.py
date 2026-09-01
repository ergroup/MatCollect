"""Duplicate remover for structured data."""

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from time import time

import networkx as nx
import numpy as np
import plotly.graph_objects as go

# Relative Import
from matcollect.core.duplicate_removal.workers import check_pair_worker, worker_init
from matcollect.core.utils.pymatgen_helper import convert_to_structure


class DuplicateRemover:
    """
    A class for identifying and removing duplicate materials from a collection of structures.
    This class uses pymatgen's StructureMatcher to compare crystal structures across
    multiple databases and identify duplicates based on configurable tolerance parameters.
    It generates similarity matrices and can produce visualizations of the deduplication results.
    Attributes:
        materials (dict): A nested dictionary containing materials organized by chemical system,
            database, and material ID.
        priority_database_list (list): An ordered list of database names that defines the priority
            order for keeping materials when duplicates are found.
        tolerances (dict): Tolerance parameters for structure matching. Defaults to
            {"ltol": 0.2, "stol": 0.3, "angle_tol": 5}.
        unique_materials (dict): Output dictionary containing deduplicated materials with the
            same structure as the input materials dictionary.
        truth_matrices (dict): Output dictionary mapping chemical systems to boolean numpy arrays
            indicating which structures are duplicates of each other.
        truth_figures (dict): Output dictionary mapping chemical systems to plotly Figure objects
            visualizing the similarity matrices.
    """

    def __init__(self,
                 materials: dict,
                 priority_database_list: list,
                 tolerances: dict={"ltol": 0.2, "stol": 0.3, "angle_tol": 5}):
        """
        Initialize a DuplicateRemover object.

        Parameters:
        materials (dict): A nested dictionary containing materials organized by chemical system,
            database, and material ID.
        priority_database_list (list): An ordered list of database names that defines the priority
            order for keeping materials when duplicates are found.
        tolerances (dict): Tolerance parameters for structure matching. Defaults to
            {"ltol": 0.2, "stol": 0.3, "angle_tol": 5}.
        """
        self.materials = materials
        self.priority_database_list = priority_database_list
        self.tolerances = tolerances

        # Outputs
        self.unique_materials = {}
        self.truth_matrices = {}
        self.truth_figures = {}



    def deduplicate(self) -> dict:
        """
        Deduplicate materials by comparing their structures.
        Returns:
            dict: A nested dictionary containing deduplicated materials
                organized by chemical system, database, and material ID.
        """
        start_time = time()

        structures_by_chemsys = self._generate_pymatgen_structures_by_chemsys()
        generate_time = time()
        print(f"Generated pymatgen structures in {generate_time-start_time:.2f} seconds.")

        self.truth_matrices = self._get_structure_similarities(structures_by_chemsys,
                                                               self.tolerances)
        similarity_time = time()
        print(f"Calculated structure similarities in {similarity_time-generate_time:.2f} seconds.")

        unique_structures_by_chemsys = self._remove_duplicate_structures(structures_by_chemsys,
                                                                         self.truth_matrices)
        removal_time = time()
        print(f"Removed duplicate structures in {removal_time-similarity_time:.2f} seconds.")

        self.unique_materials = self._parse_structures(unique_structures_by_chemsys)
        parse_time = time()
        print(f"Parsed unique materials in {parse_time-removal_time:.2f} seconds.")

        self.truth_figures = self.generate_network_figures(structures_by_chemsys)
        figure_time = time()
        print(f"Generated network figures in {figure_time-parse_time:.2f} seconds.")
        return self.unique_materials, self.truth_figures

    def generate_network_figures(self,
                                structures_by_chemsys: dict[str, list]) -> dict[str, go.Figure]:
        """
        Generate a force-directed network graph for each chemical system,
        where nodes are materials and edges connect duplicate pairs (truth=1).

        Parameters:
            structures_by_chemsys (dict): A nested dictionary containing materials
                organized by chemical system, database, and material ID.
        Returns:
            dict: A dictionary mapping chemical systems to plotly Figure objects.
        """
        self.network_figures = {}

        palette = [
            "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
            "#FFA15A", "#19D3F3", "#FF6692", "#B6E880"
        ]

        for chemsys, truth_matrix in self.truth_matrices.items():
            z = np.array(truth_matrix, dtype=float)
            n = z.shape[0]

            structures = structures_by_chemsys[chemsys]
            labels = [s["database"] + "/" + s["material_id"] + " (" + s["json_entry"]["normalized_attributes"]["reduced_formula"] + ")"  # noqa: E501
                      for s in structures]
            symbols = ["circle" if s["material_id"] in self.unique_materials[chemsys][s["database"]]  # noqa: E501
                       else "x" for s in structures]
            databases = [s["database"] for s in structures]
            unique_dbs = sorted(set(databases))
            color_map = {db: palette[i % len(palette)] for i, db in enumerate(unique_dbs)}

            # Build graph — nodes are materials, edges are duplicate pairs
            G = nx.Graph()  # noqa: N806
            G.add_nodes_from(range(n))
            for i in range(n):
                for j in range(i + 1, n):
                    if z[i, j] == 1:
                        G.add_edge(i, j)

            # Spring layout — connected duplicates are pulled together
            pos = nx.spring_layout(G, seed=42, k=2 / np.sqrt(n) if n > 1 else 1)

            # Edge trace
            edge_x, edge_y = [], []
            for u, v in G.edges():
                x0, y0 = pos[u]
                x1, y1 = pos[v]
                edge_x += [x0, x1, None]
                edge_y += [y0, y1, None]

            edge_trace = go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line={"width": 2, "color": "#727272"},
                hoverinfo="none",
                showlegend=False
            )

            # Node traces (one per database for legend)
            node_traces = []
            for db in unique_dbs:
                indices = [i for i, d in enumerate(databases) if d == db]
                node_traces.append(go.Scatter(
                    x=[pos[i][0] for i in indices],
                    y=[pos[i][1] for i in indices],
                    mode="markers",
                    name=db,
                    marker={
                        "color": color_map[db],
                        "size": 10,
                        "opacity": 0.9,
                        "symbol": [symbols[i] for i in indices],
                        "line": {"width": 1, "color": "white"}
                    },
                    text=[labels[i] for i in indices],
                    hovertemplate="<b>%{text}</b><extra></extra>"
                ))

            fig = go.Figure(data=[edge_trace, *node_traces])
            fig.update_layout(
                title=f"Duplicate Network — {chemsys}",
                xaxis={"showticklabels": False, "showgrid": False, "zeroline": False},
                yaxis={"showticklabels": False, "showgrid": False, "zeroline": False},
                legend={"title": "Database"},
                margin={"l": 20, "r": 20, "t": 80, "b": 20},
                plot_bgcolor="#f9f9f9"
            )

            self.network_figures[chemsys] = fig

        return self.network_figures

    def _generate_pymatgen_structures_by_chemsys(self) -> dict[str, list]:
        structures_by_chemsys = {}
        for chemsys in self.materials:
            structures_by_chemsys[chemsys] = []
            for database in self.priority_database_list:
                if database not in self.materials[chemsys]:
                    continue
                for material_id in self.materials[chemsys][database]:
                    material = self.materials[chemsys][database][material_id]
                    struct = convert_to_structure(material["normalized_attributes"])
                    structures_by_chemsys[chemsys].append({
                        "structure": struct,
                        "material_id": material_id,
                        "database": database,
                        "chemsys": chemsys,
                        "json_entry": material
                    })
        return structures_by_chemsys


    def _get_structure_similarities(self,
                                    structures_by_chemsys: dict,
                                    tolerances: dict) -> dict[str, np.ndarray]:
        truth_matrices = {}

        # Flatten all work across all chemsys into one batch
        chemsys_meta = {}

        for chemsys, list_of_structures in structures_by_chemsys.items():
            n = len(list_of_structures)
            truth_matrix = np.zeros((n, n), dtype=bool)
            np.fill_diagonal(truth_matrix, val=True)
            truth_matrices[chemsys] = truth_matrix

            structures = [s["structure"] for s in list_of_structures]

            comp_groups = defaultdict(list)
            for idx, s in enumerate(list_of_structures):
                comp_key = s["structure"].composition.reduced_formula
                comp_groups[comp_key].append(idx)

            pairs = [
                (i, j)
                for group_indices in comp_groups.values()
                for i, j in combinations(group_indices, 2)
            ]

            chemsys_meta[chemsys] = {
                "structures": structures,
                "pairs": pairs,
            }

        # Single pool, initialised once across ALL chemsys
        with ProcessPoolExecutor(initializer=worker_init, initargs=(tolerances,)) as executor:
            futures = {}
            for chemsys, meta in chemsys_meta.items():
                structures = meta["structures"]
                pairs = meta["pairs"]
                if not pairs:
                    continue

                args_iter = [(i, j, structures[i], structures[j]) for i, j in pairs]
                chunksize = max(1, len(args_iter) // (executor._max_workers * 4))  # noqa: SLF001
                futures[chemsys] = executor.map(check_pair_worker, args_iter, chunksize=chunksize)

            for chemsys, results in futures.items():
                for i, j, match in results:
                    truth_matrices[chemsys][i, j] = match
                    truth_matrices[chemsys][j, i] = match

        return truth_matrices

    def _remove_duplicate_structures(self,
                                    structures_by_chemsys: dict["str", list],
                                    truth_matrices: dict["str", np.ndarray]) -> dict[str, list]:
        unique_structures_by_chemsys = {}
        db_rank = {db: i for i, db in enumerate(self.priority_database_list)}

        for chemsys, list_of_structures in structures_by_chemsys.items():
            truth_matrix = truth_matrices[chemsys]
            n = len(list_of_structures)

            def selection_key(idx: int, _structures: list=list_of_structures) -> tuple:
                s = _structures[idx]
                energy = s["json_entry"]["normalized_attributes"].get("formation_energy_per_atom")
                if energy is None or not float("inf"):
                    energy = float("inf")
                return (
                    db_rank.get(s["database"], len(db_rank)),  # priority database wins first
                    energy,                                    # then lowest formation energy
                    idx,                                       # stable fallback
                )

            # Build graph and find connected components
            G = nx.Graph()  # noqa: N806
            G.add_nodes_from(range(n))
            for i in range(n):
                for j in range(i + 1, n):
                    if truth_matrix[i, j]:
                        G.add_edge(i, j)

            # Keep the best representative from each component
            unique_indices = sorted(
                min(component, key=selection_key) for component in nx.connected_components(G)
            )

            unique_structures_by_chemsys[chemsys] = [list_of_structures[i] for i in unique_indices]
        return unique_structures_by_chemsys


    def _parse_structures(self,
                          list_of_structures_by_chemsys: dict[str, list]) -> dict[str, dict]:
        unique_materials = defaultdict(lambda: defaultdict(dict))

        for list_of_structures in list_of_structures_by_chemsys.values():
            for material in list_of_structures:
                chemsys = material["chemsys"]
                database = material["database"]
                material_id = material["material_id"]
                entry = material["json_entry"]
                unique_materials[chemsys][database][material_id] = entry
        return unique_materials
