"""Main Streamlit App."""

import logging
import sys
from pathlib import Path

import streamlit as st

logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)

sys.path.append(str(Path.cwd()))

PAGES_DIR = Path(__file__).resolve().parent / "pages"

pages = [
    st.Page(PAGES_DIR / "homepage.py", title="Homepage"),
    st.Page(PAGES_DIR / "database_search.py", title="Database Search"),
    st.Page(PAGES_DIR / "duplicate_removal.py", title="Duplicate Removal"),
    st.Page(PAGES_DIR / "stability_analysis.py", title="Stability Analysis"),
]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
