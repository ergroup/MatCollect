"""Deduplication benchmarking for the MatCollect paper."""  # noqa: INP001

from __future__ import annotations

import inspect
import itertools
import json
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Lattice, Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.symmetry.groups import SpaceGroup

from matcollect.core.duplicate_removal.duplicate_remover import DuplicateRemover
from matcollect.core.duplicate_removal.workers import check_pair_worker, worker_init

DATA = Path(__file__).resolve().parent / "data" / "duplicate_analysis_materials.json"

# --- configuration ---------------------------------------------------------

# Where the ground-truth space group comes from:
#   "recomputed"  SpacegroupAnalyzer at SYMPREC, applied uniformly to every
#                 entry. Required, because the source databases apply
#                 different symmetry tolerances -- see space_group_provenance().
#   "normalized"  normalized_attributes["space_group_number"]
#   "native"      source_attributes, as reported by the source database
SG_SOURCE = "recomputed"

# Symmetry tolerance for the ground-truth assignment. pymatgen's own guidance:
# the 0.01 default suits properly refined structures with atoms on exact
# symmetry coordinates, while "for structures with slight deviations from their
# proper atomic positions (e.g. structures relaxed with electronic structure
# codes), a looser tolerance of 0.1 (the value used in Materials Project) is
# often needed". Every entry here is DFT-relaxed, so 0.1 is the applicable
# value; symprec_sensitivity() reports the effect of this choice.
SYMPREC = 0.1

# Optional guard: reassign a Pnnm label to rutile below this in-plane
# anisotropy, on the grounds that the distortion is numerical residue of the
# relaxation rather than a distinct phase. Not needed at SYMPREC = 0.1, where
# no CaCl2-type entry falls below 0.2% -- set to a percentage to enable.
ANISO_THRESHOLD: float | None = None  # percent, 2|a-b|/(a+b)

# Native space-group field per database key, inside source_attributes.
# Alexandria reports an integer, OQMD a Hermann-Mauguin symbol; MP exposes
# neither, so in "native" mode MP entries follow NATIVE_FALLBACK.
NATIVE_KEYS = {"alexa": "_alexandria_space_group",
               "oqmd": "_oqmd_spacegroup"}
NATIVE_FALLBACK = "recompute"  # "recompute" | "drop"

# Rejects 2D/slab entries returned by the retrieval, which otherwise share a
# space-group label with bulk phases while being physically distinct.
MAX_VACUUM = 5.0  # Å

BASE = dict(inspect.signature(DuplicateRemover).parameters["tolerances"].default)

# Short database key (from the OPTIMADE base URL) -> display name.
DB_NAME = {"alexa": "Alexandria", "optim": "MP", "oqmd": "OQMD"}
DB_ORDER = ("alexa", "optim", "oqmd")

# Well-defined MO2 prototypes (space-group number -> label). For these space
# groups, composition + space group fixes the prototype. The assignment is
# algorithmically independent of the pairwise matcher under test, though
# symmetry assignment is itself tolerance-based -- see symprec_sensitivity().
PROTO = {136: "rutile", 141: "anatase", 205: "pyrite", 225: "fluorite",
         58: "CaCl2-type"}
RUTILE_SG = 136

FORMULAS = ("IrO2", "RuO2", "TiO2")

# Group-subgroup pair connected by a continuous second-order displacive
# transition. Reported separately in the summary: near the boundary the space
# group does not identify a distinct phase.
SOFT_PAIR = frozenset({"rutile", "CaCl2-type"})


# --- helpers ---------------------------------------------------------------

def db_short(url: str) -> str:
    """First token of the OPTIMADE base URL host (dataset-specific helper)."""
    return url.split("//")[1].split(".")[0][:5]


def max_vacuum_gap(s: Structure) -> float:
    """Largest empty slab (Å) along any lattice direction."""
    out = []
    for i in range(3):
        fr = np.sort(s.frac_coords[:, i] % 1.0)
        gaps = np.diff(np.append(fr, fr[0] + 1.0))
        out.append(gaps.max() * s.lattice.abc[i])
    return max(out)


