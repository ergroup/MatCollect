"""Cross-database energy calibration via structure-matched compounds.

This module implements per-element offset fitting to harmonize formation
energies from heterogeneous DFT databases onto a single reference scale,
enabling unified convex hull and Pourbaix diagram construction.

Scientific basis:
    Each database D computes formation energy as
        ΔE_f^D = E_DFT^D(compound) - Σ x_i · E_ref^D(element_i)
    Different databases use different E_ref, producing systematic offsets.
    By identifying the same compound in two databases (via StructureMatcher),
    we fit per-element offsets δ_i such that
        ΔE_f^D1 - ΔE_f^D2 ≈ Σ x_i · δ_i
    and apply the correction to all D2 materials.

Uncertainty:
    The least-squares fit also yields a covariance matrix
        cov(δ) = σ² (AᵀA)⁻¹,  σ² = RSS / (n_matches - rank)
    from which per-element standard errors and 95% confidence intervals are
    derived. Because the per-compound correction is a composition-weighted sum
    Σ x_i·δ_i, its variance is xᵀ·cov(δ)·x — the off-diagonal covariance terms
    matter, so the full matrix is retained rather than only the diagonal.

    These are sampling errors under an iid-Gaussian residual assumption. They
    describe the internal consistency of the matched set, not the absolute
    accuracy of the offsets: DFT errors are correlated across chemically similar
    compounds, so a small standard error does not by itself imply a small bias.
    The reported rank and condition number are often more diagnostic than the
    standard errors alone.

References:
    - Hegde et al., Phys. Rev. Materials 7, 053805 (2023)
    - Stevanovic et al., Phys. Rev. B 85, 115104 (2012)
    - Kingsbury, Rosen et al., npj Comput. Mater. 8, 195 (2022)
"""

import logging

import numpy as np
from pymatgen.analysis.structure_matcher import StructureMatcher
from scipy import stats

from matcollect.core.utils.pymatgen_helper import convert_to_structure

logger = logging.getLogger(__name__)

# RMSE thresholds (eV/atom) for flagging calibration quality.
# Fits above UNRELIABLE are flagged as potentially unreliable; those between
# CAUTION and UNRELIABLE approach the intrinsic uncertainty of GGA-level DFT
# (Kingsbury, Rosen et al., npj Comput. Mater. 8, 195 (2022)).
RMSE_UNRELIABLE_EV = 0.100
RMSE_CAUTION_EV = 0.025

# Condition number above which fitted offsets are considered strongly correlated.
CONDITION_NUMBER_WARN = 100.0


