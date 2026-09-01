# Stability analysis

The stability analysis page evaluates the thermodynamic stability of your materials using energy above hull analysis and Pourbaix diagrams. Run this after duplicate removal for the most reliable results.

## 1. Select materials

At the top of the page, MatCollect detects what data is available in your session:

- If you ran duplicate removal, a **Unique materials only** toggle lets you choose between the deduplicated set or the full filtered set
- If you skipped duplicate removal, all filtered materials from the database search are used automatically

## 2. Configure the analysis

Three analysis steps can be toggled on or off independently:

### Cross-database energy calibration

When combining data from multiple providers, formation energies are not directly comparable because each database uses different DFT settings and elemental reference states. Calibration fits per-element energy offsets using structurally matched compounds found in the pre-deduplication data, then applies those offsets to bring all materials onto the same energy scale.

Select a **reference database** to calibrate against. Materials Project is selected by default if present. If only one database is in your dataset, calibration is skipped automatically.

Calibration is strongly recommended before hull or Pourbaix analysis when your data spans multiple providers.

### Pourbaix analysis

Pourbaix diagrams map thermodynamically stable phases as a function of pH and electrochemical potential. This is useful for screening corrosion resistance and electrochemical stability.

![Pourbax Diagram Example](/assets/images/pourbaix_example.png)

Required inputs:

- **Materials Project API key** — used to fetch aqueous ion reference data
- **pH** — default 7.0
- **Overpotential** — default 0.0 V

!!! warning

    Materials without a valid `formation_energy_per_atom` are skipped. Treat results as a screening tool and validate promising candidates with higher-fidelity methods.

### Energy above hull analysis

Computes the energy difference (eV/atom) between each material and the convex hull of stable phases in its chemical system:

- **0.0 eV/atom** — on the hull, thermodynamically stable
- **> 0.0 eV/atom** — above the hull, likely to decompose

![Convex Hull Example](/assets/gifs/convex_hull.gif)

Set the **visibility threshold** to control which unstable materials appear in the convex hull plot. The default of 0.2 eV/atom is a reasonable starting point for initial screening, as this range captures potentially synthesisable metastable materials without flooding the plot with clearly unstable entries.

It is possible to change which database to retrieve the terminal entries of the plot from. By default, it is same as the energy calibration reference database.

!!! warning

    Convex hull plots are available for systems with 1, 2, or 3 distinct elements. Systems with more elements are still analysed numerically but cannot be visualised.

## 3. Run the analysis

Click **Analyze Stability**. Each enabled step runs in sequence and reports its elapsed time on completion. If Pourbaix analysis is enabled but no API key is entered, the run will not start.

## 4. Inspect results

Results for each analysis appear in expandable sections:

**Calibration report** shows, per database, how many matched compounds were used to fit offsets, the RMSE in meV/atom, and the fitted per-element offsets. A warning is shown if calibration failed for a database.

**Pourbaix diagrams** are shown per chemical system, database, and material ID. Use the three dropdowns to navigate between entries. All diagrams can be downloaded as a ZIP file.

**Convex hull plots** show the hull for each chemical system with stable phases on the hull and near-stable materials plotted above it up to your visibility threshold. Use the dropdown to switch between systems. All plots can be downloaded as a ZIP file.

## 5. Filter stable materials

Below the results, set numeric thresholds to filter down to your candidates:

- **Energy above hull threshold** — keep materials at or below this value (eV/atom); 0.1 eV/atom is a reasonable cutoff for stability
- **Decomposition energy threshold** — keep materials at or below this Pourbaix decomposition energy (eV/atom)

The table updates to show how many materials pass the combined filters. Click any row to open the 3D structure viewer. When you are satisfied with the selection, download the stable materials as a JSON file or other formats.