# DuplicateRemover

`matcollect.core.duplicate_removal.duplicate_remover.DuplicateRemover`

Identifies and removes duplicate materials across databases by comparing crystal structures with PyMatGen's `StructureMatcher`. Produces deduplicated materials and network visualisations of the duplicate relationships.

## Constructor

```python
DuplicateRemover(
    materials,
    priority_database_list,
    tolerances={"ltol": 0.2, "stol": 0.3, "angle_tol": 5}
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `materials` | `dict` | required | Nested dictionary of materials keyed by chemical system, then database, then material ID |
| `priority_database_list` | `list` | required | Ordered list of database names. When duplicates are found, the entry from the earliest database in this list is kept |
| `tolerances` | `dict` | `{"ltol": 0.2, "stol": 0.3, "angle_tol": 5}` | Tolerance parameters passed to `StructureMatcher` |

### Tolerances

| Key | Default | Description |
|---|---|---|
| `ltol` | `0.2` | Fractional tolerance in lattice vector lengths |
| `stol` | `0.3` | Site tolerance, normalised to average free length per atom |
| `angle_tol` | `5` | Maximum allowed difference in lattice angles, in degrees |

## Attributes

| Attribute | Type | Description |
|---|---|---|
| `materials` | `dict` | Input materials dictionary |
| `priority_database_list` | `list` | Ordered list of database names. When duplicates are found, the entry from the earliest database in this list is kept. Ties within a database are broken by lowest formation energy, then by order of appearance |
| `tolerances` | `dict` | Active tolerance parameters |
| `unique_materials` | `dict` | Deduplicated materials, same nested structure as input. Populated after `deduplicate()` |
| `truth_matrices` | `dict` | Maps each chemical system to a boolean NumPy array marking duplicate pairs. Populated after `deduplicate()` |
| `truth_figures` | `dict` | Maps each chemical system to a Plotly network figure. Populated after `deduplicate()` |

## Methods

### `deduplicate`

```python
deduplicate() -> tuple[dict, dict]
```

Runs the full deduplication pipeline:

1. Converts each material into a PyMatGen `Structure`, grouped by chemical system and ordered by database priority.
2. Computes pairwise structural similarity within each chemical system using `StructureMatcher`, comparing only structures that share a reduced formula.
3. Groups duplicate structures into connected components and keeps one representative from each: the entry from the highest-priority database, then the lowest `formation_energy_per_atom`, then the earliest in the list. Materials with no formation energy are ranked last.
4. Generates a network figure per chemical system.

Returns a tuple of `(unique_materials, truth_figures)`. Both are also stored as instance attributes.

Per-stage timing is printed to stdout.

---

### `generate_network_figures`

```python
generate_network_figures(structures_by_chemsys) -> dict[str, go.Figure]
```

Builds a force-directed network graph for each chemical system. Nodes are individual materials; edges connect pairs identified as duplicates. Node colour encodes the source database, and node shape distinguishes kept entries (`circle`) from removed ones (`x`).

| Parameter | Type | Description |
|---|---|---|
| `structures_by_chemsys` | `dict[str, list]` | Structures grouped by chemical system, as produced internally during `deduplicate()` |

Returns a dictionary mapping each chemical system to a Plotly `Figure`. Also stored as `self.network_figures`.

This method is called automatically by `deduplicate()` and relies on `truth_matrices` and `unique_materials` already being populated.

## Output structure

`unique_materials` preserves the same nesting as the input:

```python
{
    chemsys: {
        database: {
            material_id: { ... }
        }
    }
}
```

## Notes

Structure comparison runs across processes via a `ProcessPoolExecutor`. Each worker holds a single `StructureMatcher` instance initialised once with the configured tolerances, defined in the accompanying `workers` module:

| Function | Description |
|---|---|
| `worker_init(tolerances)` | Initialises a per-process `StructureMatcher` with the given tolerances |
| `check_pair_worker(args)` | Compares one pair of structures and returns `(i, j, match)` |

Only structures sharing a reduced formula are compared, which keeps the number of pairwise comparisons tractable for large chemical systems.