def vol_per_atom(s: Structure) -> float:
    """Atomic volume (Å^3/atom)."""
    return s.volume / len(s)


def ab_anisotropy(s: Structure) -> float:
    """Deviation from tetragonality, 2|a-b|/(a+b) in percent, from the raw cell.

    In both rutile (P4_2/mnm) and the CaCl2-type distortion (Pnnm) the two
    longest lattice parameters are the pair that is equal by symmetry in the
    tetragonal parent, so their relative difference measures the orthorhombic
    distortion. Measured on the structure as retrieved: any symmetrisation step
    would average away the quantity under test. Only meaningful for the
    rutile/CaCl2-type family.
    """
    a, b = sorted(s.lattice.abc)[-2:]
    return 200.0 * abs(a - b) / (a + b)


# --- Hermann-Mauguin symbol -> space-group number ---------------------------

def _squash(sym: str) -> str:
    """'P 4_2/m n m' -> 'p42/mnm'. Setting-insensitive lookup key."""
    return re.sub(r"[\s_]", "", str(sym)).lower()


@lru_cache(maxsize=1)
def _symbol_lookup() -> dict[str, int]:
    """Squashed short and full HM symbols -> international number."""
    out: dict[str, int] = {}
    for n in range(1, 231):
        sg = SpaceGroup.from_int_number(n)
        for s in (sg.symbol, sg.full_symbol):
            out.setdefault(_squash(s), n)
    return out


