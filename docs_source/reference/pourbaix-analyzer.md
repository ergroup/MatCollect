# PourbaixAnalyzer

`matcollect.core.stability_analysis.pourbaix_analyzer.PourbaixAnalyzer`

Computes electrochemical stability of materials by constructing Pourbaix diagrams and evaluating decomposition energies at a given pH and applied potential. Requires a Materials Project API key to fetch aqueous ion reference data.

## Constructor

```python
PourbaixAnalyzer(materials_dict, mp_api_key)
```

| Parameter | Type | Description |
|---|---|---|
| `materials_dict` | `dict` | Nested dictionary of materials keyed by chemical system, then database, then material ID |
| `mp_api_key` | `str` | Materials Project API key, used to fetch Pourbaix entries |

## Attributes

| Attribute | Type | Description |
|---|---|---|
| `materials_dict` | `dict` | Input materials dictionary |
| `mp_api_key` | `str` | Materials Project API key |
| `pourbaix_diagrams` | `dict` | Constructed `PourbaixDiagram` objects keyed by chemical system and composition. Populated after `analyze()` |
| `pourbaix_figures` | `dict` | Rendered diagram images keyed by chemical system, database, and material ID. Populated after `analyze()` |
| `pourbaix_materials` | `dict` | Intermediate `PourbaixEntry` objects with aqueous corrections applied |

## Methods

### `analyze`

```python
analyze(ph, u) -> tuple[dict, dict]
```

Runs the full Pourbaix analysis pipeline:

1. Converts materials into `PourbaixEntry` objects with aqueous corrections applied.
2. Groups entries by composition, excluding H and O which are inherent to the Pourbaix formalism.
3. Constructs a `PourbaixDiagram` per composition using reference entries fetched from the Materials Project.
4. Computes the decomposition energy of each material at the given pH and potential.
5. Renders a stability figure per material.

| Parameter | Type | Description |
|---|---|---|
| `ph` | `float` | pH at which to evaluate decomposition energy |
| `u` | `float` | Applied potential (V vs. SHE) at which to evaluate decomposition energy |

Returns a tuple of `(updated_materials_dict, pourbaix_figures)`.

The updated materials dictionary preserves the input nesting, with a `decomposition_energy_per_atom` field added to each entry's `normalized_attributes`. Materials whose diagram could not be constructed or whose decomposition energy could not be computed have this field set to `None`.

---

### `filter_stable_materials`

```python
filter_stable_materials(materials, energy_threshold) -> dict
```

Filters materials by decomposition energy.

| Parameter | Type | Description |
|---|---|---|
| `materials` | `dict` | Materials dictionary with `decomposition_energy_per_atom` populated |
| `energy_threshold` | `float` | Maximum decomposition energy (eV/atom) for a material to be kept |

Returns a filtered dictionary in the same nested structure. Materials with a `None` decomposition energy are excluded.

## Output

Each analysed material gains a `decomposition_energy_per_atom` field (eV/atom) in its `normalized_attributes`. Lower values indicate greater electrochemical stability at the specified operating conditions.

Figures are returned as PNG bytes, nested as:

```python
{
    chemsys: {
        database: {
            material_id: png_bytes
        }
    }
}
```

Each figure shows the entry's stability across the pH-potential plane, with the hydrogen and oxygen stability lines overlaid and the operating point marked.

## Aqueous energy corrections

Pourbaix diagrams require formation free energies referenced to gaseous H₂ and O₂ at 298 K, not raw DFT energies at 0 K. `PourbaixAnalyzer` applies a correction of **0.318 eV per oxygen atom** to account for the entropy of gaseous O₂ at 298 K, which is absent from 0 K DFT calculations.

This value derives from the O₂ entropy (S(O₂) = 205.15 J/mol·K, giving 0.317 eV/atom O) and was cross-checked against Materials Project Pourbaix energies on the Ir-O system, where a least-squares fit yields 0.318 eV/atom O at negligible RMSE.

References:

- Persson et al., *Phys. Rev. B* **85**, 235438 (2012)
- Wang, Kingsbury et al., *Sci. Rep.* **11**, 15496 (2021)
- Singh et al., *npj Materials Degradation* **3**, 15 (2019)

## Notes

Diagram construction depends on the Materials Project returning Pourbaix entries for a given chemical system. **Systems without available reference entries are skipped**, as are individual compositions that fail diagram construction (typically a `QhullError` from degenerate geometry).

Figure rendering runs across processes via a `ProcessPoolExecutor`. The accompanying `workers` module provides:

| Function | Description |
|---|---|
| `figure_worker_init(diagrams)` | Stores the constructed diagrams in each worker process |
| `figure_worker(args)` | Renders one material's stability figure and returns it as PNG bytes |

Operating conditions are clipped to a sensible range before rendering pH to (-2, 16), potential to (-3, 3) V.