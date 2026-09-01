# HullAnalyzer

`matcollect.core.stability_analysis.e_above_hull_analyzer.HullAnalyzer`

Computes thermodynamic stability by calculating each material's energy above the convex hull of stable phases in its chemical system. Produces phase diagram plots for systems with up to three elements.

## Constructor

```python
HullAnalyzer(
    materials_dict,
    terminal_energy_provider="mp"
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `materials_dict` | `dict` | required | Nested dictionary of materials keyed by chemical system, then database, then material ID |
| `terminal_energy_provider` | `str` | `"mp"` | Source of terminal (elemental) reference entries. Accepts either a short OPTIMADE provider id (`"mp"`, `"oqmd"`, `"odbx"`, …) or a full or partial base URL that resolves to one |

Provider resolution happens at construction. URLs are normalised — scheme, `www.` prefix, and trailing slash are stripped — so `https://www.materialsproject.org/`, `materialsproject.org`, and `mp` all resolve to the same id, and a longer URL such as `https://alexandria.icams.rub.de/pbe` matches its base entry. A value that cannot be resolved raises `ValueError` listing the known provider ids. The resolved short id is what gets stored on the instance.

### Terminal energy fallback

Only **single-element** vertices are mandatory hull anchors. A missing binary or ternary sub-system is legitimate — it simply means no known compound exists there — and is not treated as a failure.

If the requested provider fails to supply a usable energy for *any* required element, **all** terminal entries are refetched from the Materials Project. The refetch is wholesale rather than element-by-element, so every hull in the run stays on a single consistent reference scale instead of mixing providers. Whether this happened is recorded in `used_fallback_provider`.

`TerminalEnergyFetchError` is raised when:

- elements are still missing after the Materials Project fallback, or
- the requested provider already *was* the Materials Project, so no fallback is available.

In both cases the provider may be temporarily down or rate-limited; retrying shortly, or choosing a different reference database, is usually the fix.

## Attributes

| Attribute | Type | Description |
|---|---|---|
| `materials_dict` | `dict` | Input materials dictionary |
| `terminal_energy_provider` | `str` | Resolved short OPTIMADE provider id used for terminal entries |
| `used_fallback_provider` | `bool` | `True` if terminal entries had to be refetched from the Materials Project |
| `terminal_entries` | `dict` | Reference entries fetched from the active provider, keyed by sub-system |
| `hull_materials` | `dict` | Materials with `energy_above_hull` populated. Set after `analyze()` |
| `hull_phase_diagrams` | `dict` | Phase diagram figures as JSON, keyed by chemical system. Set after `analyze()` |

## Methods

### `analyze`

```python
analyze(energy_visibility_threshold=1.0) -> tuple[dict, dict]
```

Runs the full energy above hull pipeline:

1. Converts materials with a valid formation energy into phase diagram entries.
2. Combines them with terminal reference entries for all proper sub-systems of the chemical system.
3. Constructs a `PhaseDiagram` per chemical system.
4. Computes energy above hull and formation energy per atom for each material.
5. Renders a phase diagram plot for systems with three or fewer elements.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `energy_visibility_threshold` | `float` | `1.0` | Maximum energy above hull (eV/atom) for an unstable material to be shown on the plot. Does not affect which materials are analysed |

Returns a tuple of `(hull_materials, hull_phase_diagrams)`.

The materials dictionary preserves the input nesting, with `energy_above_hull` and a recomputed `formation_energy_per_atom` added to each entry's `normalized_attributes`. Materials without a valid formation energy are excluded from the hull and do not appear in the output.

---

### `filter_stable_materials`

```python
filter_stable_materials(materials, energy_threshold) -> dict
```

Filters materials by energy above hull.

| Parameter | Type | Description |
|---|---|---|
| `materials` | `dict` | Materials dictionary with `energy_above_hull` populated |
| `energy_threshold` | `float` | Maximum energy above hull (eV/atom) for a material to be kept |

Returns a filtered dictionary in the same nested structure. Materials with a `None` energy above hull are excluded.

## Output

Each analysed material gains two fields in its `normalized_attributes`:

| Field | Description |
|---|---|
| `energy_above_hull` | Energy above the convex hull (eV/atom). `0.0` means the material lies on the hull and is thermodynamically stable; higher values indicate likelihood of decomposition |
| `formation_energy_per_atom` | Formation energy per atom (eV/atom), recomputed against the constructed phase diagram |

Phase diagram figures are returned as Plotly JSON strings, keyed by chemical system. Binary systems render as 2D plots and ternary systems as ternary plots. Systems with four or more elements are analysed numerically but produce no figure.

## Notes

Terminal entries are fetched in parallel from the active provider via a `ThreadPoolExecutor` during initialisation. Hydrogen is always included among the reference sub-systems so that hydride and aqueous-adjacent phases are accounted for.

Only systems with one, two, or three distinct elements can be visualised. The convex hull is still computed for larger systems, and energy above hull values remain available in the output, **but no plot is generated**.

`hull_materials` and the dictionary returned by `filter_stable_materials` are nested `defaultdict` objects rather than plain dicts. Indexing a missing key silently creates an empty entry instead of raising `KeyError`, and neither object can be pickled directly.