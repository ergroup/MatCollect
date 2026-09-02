# Installation

MatCollect runs as a Streamlit application. You can install it directly with Python or run it in a container with Docker or Podman.

Alternatively, you can use MatCollect without any installation at [matcollect.streamlit.app](https://matcollect.streamlit.app/).

## Requirements

- Python 3.13 or newer

## Install with pip

Clone the repository and install in editable mode:

```bash
git clone git@github.com:ergroup/MatCollect.git
cd matcollect
pip install -e .
```

This installs MatCollect and all its dependencies, including PyMatGen, the OPTIMADE client, and the Materials Project API client.

Once installed, the `matcollect` command is available on your path. See the [Quickstart](quickstart.md) to launch the app.

## Run with Docker

If you prefer not to manage a Python environment, the project ships with a Docker setup:

```bash
docker compose up
```

This builds the image and starts the app. Once running, open your browser at `http://localhost:8501`.

## Run with Podman

For HPC or rootless environments where Docker is unavailable, Podman works as a drop-in replacement:

```bash
podman compose up
```

The app is served at the same address, `http://localhost:8501`.

## Materials Project API key

- **Pourbaix analysis** requires a Materials Project API key to fetch aqueous ion reference data.

You can obtain a free key from your [Materials Project account](https://materialsproject.org/api). The key is entered directly in the app when running an analysis that needs it, so no configuration file changes are required.
