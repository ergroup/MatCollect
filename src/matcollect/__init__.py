"""Allows running the Streamlit app from the command line cleanly."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Run the Streamlit app."""
    app_dir = os.environ.get("APP_DIR")
    if app_dir:
        app_path = Path(app_dir) / "app.py"
    else:
        app_path = Path(__file__).resolve().parent.parent.parent / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", app_path.as_posix()]
    subprocess.run(cmd, check=True)  # noqa: S603