def sg_number_from_symbol(value) -> int | None:
    """Space-group number from an int, a numeric string, or an HM symbol.

    Returns None rather than raising: unconvertible labels are counted and
    reported instead of being silently dropped.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 230 else None
    s = str(value).strip()
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 230 else None
    n = _symbol_lookup().get(_squash(s))
    if n is not None:
        return n
    try:  # non-standard settings pymatgen still recognises
        return SpaceGroup(s).int_number
    except Exception:  # noqa: BLE001
        return None


def native_space_group(entry: dict, db: str) -> int | None:
    """Space group as reported by the source database, or None."""
    key = NATIVE_KEYS.get(db)
    if key is None:
        return None
    src = entry.get("source_attributes") or {}
    if key in src:
        return sg_number_from_symbol(src[key])
    for k, v in src.items():  # tolerate a differently nested payload
        if k.lower().endswith(key.lstrip("_")):
            return sg_number_from_symbol(v)
    return None


# --- data loading ----------------------------------------------------------

def load_oxides(symprec: float = SYMPREC,
                source: str = SG_SOURCE,
                aniso_threshold: float | None = ANISO_THRESHOLD,
                verbose: bool = True) -> dict:
    """MO2 structures grouped by (formula, space group), tagged by database."""
    data = json.loads(DATA.read_text())
    groups = defaultdict(list)
    n_slab = n_bad = n_nolabel = n_fallback = 0
    relabelled: list[str] = []
    for _cs, csd in data.items():
        for url, dbd in csd.items():
            db = db_short(url)
            assert db in DB_NAME, f"unknown provider host: {url!r} -> {db!r}"
            for mid, entry in dbd.items():
                a = entry["normalized_attributes"]
                f = a.get("reduced_formula")
                if f not in FORMULAS or not a.get("lattice_vectors"):
                    continue
                try:
                    s = Structure(a["lattice_vectors"], a["species_at_sites"],
                                  a["cartesian_site_positions"],
                                  coords_are_cartesian=True)
                    if max_vacuum_gap(s) > MAX_VACUUM:
                        n_slab += 1
                        continue
                    if source == "recomputed":
                        sg = SpacegroupAnalyzer(s, symprec=symprec).get_space_group_number()
                    elif source == "normalized":
                        sg = a.get("space_group_number")
                    elif source == "native":
                        sg = native_space_group(entry, db)
                        if sg is None:
                            if NATIVE_FALLBACK == "drop":
                                n_nolabel += 1
                                continue
                            n_fallback += 1
                            sg = SpacegroupAnalyzer(
                                s, symprec=symprec).get_space_group_number()
                    else:
                        raise ValueError(f"unknown SG_SOURCE {source!r}")
                except Exception:  # noqa: BLE001
                    n_bad += 1
                    continue
                if sg is None:
                    n_nolabel += 1
                    continue
                if aniso_threshold is not None and PROTO.get(sg) == "CaCl2-type":
                    aniso = ab_anisotropy(s)
                    if aniso < aniso_threshold:
                        sg = RUTILE_SG
                        relabelled.append(f"{f} {DB_NAME[db]}/{mid} ({aniso:.3f}%)")
                groups[(f, sg)].append((db, s))
    if verbose:
        src = (f"recomputed, symprec={symprec}" if source == "recomputed"
               else source)
        extra = f", {n_fallback} recomputed fallback" if n_fallback else ""
        print(f"[load] space groups {src}  rejected: {n_slab} slab/2D, "
              f"{n_bad} unparseable, {n_nolabel} no label{extra}")
        if aniso_threshold is not None:
            print(f"[load] Pnnm -> rutile below {aniso_threshold}% anisotropy: "
                  f"{len(relabelled)} entries")
            for r in relabelled:
                print(f"         {r}")
    return groups


def db_counts(lst: list) -> dict:
    """Instances per database, in fixed display order."""
    counts = dict.fromkeys(DB_ORDER, 0)
    for d, _ in lst:
        counts[d] += 1
    return counts


def db_label(counts: dict) -> str:
    """'Alexandria, MP, OQMD' -- databases contributing at least one instance."""
    return ", ".join(DB_NAME[d] for d in DB_ORDER if counts[d])


def n_cross_pairs(counts: dict) -> int:
    """Cross-database pair count: (n^2 - sum_i n_i^2) / 2."""
    n = sum(counts.values())
    return (n**2 - sum(c**2 for c in counts.values())) // 2


def canonical_tio2() -> dict:
    """TiO2 polymorphs from the crystallography literature.

    Fully external ground truth: experimental structures, prototype names
    assigned by crystallographers, no symmetry-analysis step in the chain.

    Lattice parameters and Wyckoff positions:
      rutile, anatase -- Howard, Sabine & Dickson, Acta Cryst. B47, 462 (1991).
      brookite        -- Meagher & Lager, Can. Mineral. 17, 77 (1979).
    """
    rutile = Structure.from_spacegroup(
        136, Lattice.tetragonal(4.5937, 2.9587),
        ["Ti", "O"], [[0, 0, 0], [0.3053, 0.3053, 0]])
    anatase = Structure.from_spacegroup(
        141, Lattice.tetragonal(3.7842, 9.5146),
        ["Ti", "O"], [[0, 0, 0], [0, 0, 0.2081]])
    brookite = Structure.from_spacegroup(
        61, Lattice.orthorhombic(9.174, 5.449, 5.138),
        ["Ti", "O", "O"],
        [[0.1290, 0.0972, 0.8628], [0.0095, 0.1491, 0.1835],
         [0.2314, 0.1110, 0.5359]])
    return {"rutile": rutile, "anatase": anatase, "brookite": brookite}


# --- evaluation ------------------------------------------------------------

def evaluate(groups: dict, mc_fit, sm: StructureMatcher) -> dict:
    """Full positive/negative evaluation of one reference set."""
    rows, n_pos_pairs, n_pos_merged = [], 0, 0

    # positives: same prototype, different database
    for (f, sg), lst in sorted(groups.items()):
        if sg not in PROTO:
            continue
        counts = db_counts(lst)
        vols = [vol_per_atom(s) for _, s in lst]
        vspread = (max(vols) - min(vols)) / np.mean(vols) * 100

        rms, dvol = [], []
        for (d1, s1), (d2, s2) in itertools.combinations(lst, 2):
            if d1 == d2:
                continue
            n_pos_pairs += 1
            merged = mc_fit(s1, s2)
            if merged != sm.fit(s1, s2):
                raise AssertionError("check_pair_worker disagrees with StructureMatcher")
            if not merged:
                continue
            n_pos_merged += 1
            r = sm.get_rms_dist(s1, s2)
            if r:
                rms.append(r[0])
            # Absolute atomic-volume difference, Å^3/atom.
            dvol.append(abs(vol_per_atom(s1) - vol_per_atom(s2)))

        stats = None if not rms else (float(np.mean(rms)), float(np.mean(dvol)))
        rows.append({"formula": f, "proto": PROTO[sg], "n": len(lst),
                     "dbs": db_label(counts),
                     "n_dbs": sum(c > 0 for c in counts.values()),
                     "pairs": n_cross_pairs(counts), "stats": stats,
                     "vspread": vspread})

    assert n_pos_pairs == sum(r["pairs"] for r in rows), (
        "duplicate-pair total is not reconstructible from the tabulated counts")

    # negatives: distinct prototypes, same composition
    n_neg = n_neg_merged = n_combos = n_soft_pairs = 0
    false_merges: dict[str, int] = defaultdict(int)
    for f in FORMULAS:
        by_sg = {sg: [s for _, s in lst] for (ff, sg), lst in groups.items()
                 if ff == f and sg in PROTO}
        for sg1, sg2 in itertools.combinations(sorted(by_sg), 2):
            n_combos += 1
            soft = frozenset({PROTO[sg1], PROTO[sg2]}) == SOFT_PAIR
            for s1, s2 in itertools.product(by_sg[sg1], by_sg[sg2]):
                n_neg += 1
                n_soft_pairs += int(soft)
                merged = mc_fit(s1, s2)
                if merged != sm.fit(s1, s2):
                    raise AssertionError("check_pair_worker disagrees with StructureMatcher")
                if merged:
                    n_neg_merged += 1
                    false_merges[f"{f}: {PROTO[sg1]}<->{PROTO[sg2]}"] += 1

    expected = 0
    for f in FORMULAS:
        ns = [len(lst) for (ff, sg), lst in groups.items()
              if ff == f and sg in PROTO]
        expected += sum(a * b for a, b in itertools.combinations(ns, 2))
    assert n_neg == expected, (
        f"distinct-pair total {n_neg} != {expected} from tabulated n")

    # False merges attributable to the rutile/CaCl2-type group-subgroup pair.
    n_soft_merged = sum(v for k, v in false_merges.items()
                        if frozenset(k.split(": ")[1].split("<->")) == SOFT_PAIR)

    return {"rows": rows, "n_pos_pairs": n_pos_pairs, "n_pos_merged": n_pos_merged,
            "n_neg": n_neg, "n_neg_merged": n_neg_merged, "n_combos": n_combos,
            "false_merges": dict(false_merges), "n_soft_pairs": n_soft_pairs,
            "n_soft_merged": n_soft_merged}


def specificities(r: dict) -> tuple[float, float]:
    """Specificity including and excluding the rutile/CaCl2-type class."""
    incl = 1 - r["n_neg_merged"] / r["n_neg"] if r["n_neg"] else float("nan")
    hard = r["n_neg"] - r["n_soft_pairs"]
    other = r["n_neg_merged"] - r["n_soft_merged"]
    excl = 1 - other / hard if hard else float("nan")
    return incl, excl


def canonical_check(mc_fit, sm: StructureMatcher) -> tuple[int, int, list[str]]:
    """Experimental TiO2 triple: the only fully external ground truth here."""
    tio2 = canonical_tio2()
    n = merged_pairs = 0
    merged_names = []
    for p1, p2 in itertools.combinations(tio2, 2):
        n += 1
        merged = mc_fit(tio2[p1], tio2[p2])
        if merged != sm.fit(tio2[p1], tio2[p2]):
            raise AssertionError("check_pair_worker disagrees with StructureMatcher")
        if merged:
            merged_pairs += 1
            merged_names.append(f"{p1}<->{p2}")
    return n, merged_pairs, merged_names


# --- diagnostics -----------------------------------------------------------

def group_membership(symprec: float = SYMPREC) -> None:
    """Entry-by-entry membership of the rutile/CaCl2-type family, with the
    anisotropy of each cell and the label its source database reports.
    """
    data = json.loads(DATA.read_text())
    rows = []
    for _cs, csd in data.items():
        for url, dbd in csd.items():
            db = db_short(url)
            for mid, entry in dbd.items():
                a = entry["normalized_attributes"]
                f = a.get("reduced_formula")
                if f not in FORMULAS or not a.get("lattice_vectors"):
                    continue
                try:
                    s = Structure(a["lattice_vectors"], a["species_at_sites"],
                                  a["cartesian_site_positions"],
                                  coords_are_cartesian=True)
                    if max_vacuum_gap(s) > MAX_VACUUM:
                        continue
                    sg = SpacegroupAnalyzer(s, symprec=symprec).get_space_group_number()
                except Exception:  # noqa: BLE001
                    continue
                if PROTO.get(sg) not in SOFT_PAIR:
                    continue
                rows.append((f, PROTO[sg], DB_NAME[db], mid, ab_anisotropy(s),
                             native_space_group(entry, db)))

    print(f"\nrutile / CaCl2-type membership at symprec={symprec}")
    print(f"  {'comp':6s}{'group':12s}{'database':12s}{'id':18s}"
          f"{'aniso':>9}{'native':>8}")
    for f, proto, db, mid, an, nat in sorted(rows):
        print(f"  {f:6s}{proto:12s}{db:12s}{mid:18s}{an:>8.3f}%"
              f"{(str(nat) if nat else '--'):>8}")


def symprec_sensitivity(mc_fit, sm: StructureMatcher,
                        precs: tuple[float, ...] = (0.01, 0.05, 0.1)) -> None:
    """How the reference set and the reported rates depend on the symmetry
    tolerance used to assign ground truth.

    Reported so that the tolerance-dependence of the ground truth itself is
    visible, rather than assumed away.
    """
    print("\nSymprec sensitivity of the ground truth")
    print(f"  {'symprec':>9}{'groups':>8}{'dup pairs':>11}{'recall':>9}"
          f"{'distinct':>10}{'wrong':>7}{'spec':>7}{'spec excl. soft':>17}")
    for p in precs:
        g = load_oxides(symprec=p, source="recomputed", verbose=False)
        r = evaluate(g, mc_fit, sm)
        n_groups = sum(1 for (_f, sg) in g if sg in PROTO)
        incl, excl = specificities(r)
        print(f"  {p:>9}{n_groups:>8}{r['n_pos_pairs']:>11}"
              f"{r['n_pos_merged'] / r['n_pos_pairs']:>9.2f}{r['n_neg']:>10}"
              f"{r['n_neg_merged']:>7}{incl:>7.2f}{excl:>17.2f}")

    print("\n  In-plane anisotropy 2|a-b|/(a+b) of rutile/CaCl2-type entries "
          f"at symprec={SYMPREC}")
    g = load_oxides(symprec=SYMPREC, source="recomputed", verbose=False)
    for (f, sg), lst in sorted(g.items()):
        if PROTO.get(sg) not in SOFT_PAIR:
            continue
        aniso = sorted(ab_anisotropy(s) for _, s in lst)
        print(f"    {f:5s} {PROTO[sg]:12s} n={len(lst):>2}  "
              + ", ".join(f"{x:.3f}%" for x in aniso))


def space_group_provenance(precs: tuple[float, ...] = (0.01, 0.1)) -> None:
    """Do the database-native labels agree with each other and with a
    recomputed assignment? Answers whether the source databases apply
    differing symmetry conventions.
    """
    data = json.loads(DATA.read_text())
    per_db: dict[str, Counter] = defaultdict(Counter)
    mismatches: dict[str, list[str]] = defaultdict(list)
    unconverted: Counter = Counter()

    for _cs, csd in data.items():
        for url, dbd in csd.items():
            db = db_short(url)
            for mid, entry in dbd.items():
                a = entry["normalized_attributes"]
                f = a.get("reduced_formula")
                if f not in FORMULAS or not a.get("lattice_vectors"):
                    continue
                try:
                    s = Structure(a["lattice_vectors"], a["species_at_sites"],
                                  a["cartesian_site_positions"],
                                  coords_are_cartesian=True)
                    if max_vacuum_gap(s) > MAX_VACUUM:
                        continue
                except Exception:  # noqa: BLE001
                    continue

                labels = {"normalized": a.get("space_group_number"),
                          "native": native_space_group(entry, db)}
                for p in precs:
                    labels[f"recomp@{p}"] = SpacegroupAnalyzer(
                        s, symprec=p).get_space_group_number()

                raw = (entry.get("source_attributes") or {}).get(
                    NATIVE_KEYS.get(db, ""))
                if raw is not None and labels["native"] is None:
                    unconverted[f"{DB_NAME[db]}: {raw!r}"] += 1

                per_db[db]["n"] += 1
                if labels["native"] is not None:
                    per_db[db]["has_native"] += 1
                    for key in ("normalized", *[f"recomp@{p}" for p in precs]):
                        if labels[key] is None:
                            continue
                        same = labels["native"] == labels[key]
                        per_db[db][f"native=={key}"] += int(same)
                        per_db[db][f"cmp_{key}"] += 1
                        if not same and key == f"recomp@{SYMPREC}":
                            mismatches[db].append(
                                f"{f} {mid}: native {labels['native']} vs "
                                f"{key} {labels[key]}")

    print("\nSpace-group label provenance")
    cmp_keys = ["normalized", *[f"recomp@{p}" for p in precs]]
    header = f"  {'database':12s}{'n':>5}{'native':>8}"
    for k in cmp_keys:
        header += ("== " + k).rjust(16)
    print(header)
    for db in DB_ORDER:
        c = per_db.get(db)
        if not c:
            continue
        line = f"  {DB_NAME[db]:12s}{c['n']:>5}{c['has_native']:>8}"
        for k in cmp_keys:
            tot = c[f"cmp_{k}"]
            line += (f"{c[f'native=={k}']}/{tot}".rjust(16) if tot
                     else "--".rjust(16))
        print(line)

    if unconverted:
        print("  unconvertible native labels:")
        for k, v in unconverted.most_common():
            print(f"    {k}  x{v}")
    for db, ms in mismatches.items():
        print(f"  {DB_NAME[db]} native vs recomp@{SYMPREC} disagreements "
              f"({len(ms)}):")
        for m in ms[:20]:
            print(f"    {m}")
        if len(ms) > 20:
            print(f"    ... and {len(ms) - 20} more")


# --- main ------------------------------------------------------------------

def main() -> None:
    # MatCollect's own decision (authoritative) + a direct pymatgen matcher used
    # only for the cross-check and for get_rms_dist.
    worker_init(BASE)
    sm = StructureMatcher(primitive_cell=True, scale=True, **BASE)

    def mc_fit(s1: Structure, s2: Structure) -> bool:
        """MatCollect's shipped duplicate decision."""
        return check_pair_worker((0, 1, s1, s2))[2]

    groups = load_oxides()
    res = evaluate(groups, mc_fit, sm)
    rows = res["rows"]

    print(f"\nMatCollect default tolerances: {BASE}")

    # --- 1. Cross-database reproducibility per well-defined prototype ---------
    # RMS and dV are means over the cross-database MERGED pairs, so both
    # describe the same set. Vol% is the spread over all instances of the group.
    print("\nCross-database reproducibility (same phase, different database)")
    print(f"{'phase':16s}{'n':>4}{'pairs':>7}{'RMS':>10}{'dV':>10}{'Vol%':>8}"
          "   databases")
    tabulated = [r for r in rows if r["pairs"] > 0]
    for r in tabulated:
        rms, dv = r["stats"]
        print(f"{r['formula'] + ' ' + r['proto']:16s}{r['n']:>4}{r['pairs']:>7}"
              f"{rms:>10.4f}{dv:>10.3f}{r['vspread']:>8.1f}   {r['dbs']}")

    dropped = [r for r in rows if r["pairs"] == 0]
    if dropped:
        print("  not tabulated (single database, no cross-database pair): "
              + "; ".join(f"{r['formula']} {r['proto']} (n={r['n']}, {r['dbs']})"
                          for r in dropped))
    partial = [r for r in tabulated if r["n_dbs"] < len(DB_ORDER)]
    print("  every tabulated phase is present in all three databases"
          if not partial else "  phases not present in all three databases:")
    for r in partial:
        print(f"    {r['formula']} {r['proto']}: {r['dbs']}")

    # --- 2. Polymorph discrimination (distinct prototypes must not merge) -----
    print("\nPolymorph discrimination (distinct prototypes, same composition)")
    print(f"  distinct-polymorph pairs tested: {res['n_neg']} "
          f"(from {res['n_combos']} prototype combinations), of which "
          f"{res['n_soft_pairs']} are rutile<->CaCl2-type")
    n_can, n_can_merged, can_names = canonical_check(mc_fit, sm)
    print(f"  canonical TiO2 (experimental, incl. brookite): "
          f"{n_can - n_can_merged}/{n_can} kept apart"
          + (f"  merged: {can_names}" if can_names else ""))
    print(f"  wrongly merged: {res['n_neg_merged']} pair(s) across "
          f"{len(res['false_merges'])} prototype combination(s):")
    for k, v in sorted(res["false_merges"].items()):
        print(f"    {k}  ({v} pairs)")

    # --- 3. Summary -----------------------------------------------------------
    recall = res["n_pos_merged"] / res["n_pos_pairs"]
    incl, excl = specificities(res)
    other = res["n_neg_merged"] - res["n_soft_merged"]
    print("\nSummary at default tolerances:")
    print(f"  cross-database duplicate pairs: {res['n_pos_merged']}/{res['n_pos_pairs']}"
          f" merged (recall = {recall:.2f})")
    print(f"  distinct-polymorph pairs:       {res['n_neg'] - res['n_neg_merged']}"
          f"/{res['n_neg']} kept apart (specificity = {incl:.2f})")
    print(f"  of the {res['n_neg_merged']} false merges, {res['n_soft_merged']} are "
          f"rutile<->CaCl2-type (group-subgroup) and {other} are not")
    print(f"  specificity excluding rutile<->CaCl2-type pairs: {excl:.2f} "
          f"({other} wrong out of {res['n_neg'] - res['n_soft_pairs']})")
    sg_src = (f"recomputed at symprec={SYMPREC}" if SG_SOURCE == "recomputed"
              else SG_SOURCE)
    print(f"  ground truth: space groups {sg_src}; entries with a vacuum gap "
          f"> {MAX_VACUUM} Å excluded as 2D/slab.")
    print("\nEngine check: every decision above was taken by MatCollect's "
          "check_pair_worker and verified against a direct pymatgen "
          "StructureMatcher (run aborts on any disagreement).")

    # --- 4. Provenance and tolerance-dependence of the ground truth -----------
    space_group_provenance()
    group_membership()
    symprec_sensitivity(mc_fit, sm)

    # --- LaTeX table -----------------------------------------------------------
    print("\n% ---- table (reproducibility) ----")
    print(r"\begin{tabular}{lcccc}")
    print(r"  \textbf{Phase} & \textbf{Pairs} & \textbf{RMS} & "
          r"\textbf{$\Delta V$ (\AA$^3$/atom)} & \textbf{$\Delta V$ (\%)} \\")
    print(r"  \hline")
    for r in tabulated:
        rms, dv = r["stats"]
        print(f"  \\ce{{{r['formula']}}} {r['proto']} & {r['pairs']} & "
              f"{rms:.4f} & {dv:.3f} & {r['vspread']:.1f} \\\\")
    print(r"\end{tabular}")


if __name__ == "__main__":
    main()