class EnergyCalibrator:
    """Calibrate formation energies across databases using structure-matched pairs.

    Parameters
    ----------
    materials_dict : dict
        Nested dictionary: {chemsys: {database: {material_id: {normalized_attributes: {...}}}}}
    reference_database : str
        The database to use as the energy reference (e.g., "materialsproject").
        All other databases will be corrected to this reference.
    tolerances : dict, optional
        StructureMatcher tolerances for identifying matched compounds.
        Defaults to tight tolerances: ltol=0.1, stol=0.15, angle_tol=3.

    Attributes
    ----------
    element_offsets : dict
        Fitted per-element offsets {(database, element): offset_eV_per_atom}.
    element_offset_stderr : dict
        Standard errors on the fitted offsets
        {(database, element): stderr_eV_per_atom}.
    calibration_report : dict
        Per-database fit statistics: offsets with uncertainties, RMSE, number of
        matched pairs, per-compound residuals.
    """

    def __init__(self,
                 materials_dict: dict,
                 reference_database: str,
                 tolerances: dict | None = None):
        """
        Initialize an EnergyCalibrator object.

        Parameters
        ----------
        materials_dict : dict
            A nested dictionary containing materials organized by chemical system,
            database, and material ID.
        reference_database : str
            The database to use as the energy reference (e.g., "materialsproject").
            All other databases will be corrected to this reference.
        tolerances : dict, optional
            StructureMatcher tolerances for identifying matched compounds.
            Defaults to tight tolerances: ltol=0.1, stol=0.15, angle_tol=3.

        Attributes
        ----------
        element_offsets : dict
            Fitted per-element offsets {(database, element): offset_eV_per_atom}.
        element_offset_stderr : dict
            Standard errors on the fitted offsets
            {(database, element): stderr_eV_per_atom}.
        calibration_report : dict
            Per-database fit statistics: offsets with uncertainties, RMSE, number
            of matched pairs, per-compound residuals.
        """
        self.materials_dict = materials_dict
        self.reference_database = reference_database
        self.tolerances = tolerances or {"ltol": 0.1, "stol": 0.15, "angle_tol": 3}

        self.element_offsets = {}
        self.element_offset_stderr = {}
        self.calibration_report = {}

        # {database: (element_order, covariance_matrix)} for error propagation
        self._covariances = {}

        self._matcher = StructureMatcher(**self.tolerances)

    def calibrate(self) -> dict:  # noqa: C901
        """Run the full calibration pipeline.

        Returns
        -------
        dict
            The materials_dict with corrected formation energies for
            all non-reference databases.
        """
        # Collect all databases present in the data
        all_databases = set()
        for chemsys_dict in self.materials_dict.values():
            all_databases.update(chemsys_dict.keys())

        if self.reference_database not in all_databases:
            logger.warning(
                f"Reference database '{self.reference_database}' not found in materials. "  # noqa: G004
                f"Available: {all_databases}. Skipping calibration."
            )
            return self.materials_dict

        non_ref_databases = all_databases - {self.reference_database}
        if not non_ref_databases:
            logger.info("Only one database present. No calibration needed.")
            return self.materials_dict

        # Stamp reference materials with identity corrections for consistent keys
        for chemsys_dict in self.materials_dict.values():
            if self.reference_database not in chemsys_dict:
                continue
            for material in chemsys_dict[self.reference_database].values():
                attrs = material["normalized_attributes"]
                ef = attrs.get("formation_energy_per_atom")
                if ef is None:
                    continue
                attrs["formation_energy_per_atom_uncorrected"] = ef
                attrs["calibration_correction"] = 0.0
                attrs["calibration_correction_stderr"] = 0.0
                attrs["calibration_reference"] = self.reference_database

        # For each non-reference database, find matches and fit offsets
        for other_db in sorted(non_ref_databases):
            matched_pairs = self._find_matched_pairs(self.reference_database, other_db)

            if not matched_pairs:
                logger.warning(
                    f"No matched compounds between '{self.reference_database}' "  # noqa: G004
                    f"and '{other_db}'. Cannot calibrate — skipping this database."
                )
                self.calibration_report[other_db] = {
                    "status": "failed",
                    "reason": "no matched compounds",
                    "n_matches": 0
                }
                continue

            offsets, report = self._fit_offsets(matched_pairs, other_db)

            if offsets is None:
                logger.warning(
                    f"Could not fit offsets for '{other_db}': {report['reason']}"  # noqa: G004
                )
                self.calibration_report[other_db] = report
                continue

            # Store offsets
            for element, offset in offsets.items():
                self.element_offsets[(other_db, element)] = offset

            self.calibration_report[other_db] = report

            # Apply corrections
            self._apply_corrections(other_db, offsets)

        return self.materials_dict

    def _find_matched_pairs(self, ref_db: str, other_db: str) -> list[dict]:  # noqa: C901
        """Find structurally identical compounds across two databases.

        Parameters
        ----------
        ref_db : str
            Reference database name.
        other_db : str
            Database to be calibrated.

        Returns
        -------
        list[dict]
            List of matched pairs with formation energies and compositions.
        """
        matched_pairs = []
        seen_pairs = set()

        for chemsys_dict in self.materials_dict.values():
            if ref_db not in chemsys_dict or other_db not in chemsys_dict:
                continue

            ref_materials = chemsys_dict[ref_db]
            other_materials = chemsys_dict[other_db]

            for ref_id, ref_mat in ref_materials.items():
                ref_attrs = ref_mat["normalized_attributes"]
                ref_ef = ref_attrs.get("formation_energy_per_atom")
                ref_formula = ref_attrs.get("reduced_formula")

                if ref_ef is None or ref_attrs.get("lattice_vectors") is None:
                    continue

                try:
                    ref_struct = convert_to_structure(ref_attrs)
                except (TypeError, KeyError, ValueError):
                    continue

                for other_id, other_mat in other_materials.items():
                    other_attrs = other_mat["normalized_attributes"]
                    other_ef = other_attrs.get("formation_energy_per_atom")
                    other_formula = other_attrs.get("reduced_formula")

                    if other_ef is None or other_attrs.get("lattice_vectors") is None:
                        continue

                    # Fast filter: same reduced formula
                    if ref_formula != other_formula:
                        continue

                    # Skip already-matched pairs
                    pair_key = (ref_id, other_id)
                    if pair_key in seen_pairs:
                        continue

                    try:
                        other_struct = convert_to_structure(other_attrs)
                    except (TypeError, KeyError, ValueError):
                        continue

                    try:
                        if self._matcher.fit(ref_struct, other_struct):
                            seen_pairs.add(pair_key)
                            comp = ref_attrs["composition"]
                            n_total = sum(comp.values())
                            fractions = {el: amt / n_total for el, amt in comp.items()}

                            matched_pairs.append({
                                "ref_id": ref_id,
                                "other_id": other_id,
                                "formula": ref_formula,
                                "ref_ef": ref_ef,
                                "other_ef": other_ef,
                                "delta": ref_ef - other_ef,
                                "fractions": fractions
                            })
                    except Exception:  # noqa: S112
                        continue
        return matched_pairs

    def _fit_offsets(self, matched_pairs: list[dict], other_db: str  # noqa: C901
                     ) -> tuple[dict | None, dict]:
        """Fit per-element offsets from matched pairs via least squares.

        Also estimates the covariance of the fitted offsets, from which
        per-element standard errors and 95% confidence intervals are derived.

        Parameters
        ----------
        matched_pairs : list[dict]
            Matched compounds with formation energies and compositions.
        other_db : str
            Name of the database being calibrated.

        Returns
        -------
        tuple[dict | None, dict]
            (offsets dict, report dict). offsets is None if fitting failed.
        """
        # Collect unique elements
        elements = sorted({
            el for pair in matched_pairs for el in pair["fractions"]
        })
        n_elements = len(elements)
        n_matches = len(matched_pairs)

        if n_matches < n_elements:
            return None, {
                "status": "failed",
                "reason": f"underdetermined: {n_matches} matches < {n_elements} elements",
                "n_matches": n_matches,
                "n_elements": n_elements
            }

        # Build linear system: A·δ = b
        A = np.zeros((n_matches, n_elements))  # noqa: N806
        b = np.zeros(n_matches)

        for i, pair in enumerate(matched_pairs):
            b[i] = pair["delta"]
            for j, el in enumerate(elements):
                A[i, j] = pair["fractions"].get(el, 0.0)

        # Least squares solve
        delta, _, rank, svals = np.linalg.lstsq(A, b, rcond=None)
        rank = int(rank)
        residuals = b - A @ delta
        rss = float(residuals @ residuals)
        rmse = float(np.sqrt(rss / n_matches))
        max_residual = float(np.max(np.abs(residuals)))

        # Uncertainty on the fitted offsets:
        #   cov(δ) = σ² (AᵀA)⁻¹  with  σ² = RSS / (n_matches - rank)
        # pinv is used so that rank-deficient systems still return a matrix
        # (the corresponding variances are then meaningless — see rank warning).
        dof = n_matches - rank
        if dof > 0:
            sigma2 = rss / dof
            cov = sigma2 * np.linalg.pinv(A.T @ A)
            std_errors = np.sqrt(np.clip(np.diag(cov), 0.0, None))
            t_crit = float(stats.t.ppf(0.975, dof))
            residual_std = float(np.sqrt(sigma2))
        else:
            cov = np.full((n_elements, n_elements), np.nan)
            std_errors = np.full(n_elements, np.nan)
            t_crit = float("nan")
            residual_std = float("nan")

        # Condition number of the design matrix: high values mean the matched
        # pairs span a narrow range of stoichiometries.
        cond = float(svals[0] / svals[-1]) if svals.size and svals[-1] > 0 else float("inf")

        offsets = {el: float(delta[j]) for j, el in enumerate(elements)}
        stderr = {el: float(std_errors[j]) for j, el in enumerate(elements)}

        # Retain covariance for per-compound error propagation
        self._covariances[other_db] = (elements, cov)
        for el, se in stderr.items():
            self.element_offset_stderr[(other_db, el)] = se

        report = {
            "status": "success",
            "database": other_db,
            "reference": self.reference_database,
            "n_matches": n_matches,
            "n_elements": n_elements,
            "elements": elements,
            "offsets_meV": {el: round(v * 1000, 1) for el, v in offsets.items()},
            "offset_stderr_meV": {
                el: round(v * 1000, 1) for el, v in stderr.items()
            },
            "offset_ci95_meV": {
                el: [
                    round((offsets[el] - t_crit * stderr[el]) * 1000, 1),
                    round((offsets[el] + t_crit * stderr[el]) * 1000, 1)
                ]
                for el in elements
            },
            "covariance_meV2": (cov * 1e6).round(1).tolist(),
            "dof": dof,
            "rank": rank,
            "condition_number": round(cond, 1) if np.isfinite(cond) else None,
            "rmse_meV": round(rmse * 1000, 1),
            "residual_std_meV": (
                round(residual_std * 1000, 1) if np.isfinite(residual_std) else None
            ),
            "max_residual_meV": round(max_residual * 1000, 1),
            "warnings": [],
            "matched_pairs": [
                {
                    "formula": p["formula"],
                    "ref_id": p["ref_id"],
                    "other_id": p["other_id"],
                    "ref_ef": round(p["ref_ef"], 4),
                    "other_ef": round(p["other_ef"], 4),
                    "delta_meV": round(p["delta"] * 1000, 1),
                    "residual_meV": round(float(residuals[i]) * 1000, 1)
                }
                for i, p in enumerate(matched_pairs)
            ]
        }

        # Quality warnings — RMSE
        if rmse > RMSE_UNRELIABLE_EV:
            report["warnings"].append(
                f"RMSE = {rmse*1000:.0f} meV/atom exceeds the "
                f"{RMSE_UNRELIABLE_EV*1000:.0f} meV/atom threshold. Calibration is "
                "potentially unreliable for this database pair."
            )
        elif rmse > RMSE_CAUTION_EV:
            report["warnings"].append(
                f"RMSE = {rmse*1000:.0f} meV/atom. Treat with caution: this range "
                "approaches the intrinsic uncertainty of GGA-level DFT."
            )

        # Quality warnings — conditioning of the fit
        if rank < n_elements:
            report["warnings"].append(
                f"Rank-deficient fit: rank {rank} < {n_elements} elements. "
                "Individual offsets are not identifiable — only certain linear "
                "combinations are constrained. The minimum-norm solution is "
                "returned; per-element values are arbitrary within the null space "
                "and their standard errors are not meaningful."
            )
        elif cond > CONDITION_NUMBER_WARN:
            report["warnings"].append(
                f"Condition number = {cond:.0f}: the matched pairs span a narrow "
                "range of stoichiometries, so the fitted offsets are strongly "
                "correlated and individually poorly constrained."
            )

        if dof <= 0:
            report["warnings"].append(
                f"Zero degrees of freedom ({n_matches} matches, rank {rank}): the "
                "fit is exactly determined, so no uncertainty can be estimated."
            )

        logger.info(
            f"Calibration {self.reference_database} ↔ {other_db}: "  # noqa: G004
            f"{n_matches} matches, RMSE = {rmse*1000:.1f} meV/atom, "
            f"offsets = {report['offsets_meV']} "
            f"± {report['offset_stderr_meV']} meV/atom"
        )
        for msg in report["warnings"]:
            logger.warning(f"Calibration {other_db}: {msg}")  # noqa: G004

        return offsets, report

    def _apply_corrections(self, database: str, offsets: dict) -> None:
        """Apply per-element corrections to all materials in the given database.

        Modifies the materials_dict in place: stores the uncorrected energy,
        updates 'formation_energy_per_atom' with the corrected value, and
        records the correction together with its propagated standard error.

        The correction for a compound of composition fractions x is Σ x_i·δ_i,
        so its variance is xᵀ·cov(δ)·x, including off-diagonal covariance terms.

        Parameters
        ----------
        database : str
            The database whose materials will be corrected.
        offsets : dict
            Per-element offsets {element: offset_eV_per_atom}.
        """
        elements, cov = self._covariances.get(database, (None, None))

        for chemsys_dict in self.materials_dict.values():
            if database not in chemsys_dict:
                continue
            for material in chemsys_dict[database].values():
                attrs = material["normalized_attributes"]
                ef = attrs.get("formation_energy_per_atom")
                comp = attrs.get("composition")

                if ef is None or comp is None:
                    continue

                n_total = sum(comp.values())
                correction = sum(
                    (amt / n_total) * offsets.get(el, 0.0)
                    for el, amt in comp.items()
                )

                # Store original and corrected values
                attrs["formation_energy_per_atom_uncorrected"] = ef
                attrs["formation_energy_per_atom"] = ef + correction
                attrs["calibration_correction"] = correction
                attrs["calibration_reference"] = self.reference_database

                # Propagate offset uncertainty to this compound
                if cov is not None:
                    x = np.array([
                        comp.get(el, 0.0) / n_total for el in elements
                    ])
                    variance = float(x @ cov @ x)
                    attrs["calibration_correction_stderr"] = (
                        float(np.sqrt(variance)) if np.isfinite(variance)
                        and variance > 0 else (
                            0.0 if np.isfinite(variance) else float("nan")
                        )
                    )

    def get_report_summary(self) -> str:
        """Return a human-readable summary of the calibration results.

        Returns
        -------
        str
            Multi-line summary string.
        """
        lines = [f"Cross-database calibration (reference: {self.reference_database})"]
        lines.append("=" * 60)

        for db, report in self.calibration_report.items():
            lines.append(f"\n{db}:")
            if report["status"] == "failed":
                lines.append(f"  FAILED: {report['reason']}")
                continue

            lines.append(f"  Matched compounds: {report['n_matches']}")
            lines.append(f"  Elements fitted:   {', '.join(report['elements'])}")
            lines.append(
                f"  Rank / DOF:        {report['rank']} / {report['dof']}"
            )
            if report["condition_number"] is not None:
                lines.append(f"  Condition number:  {report['condition_number']}")
            lines.append(f"  RMSE:              {report['rmse_meV']} meV/atom")
            if report["residual_std_meV"] is not None:
                lines.append(
                    f"  Residual std:      {report['residual_std_meV']} meV/atom "
                    "(used for error bars)"
                )
            lines.append(f"  Max residual:      {report['max_residual_meV']} meV/atom")

            lines.append("  Offsets (meV/atom, ±1σ, 95% CI):")
            for el in report["elements"]:
                lo, hi = report["offset_ci95_meV"][el]
                lines.append(
                    f"    {el:3s}  {report['offsets_meV'][el]:+9.1f}"
                    f"  ± {report['offset_stderr_meV'][el]:7.1f}"
                    f"   [{lo:+.1f}, {hi:+.1f}]"
                )

            for msg in report.get("warnings", []):
                lines.append(f"  WARNING: {msg}")

            lines.append("  Matched pairs:")
            for p in report["matched_pairs"]:
                lines.append(  # noqa: PERF401
                    f"    {p['formula']:8s}  ref={p['ref_ef']:+.4f}  "
                    f"other={p['other_ef']:+.4f}  Δ={p['delta_meV']:+.1f}  "
                    f"residual={p['residual_meV']:+.1f} meV"
                )

        return "\n".join(lines)
