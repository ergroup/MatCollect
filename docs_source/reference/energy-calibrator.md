# EnergyCalibrator

`matcollect.core.stability_analysis.energy_calibrator.EnergyCalibrator`

Harmonises formation energies from different databases onto a single reference scale by fitting per-element offsets from structurally matched compounds. This enables convex hull and Pourbaix construction across data from heterogeneous DFT sources.

## Constructor

```python
EnergyCalibrator(
    materials_dict,
    reference_database,
    tolerances=None
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `materials_dict` | `dict` | required | Nested dictionary of materials keyed by chemical system, then database, then material ID |
| `reference_database` | `str` | required | Database to treat as the energy reference, e.g. `"materialsproject"`. All other databases are corrected to this scale |
| `tolerances` | `dict \| None` | `None` | `StructureMatcher` tolerances for identifying matched compounds. Defaults to `{"ltol": 0.1, "stol": 0.15, "angle_tol": 3}` |

The default tolerances are tighter than those used for duplicate removal, since calibration requires confident structural identity between the same compound in two databases.

## Attributes

| Attribute | Type | Description |
|---|---|---|
| `materials_dict` | `dict` | Input materials dictionary, modified in place during calibration |
| `reference_database` | `str` | The reference database name |
| `tolerances` | `dict` | Active `StructureMatcher` tolerances |
| `element_offsets` | `dict` | Fitted offsets keyed by `(database, element)`, in eV/atom. Populated after `calibrate()` |
| `element_offset_stderr` | `dict` | Standard errors on those offsets, same keys, in eV/atom. Populated after `calibrate()` |
| `calibration_report` | `dict` | Per-database fit statistics. Populated after `calibrate()` |

## Methods

### `calibrate`

```python
calibrate() -> dict
```

Runs the full calibration pipeline:

1. Identifies all databases present in the data.
2. For each non-reference database, finds compounds that structurally match a compound in the reference database.
3. Fits per-element offsets by least squares so that the formation energy difference between matched pairs is explained by a sum of per-element corrections. The fit also yields a covariance matrix for the offsets.
4. Applies the fitted offsets to every material in that database, together with a propagated uncertainty on each correction.

Returns the `materials_dict` with corrected formation energies. The dictionary is also modified in place.

If the reference database is absent, or only one database is present, calibration is skipped and the dictionary is returned unchanged. A database with no matched compounds, or with fewer matches than elements to fit, is skipped and recorded as failed in the report.

---

### `get_report_summary`

```python
get_report_summary() -> str
```

Returns a human-readable multi-line summary of the calibration results: matched compound counts, fitted offsets with their standard errors and 95% confidence intervals, rank and degrees of freedom, condition number, RMSE and residual spread, and per-pair residuals for each database.

## Output

After calibration, materials in non-reference databases gain the following fields in their `normalized_attributes`:

| Field | Description |
|---|---|
| `formation_energy_per_atom` | Corrected formation energy per atom (eV/atom) |
| `formation_energy_per_atom_uncorrected` | Original value before correction |
| `calibration_correction` | Applied correction (eV/atom) |
| `calibration_correction_stderr` | 1σ uncertainty on that correction (eV/atom), propagated from the offset covariance. `NaN` when the fit had no degrees of freedom |
| `calibration_reference` | Name of the reference database |

Reference-database materials are stamped with the same fields, with a correction and standard error of `0.0`, so all entries carry a consistent set of keys.

## Calibration report

The `calibration_report` maps each non-reference database to a dictionary of fit statistics. A successful entry includes:

| Key | Description |
|---|---|
| `status` | `"success"` or `"failed"` |
| `database`, `reference` | Database being calibrated, and the reference it was calibrated against |
| `n_matches`, `n_elements` | Number of matched compound pairs, and number of elements fitted |
| `elements` | Elements for which an offset was fitted |
| `offsets_meV` | Per-element offsets in meV/atom |
| `offset_stderr_meV` | Standard error on each offset in meV/atom |
| `offset_ci95_meV` | 95% confidence interval `[lo, hi]` per element, in meV/atom |
| `covariance_meV2` | Full offset covariance matrix, ordered as `elements`, in meV²/atom² |
| `rank`, `dof` | Rank of the design matrix, and residual degrees of freedom |
| `condition_number` | Conditioning of the design matrix; `None` if not finite |
| `rmse_meV` | Root-mean-square error of the fit in meV/atom |
| `residual_std_meV` | Residual standard deviation used for the error bars; `None` when `dof` is zero |
| `max_residual_meV` | Largest single-pair residual in meV/atom |
| `warnings` | List of quality warnings raised for this fit (empty if none) |
| `matched_pairs` | Per-pair detail: formula, IDs, formation energies, delta, and residual |

A failed entry instead carries a `reason`, such as no matched compounds or an underdetermined system.

### Quality warnings

The fit RMSE is compared against DFT-level uncertainty:

| RMSE | Interpretation |
|---|---|
| > 100 meV/atom | Calibration may be unreliable for this database pair |
| 25-100 meV/atom | Treat with caution; approaches the intrinsic uncertainty of GGA-level DFT |
| < 25 meV/atom | Within DFT uncertainty, no warning |

Three further warnings describe the conditioning of the fit:

- **Rank-deficient** (`rank < n_elements`) — individual offsets are not identifiable, only certain linear combinations. The minimum-norm solution is returned; per-element values are arbitrary within the null space and their standard errors are not meaningful.
- **Condition number > 100** — the matched pairs span a narrow range of stoichiometries, so the offsets are strongly correlated and individually poorly constrained.
- **Zero degrees of freedom** — the fit is exactly determined and no uncertainty can be estimated.

## Scientific basis

Each database computes formation energy relative to its own elemental reference states, which differ between DFT settings and produce systematic offsets. By identifying the same compound in two databases and fitting per-element offsets δ such that the formation energy difference equals the composition-weighted sum of offsets, all materials can be placed on a common scale.

References:

- Hegde et al., *Phys. Rev. Materials* **7**, 053805 (2023)
- Stevanovic et al., *Phys. Rev. B* **85**, 115104 (2012)
- Kingsbury, Rosen et al., *npj Comput. Mater.* **8**, 195 (2022)