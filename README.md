# MatCollect

MatCollect is a Streamlit-based application for collecting, analyzing, and visualizing materials science data. It interfaces with materials databases via the OPTIMADE API and the Materials Project, providing a full pipeline from database query to a deduplicated, stability-filtered dataset.

## Features

- **Database Search** — query materials databases through OPTIMADE-compliant providers and the Materials Project API, with filtering by chemical system, element count, formation energy, and band gap
- **Duplicate Removal** — detect and remove duplicate entries within and across databases using pymatgen's `StructureMatcher` with configurable tolerances, visualised as a force-directed duplicate network
- **Cross-Database Energy Calibration** — fit per-element offsets from structurally matched compounds to place formation energies from different providers on a single reference scale, with standard errors, RMSE, rank, and condition number reported
- **Stability Analysis** — energy above the convex hull for thermodynamic stability, and Pourbaix decomposition energy for electrochemical stability at a specified pH and potential
- **Structure Visualization** — interactive 3D viewing of any retrieved material

### Pipeline order

Calibration must run **before** the convex hull is built. The hull is constructed from whatever formation energies are present at the time, so calibrating afterwards has no effect on the result.

```
Search → Deduplicate → Calibrate → Energy above hull → Pourbaix
```

## Project Structure

```
MatCollect/
├── app.py
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── README.md
├── .github/
│   └── workflows/
├── .streamlit/
│   └── config.toml
├── assets/
│   └── images/
├── docs_source/                # documentation source (Zensical markdown)
│   ├── assets/
│   ├── getting-started/
│   ├── guides/
│   └── reference/
├── paper_figures/              # scripts and data for the paper figures
│   ├── data/
│   └── figures/
├── pages/
│   ├── homepage.py
│   ├── database_search.py
│   ├── duplicate_removal.py
│   └── stability_analysis.py
└── src/
    └── matcollect/
        ├── components/
        │   ├── download.py
        │   ├── optimade_providers.py
        │   ├── session_state.py
        │   ├── sidebar.py
        │   └── value_sliders.py
        └── core/
            ├── database_search/
            │   └── optimade_extractor.py
            ├── duplicate_removal/
            │   ├── duplicate_remover.py
            │   └── workers.py
            ├── stability_analysis/
            │   ├── energy_calibrator.py
            │   ├── e_above_hull_analyzer.py
            │   └── pourbaix_analyzer.py
            └── utils/
                ├── misc.py
                ├── modal_ase_viewer.py
                ├── pymatgen_helper.py
                └── summarizer.py
```

`docs/` holds the built documentation site and is generated output, so it is not edited directly. Rebuild it with `zensical build --clean` after editing files in `docs_source/`.

## Requirements

- Python 3.13+
- A **Materials Project API key** for Pourbaix analysis. Search, deduplication, calibration, and hull screening work without one, though the Materials Project is the default source of elemental reference energies for the hull.

## Installation

Clone the repository and install in editable mode:

```bash
git clone git@github.com:ergroup/MatCollect.git
cd matcollect
pip install -e .
```

If you want to use the build/deployment tools for documentation or containers, run the following:
```bash
pip install -e ".[dev]"
```

## Usage

### Local

```bash
matcollect
```

### Docker

```bash
docker compose up
```

### Podman (HPC / rootless environments)

```bash
podman compose up
```

Then open your browser at `http://localhost:8501`.

## Documentation

Full documentation, including API reference for each core class and three worked case studies (solid-state battery cathodes, plasma-facing fusion materials, and low-iridium OER catalysts), is published at `docs/` and served via GitHub Pages.

Source files live in `docs_source/`. To rebuild after editing:

\```bash
zensical build --clean
\```

## Citation

<!-- TODO: add citation once the paper reference is final. -->

## License

MIT
