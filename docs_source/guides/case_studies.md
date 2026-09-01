# Case Studies

MatCollect adapts a single retrieval-and-screening pipeline to very different
discovery problems. The three case studies below span **solid-state batteries**,
**nuclear fusion**, and **heterogeneous catalysis**, and are ordered by
increasing complexity in data sourcing and stability requirements, from a
single-database hull screen through to the full electrochemical stability suite.

!!! info About the timings
    All timings were measured on a consumer laptop (AMD Ryzen 7 8845HS, 8 cores,
    16 GB RAM, Windows 11). Retrieval times depend mainly on provider server load
    and network conditions and are **indicative rather than reproducible
    benchmarks**; post-retrieval processing scales with local hardware.

---

## Solid-state battery cathode materials

Li-ion cathodes are among the most extensively studied material families in
computational materials science, which makes them an ideal baseline. The
Materials Project offers mature, well-validated coverage of these systems, so a
**single-database query** is enough to build a representative dataset, with no
cross-database calibration needed. Pourbaix analysis is skipped, since these are
solid-state materials that never operate in aqueous environments.

### Search parameters

| Parameter | Value |
|---|---|
| Databases | The Materials Project (single source) |
| Chemical systems | Li-Co-O (LCO), Li-Mn-O (LMO), Li-Ni-Co-Al-O (NCA), Li-Ni-Mn-Co-O (NMC), Li-Fe-P-O (LFP), Li-V-O, Li-Ru-O |
| De-duplication | Default tolerances |
| Cross-database calibration | Not required (single database) |
| Pourbaix analysis | Omitted (non-aqueous) |
| Energy above hull threshold | 0.1 eV/atom, then 0.025 eV/atom |

### Results and timings

| Stage | Materials | Time |
|---|---:|---:|
| Query | 1382 | 20 s |
| De-duplication | 1135 | 72 s |
| Energy above hull ≤ 0.1 eV/atom | 984 | 67 s |
| Energy above hull ≤ 0.025 eV/atom | 167 | 67 s |
| **Total** | **984 / 167 candidates** | **< 4 min** |

Two hull thresholds are reported. The 0.1 eV/atom window is the range commonly
used to capture experimentally observable metastable phases. The stricter
0.025 eV/atom filter — comparable to the reported error of GGA+U reaction
energies relative to experiment — cuts the set to 167 structures to reduce the
cost of downstream screening. Both filters retain structures from all seven
queried systems, giving a dataset ready for voltage-profile screening and
synthesis prioritization.

---

## Plasma-facing materials for fusion

Tungsten (W) is the standard plasma-facing material in fusion reactors thanks to
its high melting point, low sputtering yield, and low tritium retention, but pure
W suffers from low ductility, poor radiation stability, and limited oxidation
resistance. W-based alloys with **Re, Ta, V, Mo, and Cr** are of interest for
improving ductility and radiation tolerance.

A Materials Project-only query returned just 23 materials, too little coverage
for meaningful screening, so the **Alexandria database** was added as a second
source. Alexandria's PBEsol entries were excluded to keep the
exchange-correlation treatment consistent across the combined dataset. As with
the battery case, Pourbaix analysis is skipped given the non-aqueous operating
environment.

### Search parameters

| Parameter | Value |
|---|---|
| Databases | The Materials Project + Alexandria (PBEsol entries excluded) |
| Chemical systems | W, W-Re, W-Ta, W-V, W-Mo, W-Cr |
| De-duplication | Default tolerances; Materials Project prioritized over Alexandria on conflict |
| Cross-database calibration | The Materials Project as reference |
| Pourbaix analysis | Omitted (non-aqueous) |
| Energy above hull threshold | 0.1 eV/atom |

### Results and timings

| Stage | Materials | Time |
|---|---:|---:|
| Query (MP + Alexandria) | 1209 | 124 s |
| De-duplication | 1177 | 11 s |
| Energy-above-hull screening | 101 | 9 s |
| **Total** | **101 candidates** | **< 3 min** |

---

## Lowering iridium content in heterogeneous catalysts

MatCollect was first developed with catalyst discovery in mind, so this case
exercises its full capability set. The target is **iridium oxide catalysts for
the Oxygen Evolution Reaction (OER)**, the kinetic bottleneck of water
electrolysis under Proton Exchange Membrane (PEM) conditions. Bimetal oxides that
pair iridium with more abundant transition metals are a promising route to
low-iridium catalysts, motivating a broad sweep of the **Ir-Ti-O** system to
study iridium doping of titanium oxide.

Every available database carrying formation energy per atom was queried —
**Alexandria, odbx, OQMD, and the Materials Project**. PBEsol entries were filtered out.

### Search parameters

| Parameter | Value |
|---|---|
| Databases | Alexandria, odbx, OQMD, The Materials Project |
| Chemical systems | Ir-O, Ir-Ti-O, Ti-O |
| De-duplication | Default tolerances and default database priority |
| Cross-database calibration | The Materials Project as reference |
| Pourbaix analysis | pH 1.0, electrode potential 1.8 V (PEM anode conditions); retain if $\Delta G_\mathrm{pbx} \leq 0.5$ eV/atom |
| Energy above hull threshold | 0.1 eV/atom |

### Results and timings

| Stage | Materials | Time |
|---|---:|---:|
| Query | 852 | 105 s |
| De-duplication | 563 | 117 s |
| Full stability suite (hull + Pourbaix) | 66 | 234 s |
| **Total** | **66 candidates** | **~7.6 min** |

The 66 electrochemically viable candidates include two crystal structures of
Ir-Ti-O plus a range of Ir-O and Ti-O phases suitable for PEM operating
conditions, a working set for analysing iridium doping in titanium oxide and
comparing iridium oxide polymorphs.
