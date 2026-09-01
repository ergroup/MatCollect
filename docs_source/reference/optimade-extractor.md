# OptimadeExtractor

`matcollect.core.database_search.optimade_extractor.OptimadeExtractor`

Queries OPTIMADE-compliant providers and normalises results into a unified nested dictionary format.

## Constructor

```python
OptimadeExtractor(
    include_providers=None,
    exclude_providers=["aflow"],
    max_results_per_provider=None,
    use_async=False,
    timeout=120.0
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `include_providers` | `list[str] \| None` | `None` | Provider IDs to query. If `None`, all available providers are used |
| `exclude_providers` | `list[str] \| None` | `["aflow"]` | Provider IDs to exclude |
| `max_results_per_provider` | `int \| None` | `None` | Cap on results per provider. If `None`, no limit is applied |
| `use_async` | `bool` | `False` | Whether to use async HTTP requests |
| `timeout` | `float \| None` | `120.0` | HTTP timeout in seconds |

## Methods

### `generate_elements_filter`

```python
generate_elements_filter(
    elements,
    only_elements=True,
    min_elements=None,
    max_elements=None
) -> str
```

Constructs an OPTIMADE filter string from a list of element symbols and stores it on the instance.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `elements` | `list[str]` | required | Element symbols to filter by, e.g. `["Fe", "O"]` |
| `only_elements` | `bool` | `True` | If `True`, restricts results to materials containing exactly these elements |
| `min_elements` | `int \| None` | `None` | Minimum number of elements in the system. Only used when `only_elements=False` |
| `max_elements` | `int \| None` | `None` | Maximum number of elements in the system. Only used when `only_elements=False` |

Returns the generated filter string, which is also stored as `self.optimade_filter`.

Raises `TypeError` if `elements` is not a list of strings.

---

### `set_filter`

```python
set_filter(optimade_filter) -> str
```

Manually set an OPTIMADE filter string instead of using `generate_elements_filter`.

| Parameter | Type | Description |
|---|---|---|
| `optimade_filter` | `str \| list[str] \| None` | Filter string or list of strings joined with `AND` |

---

### `extract`

```python
extract(flush=True) -> dict
```

Executes the stored filter against all configured providers.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `flush` | `bool` | `True` | If `True`, clears previous results before extracting |

Returns the raw OPTIMADE response dictionary. Also triggers internal normalisation of all retrieved entries.

---

### `extract_many`

```python
extract_many(
    chemsys_list,
    only_elements=True,
    min_elements=None,
    max_elements=None,
    max_workers=8
) -> dict
```

Fetches multiple chemical systems in parallel, each in its own thread with a dedicated extractor instance.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `chemsys_list` | `list[list[str]]` | required | List of chemical systems, e.g. `[["Fe", "O"], ["Li", "Fe", "O"]]` |
| `only_elements` | `bool` | `True` | Passed to `generate_elements_filter` for each system |
| `min_elements` | `int \| None` | `None` | Passed to `generate_elements_filter` for each system |
| `max_elements` | `int \| None` | `None` | Passed to `generate_elements_filter` for each system |
| `max_workers` | `int` | `8` | Maximum number of parallel threads |

Returns a merged `dump()` dictionary keyed by chemical system string.

Raises `RuntimeError` if any individual system fails to extract.

---

### `dump`

```python
dump() -> dict
```

Returns extracted and normalised materials as a nested dictionary:

```python
{
    chemsys: {
        database: {
            material_id: {
                "source_attributes": { ... },
                "normalized_attributes": { ... }
            }
        }
    }
}
```

---

### `parse_errors`

```python
parse_errors() -> list[dict]
```

Returns a list of provider errors encountered during the last `extract()` or `extract_many()` call. Each entry is a dictionary with the following keys:

| Key | Description |
|---|---|
| `provider` | Hostname of the provider that returned the error |
| `status` | HTTP status code as a string |
| `friendly` | Human-readable error description |

Common status codes:

| Status | Meaning |
|---|---|
| `429` | Rate limited |
| `500` | Internal server error |
| `502` | Bad gateway |
| `503` | Service unavailable |
| `404` | Endpoint not found |

## Normalised attributes

After extraction, each material entry contains a `normalized_attributes` dictionary with the following fields. Fields that cannot be resolved from a given provider are set to `None`.

| Field | Type | Description |
|---|---|---|
| `material_id` | `str` | Provider-assigned material ID |
| `database` | `str` | Provider base URL |
| `chemical_formula` | `str` | Full chemical formula |
| `reduced_formula` | `str` | Reduced formula |
| `chemsys` | `str` | Hyphen-separated sorted element symbols, e.g. `Fe-O` |
| `nelements` | `int` | Number of distinct elements |
| `nsites` | `int` | Number of sites in the unit cell |
| `composition` | `dict` | Element counts |
| `composition_reduced` | `dict` | Reduced element counts |
| `composition_fractional` | `dict` | Fractional occupancies |
| `elements_ratios` | `list[float]` | Fractional occupancy values in composition order |
| `space_group_symbol` | `str` | Space group symbol, if structure data is available |
| `space_group_number` | `int` | Space group number, if structure data is available |
| `total_energy` | `float` | Total energy (eV) |
| `formation_energy_per_atom` | `float` | Formation energy per atom (eV/atom) |
| `band_gap` | `float` | Band gap (eV) |
| `magnetic_moments` | `list` | Per-site magnetic moments |
| `lattice_vectors` | `list` | Lattice vectors |
| `cartesian_site_positions` | `list` | Cartesian atomic positions |
| `species_at_sites` | `list` | Species occupying each site |
| `nperiodic_dimensions` | `int` | Number of periodic dimensions |

Space group information is derived from PyMatGen's `Structure` class when full structure data (lattice vectors, positions, species) is available. If structure data is absent, it falls back to database-reported fields and space group fields are set to `None`.

Formation energy is resolved from provider-specific tags in the following order of precedence per provider:

- Alexandria: `_alexandria_formation_energy_per_atom`
- OQMD: `_oqmd_delta_e`
- odbx: `_odbx_formation_energy`
- Materials Project: `_mp_stability` (GGA/GGA+U)