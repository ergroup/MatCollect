"""Contains the HullAnalyzer class for analyzing materials stability."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import combinations
from urllib.parse import urlparse

from plotly.graph_objs import Figure
from pymatgen.analysis.phase_diagram import PDPlotter, PhaseDiagram

from matcollect.core.database_search.optimade_extractor import OptimadeExtractor
from matcollect.core.utils.pymatgen_helper import convert_to_pd_entry

FONT_COLOR = "black"
TITLE_FONT_SIZE = 28
TICK_FONT_SIZE = 24
LABEL_FONT_SIZE = 26
LEGEND_FONT_SIZE = 24

LINE_WIDTH = 5
MARKER_SIZE = 14

COLORBAR_THICKNESS = 24
COLORBAR_LEN = 0.8

TERNARY_TICK_FONT_SIZE = 22
TERNARY_TITLE_FONT_SIZE = 22

FALLBACK_PROVIDER = "mp"  # last-resort provider for terminal reference energies

PROVIDER_LOOKUP = {
    "https://aflow.org": "aflow",
    "https://alexandria.icams.rub.de": "alexandria",
    "https://www.crystallography.net/cod": "cod",
    "https://cmr.fysik.dtu.dk": "cmr",
    "https://example.com": "exmpl",
    "http://matcloud.cnic.cn": "matcloud",
    "https://www.materialscloud.org": "mcloud",
    "https://archive.materialscloud.org": "mcloudarchive",
    "https://www.materialsproject.org": "mp",
    "https://www.phaseslab.com/mpdd": "mpdd",
    "https://mpds.io": "mpds",
    "https://matterverse.ai": "matterverse",
    "http://mpod.cimav.edu.mx": "mpod",
    "https://nomad-lab.eu": "nmd",
    "https://odbx.science": "odbx",
    "https://openmaterialsdb.se": "omdb",
    "https://oqmd.org": "oqmd",
    "https://jarvis.nist.gov": "jarvis",
    "https://www.crystallography.net/tcod": "tcod",
    "http://2dmatpedia.org": "twodmatpedia",
    "https://atomgpt.org": "atomgpt",
}


class TerminalEnergyFetchError(RuntimeError):
    """Raised only when an elemental reference energy could not be obtained from
    either the requested provider OR the Materials Project fallback.
    """


def _normalize_url(value: str) -> str:
    """Strip scheme, 'www.' prefix, and trailing slash so URL comparisons aren't
    thrown off by http-vs-https or a missing/extra 'www.'.
    """
    parsed = urlparse(value if "://" in value else f"https://{value}")
    netloc = parsed.netloc.lower()
    netloc = netloc.removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


def _font(size: int) -> dict:
    """Fully-specified font dict, so nothing is inherited from pymatgen/template defaults."""
    return {"size": size, "color": FONT_COLOR}


class HullAnalyzer:
    """A class for analyzing materials stability via energy above hull calculations."""

    def __init__(self, materials_dict: dict, terminal_energy_provider: str = "mp"):
        """
        Initialize a HullAnalyzer object.

        Parameters
        ----------
        materials_dict : dict
            A dictionary containing the materials data.
        terminal_energy_provider : str
            The OPTIMADE provider id (e.g. "mp", "oqmd", "cod") — or a base URL that
            resolves to one — to source terminal (elemental) reference entries from.
            If this provider fails to supply a usable energy for ANY required element,
            ALL terminal entries are refetched from Materials Project ("mp") instead,
            so the hull stays on one consistent reference scale. Whether this happened
            is recorded in `self.used_fallback_provider`.

        Attributes
        ----------
        terminal_entries : dict
            A dictionary containing the terminal entries for each element/sub-chemsys.
        fallback_notices : list[str]
            Elements whose terminal energy had to be fetched from Materials Project
            instead of the requested provider.
        hull_materials : dict
            A dictionary containing the materials for each chemistry system.
        hull_phase_diagrams : dict
            A dictionary containing the phase diagrams for each chemistry system.
        """
        self.materials_dict = materials_dict
        self.terminal_energy_provider = self._resolve_terminal_energy_provider(
            terminal_energy_provider
        )
        self.used_fallback_provider = False
        self.terminal_entries = self._get_terminal_entries()

        self.hull_materials = {}
        self.hull_phase_diagrams = {}

    @staticmethod
    def _resolve_terminal_energy_provider(value: str) -> str:
        """Resolve a stored database identifier — which may be a short OPTIMADE
        provider id ('mp') or a full/partial base URL (e.g.
        'https://alexandria.icams.rub.de/pbe') — to the short provider id that
        OptimadeExtractor's include_providers expects.
        """
        value = value.strip()

        if value in PROVIDER_LOOKUP.values():
            return value

        normalized_value = _normalize_url(value)

        for base_url in sorted(PROVIDER_LOOKUP, key=len, reverse=True):
            if _normalize_url(base_url) in normalized_value:
                return PROVIDER_LOOKUP[base_url]

        raise ValueError(
            f"Could not resolve '{value}' to a known OPTIMADE provider id. "
            f"Known providers: {sorted(PROVIDER_LOOKUP.values())}"
        )

    def analyze(self, energy_visibility_threshold: float = 1.0) -> tuple[dict, dict]:
        """
        Analyze the materials in the given dictionary.

        For each chemsys, it constructs a phase diagram and plots it.
        It then updates the energy_above_hull values for each material
        and parses the material dictionary.

        Returns a tuple of two dictionaries: the first contains the parsed
        materials dictionary, and the second contains the phase diagrams.

        :return: tuple[dict, dict]
        """
        pd_entries = {}
        for chemsys, chemsys_materials in self.materials_dict.items():
            entries = self._build_pd_entries(chemsys_materials)

            list_of_elements = chemsys.split("-")
            all_chemsys = []
            for r in range(1, len(list_of_elements) + 1):
                for combo in combinations(list_of_elements, r):
                    all_chemsys.append(sorted(combo))  # noqa: PERF401

            terminal_entries = []
            for possible_chemsys in all_chemsys:
                if possible_chemsys == list_of_elements:
                    continue
                possible_chemsys_str = "-".join(possible_chemsys)
                terminal_entries.extend(self.terminal_entries.get(possible_chemsys_str, []))

            phase_diagram = PhaseDiagram(entries + terminal_entries)

            if len(list_of_elements) <= 3:  # noqa: PLR2004
                plotter = PDPlotter(phase_diagram, show_unstable=energy_visibility_threshold)
                fig = plotter.get_plot()

                self._apply_figure_layout(fig, list_of_elements)
                self.hull_phase_diagrams[chemsys] = fig.to_json()

            pd_entries[chemsys] = entries
            self._update_hull_energies(phase_diagram, entries)

        self.hull_materials = self._parse_materials(pd_entries)
        return self.hull_materials, self.hull_phase_diagrams

    def filter_stable_materials(self, materials: dict, energy_threshold: float) -> dict:
        """
        Filter materials based on energy above hull.

        Parameters
        ----------
        materials : dict
            A dictionary containing the materials data.
        energy_threshold : float
            The energy threshold (in eV) below which the material is considered stable.

        Returns
        -------
        dict
            A dictionary containing the filtered materials data.
        """
        filtered_materials = defaultdict(lambda: defaultdict(dict))
        for chemsys, chemsys_dict in materials.items():
            for database, database_dict in chemsys_dict.items():
                for material_id, entry in database_dict.items():
                    attributes = entry["normalized_attributes"]
                    if attributes["energy_above_hull"] is not None and \
                            attributes["energy_above_hull"] <= energy_threshold:
                        filtered_materials[chemsys][database][material_id] = entry
        return filtered_materials

    def _build_pd_entries(self, chemsys_materials: dict) -> list:
        """Convert materials in a chemsys to PDEntry objects."""
        entries = []
        for database_materials in chemsys_materials.values():
            for material_id, material in database_materials.items():
                attributes = material["normalized_attributes"]
                if attributes.get("formation_energy_per_atom") is None:
                    continue
                pd_entry = convert_to_pd_entry(
                    entry=attributes,
                    material_id=material_id,
                    data=material
                )
                entries.append(pd_entry)
        return entries

    def _apply_ternary_layout(self, fig: Figure, layout_kwargs: dict, ternary_axis: dict) -> None:
        """Apply ternary-specific layout overrides."""
        layout_kwargs["width"] = 1100
        layout_kwargs["ternary"] = {
            "aaxis": {**ternary_axis, "dtick": 0.2},
            "baxis": {**ternary_axis, "dtick": 0.2},
            "caxis": {**ternary_axis, "dtick": 0.2},
        }
        layout_kwargs["legend"] = {
            "font": {"size": LEGEND_FONT_SIZE},
            "title_font": {"size": LEGEND_FONT_SIZE},
            "x": 0.05,
            "y": 1.0,
            "xanchor": "left",
            "yanchor": "top",
        }
        layout_kwargs["margin"] = {
            "t": 80, "b": 80, "l": 0, "r": 0, "autoexpand": True
        }
        fig.update_traces(
            marker={"size": MARKER_SIZE},
            line={"width": LINE_WIDTH},
            selector={"type": "scatterternary"}
        )
        for trace in fig.data:
            if hasattr(trace, "marker") and hasattr(trace.marker, "colorscale") and trace.marker.colorscale:
                trace.marker.showscale = True
                trace.marker.colorbar = {
                    "x": 0.9,
                    "xanchor": "left",
                    "y": 0.5,
                    "yanchor": "middle",
                    "title": {
                        "text": "Energy above hull (eV atom⁻¹)",
                        "font": _font(TITLE_FONT_SIZE),
                        "side": "right",
                    },
                    "tickfont": _font(TICK_FONT_SIZE),
                    "tick0": 0.0,
                    "thickness": COLORBAR_THICKNESS,
                    "len": COLORBAR_LEN,
                }
                break

    def _apply_figure_layout(self, fig: Figure, list_of_elements: list) -> None:
        """Apply consistent layout styling to a phase diagram figure."""
        for trace in fig.data:
            if hasattr(trace, "name") and trace.name and "label" in trace.name.lower():
                trace.showlegend = False

        common_axis = {
            "mirror": False,
            "showgrid": False,
            "ticks": "outside",
            "tickfont": _font(TICK_FONT_SIZE),
        }
        ternary_axis = {
            "showgrid": True,
            "ticks": "outside",
            "tickfont": _font(TERNARY_TICK_FONT_SIZE),
            "title_font": _font(TERNARY_TITLE_FONT_SIZE),
        }
        layout_kwargs = {
            "template": "simple_white",
            "autosize": True,
            "height": 600,
            "paper_bgcolor": "white",
            "font": _font(TICK_FONT_SIZE),
            "legend": {
                "font": {"size": LEGEND_FONT_SIZE},
                "title_font": {"size": LEGEND_FONT_SIZE},
                "x": 0,
                "y": 1.1,
            },
            "margin": {"l": 20, "r": 20, "t": 40, "b": 40},
        }

        fig.update_traces(
            marker={"size": MARKER_SIZE},
            line={"width": LINE_WIDTH},
        )

        for trace in fig.data:
            if hasattr(trace, "textfont"):
                trace.textfont = _font(LABEL_FONT_SIZE)

        for annotation in fig.layout.annotations:
            if annotation.text and annotation.text != "":
                annotation.font = _font(LABEL_FONT_SIZE)

        is_ternary = len(list_of_elements) == 3  # noqa: PLR2004
        if is_ternary:
            self._apply_ternary_layout(fig, layout_kwargs, ternary_axis)
        else:
            layout_kwargs["xaxis"] = {**common_axis, "dtick": 0.2}
            layout_kwargs["yaxis"] = common_axis
            for trace in fig.data:
                if hasattr(trace, "marker") and hasattr(trace.marker, "colorscale") and trace.marker.colorscale:
                    trace.marker.showscale = True
                    trace.marker.colorbar = {
                        "title": {
                            "text": "Energy above hull (eV atom⁻¹)",
                            "font": _font(TITLE_FONT_SIZE),
                            "side": "right",
                        },
                        "tickfont": _font(TICK_FONT_SIZE),
                        "thickness": COLORBAR_THICKNESS,
                        "len": COLORBAR_LEN,
                        "tick0": 0.0,
                    }
                    break

        fig.update_layout(**layout_kwargs)

        if not is_ternary:
            fig.update_yaxes(
                title_text="Formation energy (eV atom⁻¹)",
                title_font=_font(TITLE_FONT_SIZE),
            )
            fig.update_xaxes(
                title_font=_font(TITLE_FONT_SIZE),
            )

    def _update_hull_energies(self, phase_diagram: PhaseDiagram, entries: list) -> None:
        """Sync energy_above_hull and formation_energy_per_atom from the phase diagram."""
        for entry in entries:
            e_above_hull = phase_diagram.get_e_above_hull(entry)
            form_energy = phase_diagram.get_form_energy_per_atom(entry)
            entry.attribute["normalized_attributes"]["energy_above_hull"] = e_above_hull
            entry.attribute["normalized_attributes"]["formation_energy_per_atom"] = form_energy

    def _collect_unique_elements(self) -> dict:
        """Collect unique elements per chemsys, skipping systems with more than 3 elements."""
        unique_elements = {}
        for chemsys, chemsys_materials in self.materials_dict.items():
            unique_elements[chemsys] = []
            for database_materials in chemsys_materials.values():
                for material in database_materials.values():
                    attributes = material["normalized_attributes"]
                    for element in attributes["composition"]:
                        if element not in unique_elements[chemsys]:
                            unique_elements[chemsys].append(element)
        return unique_elements

    def _build_all_chemsys(self, unique_elements: dict) -> list:
        """Generate all unique sub-chemsys combinations, always including hydrogen."""
        all_chemsys = []
        for elements in unique_elements.values():
            for r in range(1, len(elements) + 1):
                for combo in combinations(elements, r):
                    new_chemsys = sorted(combo)
                    if new_chemsys not in all_chemsys:
                        all_chemsys.append(new_chemsys)
        if ["H"] not in all_chemsys:
            all_chemsys.insert(0, ["H"])
        return all_chemsys

    def _fetch_terminal_entries_worker(self, chemsys: list, provider: str) -> tuple[str, list]:
        extractor = OptimadeExtractor(
            include_providers=[provider],
            use_async=True
        )
        entries = self._fetch_terminal_entries_for_chemsys(extractor, chemsys)
        return "-".join(chemsys), entries

    def _fetch_terminal_entries_for_chemsys(self,
                                            extractor: OptimadeExtractor,
                                            chemsys: list) -> list:
        """Fetch and convert terminal PDEntries for a single chemsys from the extractor."""
        extractor.generate_elements_filter(chemsys)
        extractor.extract(flush=True)
        retrieved_materials = extractor.dump()
        entries = []
        for chemsys_materials in retrieved_materials.values():
            for database_materials in chemsys_materials.values():
                for material_id, material in database_materials.items():
                    attributes = material["normalized_attributes"]
                    if attributes.get("formation_energy_per_atom") is None:
                        continue
                    pd_entry = convert_to_pd_entry(
                        entry=attributes,
                        material_id=material_id,
                        data=material
                    )
                    entries.append(pd_entry)
        return entries

    def _fetch_all_chemsys(self, chemsys_list: list, provider: str) -> dict:
        """Fetch terminal entries for a list of chemsys combos from a specific provider.
        Used both for the primary provider pass and the Materials Project fallback pass.
        """
        entries_by_chemsys = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(self._fetch_terminal_entries_worker, chemsys, provider)
                for chemsys in chemsys_list
            ]
            for future in as_completed(futures):
                chemsys_str, entries = future.result()
                entries_by_chemsys[chemsys_str] = entries
        return entries_by_chemsys

    def _get_terminal_entries(self) -> dict:
        unique_elements = self._collect_unique_elements()
        all_chemsys = self._build_all_chemsys(unique_elements)

        terminal_entries = self._fetch_all_chemsys(all_chemsys, self.terminal_energy_provider)

        # Only single-element vertices are mandatory hull anchors — a missing
        # binary/ternary sub-system just means no known compound there, which is
        # valid. A missing element (empty due to no response, or no
        # formation_energy_per_atom) is what actually breaks the hull.
        missing_elements = sorted(
            chemsys_str for chemsys_str, entries in terminal_entries.items()
            if "-" not in chemsys_str and not entries
        )

        if not missing_elements:
            return terminal_entries

        if self.terminal_energy_provider == FALLBACK_PROVIDER:
            raise TerminalEnergyFetchError(
                f"Could not fetch elemental reference energies for {missing_elements} "
                f"from Materials Project ('{FALLBACK_PROVIDER}'). The provider may be "
                f"temporarily down or rate-limited. Try again shortly."
            )

        # At least one element failed — refetch ALL terminal entries from Materials
        # Project instead, so every hull in this run uses a single, consistent
        # reference scale rather than mixing providers element-by-element.
        self.used_fallback_provider = True
        terminal_entries = self._fetch_all_chemsys(all_chemsys, FALLBACK_PROVIDER)

        still_missing = sorted(
            chemsys_str for chemsys_str, entries in terminal_entries.items()
            if "-" not in chemsys_str and not entries
        )
        if still_missing:
            raise TerminalEnergyFetchError(
                f"Could not fetch elemental reference energies for {still_missing} "
                f"from '{self.terminal_energy_provider}' or from the Materials Project "
                f"fallback. Try a different reference database, or try again shortly."
            )

        return terminal_entries

    def _parse_materials(self, pd_entries: dict) -> dict:
        parsed_materials = defaultdict(lambda: defaultdict(dict))
        for chemsys, entries in pd_entries.items():
            for entry in entries:
                database = entry.attribute["normalized_attributes"]["database"]
                material_id = entry.attribute["normalized_attributes"]["material_id"]
                parsed_materials[chemsys][database][material_id] = entry.attribute
        return parsed_materials