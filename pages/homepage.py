"""Streamlit page for the homepage."""

from pathlib import Path

import streamlit as st

from matcollect.components.session_state import initialize_session_state
from matcollect.components.sidebar import render_sidebar
from matcollect.core.utils.modal_ase_viewer import show_material_preview

# Resolve assets from the project root (this file lives in pages/).
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "images"

# TODO: fill paper doi
URL_DOCS = "https://ergroup.github.io/MatCollect/"
URL_PAPER = "https://example.com/paper"
URL_REPO = "https://github.com/ergroup/MatCollect"
URL_GROUP = "https://www.amdlab.nl/"
URL_OPTIMADE = "https://optimade.org/"

N_PROVIDERS = 10

st.set_page_config(
    page_title="MatCollect",
    layout="wide",
    page_icon=str(ASSETS / "matcollect.ico"),
)


@st.cache_data
def load_html(path: str) -> str:
    """Read a bundled HTML figure once and cache it across reruns."""
    return Path(path).read_text(encoding="utf-8")


initialize_session_state()
render_sidebar()

st.logo(
    str(ASSETS / "matcollect_logo_with_text.png"),
    icon_image=str(ASSETS / "matcollect.ico"),
)

st.image(str(ASSETS / "matcollect_logo_with_text.png"), width="content")

st.markdown("""
# Millions of crystal structures. Reduced to a defensible few.""", text_alignment="center")
STAGE_COLORS = {
    "dedup": "#7F77DD",
    "calibration": "#1D9E75",
    "stability": "#D85A30",
    "pipeline": "#888780",
}

def metric_card(col, label: str, value: str, color: str) -> None:
    """Metric with a coloured value and a top accent rule."""
    col.markdown(
        f"<div style='border-top:3px solid {color}; padding:0.6rem 0.2rem;'>"
        f"<p style='margin:0; font-size:1.0rem; opacity:1.0;'>{label}</p>"
        f"<p style='margin:0; font-size:1.6rem; font-weight:600; color:{color};'>{value}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

m1, m2, m3, m4 = st.columns(4)
metric_card(m1, "OPTIMADE providers", str(N_PROVIDERS), STAGE_COLORS["pipeline"])
metric_card(m2, "Battery screening", "1382 → 167", STAGE_COLORS["dedup"])
metric_card(m3, "Fusion screening", "1209 → 101", STAGE_COLORS["calibration"])
metric_card(m4, "Catalyst screening", "852 → 66", STAGE_COLORS["stability"])
st.write("")

st.markdown("""
MatCollect retrieves materials from public OPTIMADE databases, removes structural
duplicates, calibrates formation energies onto a common reference scale, and screens
the result for thermodynamic and electrochemical stability, a full pipeline from
query to shortlist, within minutes.
""")

cta1, cta2, cta3, cta4 = st.columns([1, 1, 1, 1])
with cta1:
    st.link_button("Read the paper", URL_PAPER, width="stretch", type="primary")
with cta2:
    st.link_button("Documentation", URL_DOCS, width="stretch")
with cta3:
    st.link_button("Source code", URL_REPO, width="stretch")
with cta4:
    st.link_button("Our group", URL_GROUP, width="stretch")

st.markdown("""---""")


st.markdown("""## What you get""")

c1, c2 = st.columns(2)
with c1:
    st.markdown(f"""
#### Query all you want
Search {N_PROVIDERS} OPTIMADE providers at once or individually; The Materials Project, Alexandria, OQMD and more.
Filter by chemical system, formation energy, and band gap, with per-database limits to prevent over-representation.
""")
with c2:
    st.markdown("""
#### Remove duplicates
Structures are matched on geometry with `StructureMatcher` rather than on formula
or ID, at tolerances you set. Redundancy within a single provider is caught alongside
redundancy across providers.
""")

c3, c4 = st.columns(2)
with c3:
    st.markdown("""
#### Put energies on one scale
Each database references its own elemental states. Per-element offsets are fitted by
least squares from structurally matched compounds, and reported with standard errors,
RMSE, rank, and condition number.
""")
with c4:
    st.markdown("""
#### Stability, not just formation energy
Energy above the convex hull gives thermodynamic reachability. Pourbaix decomposition
energy at a specified pH and potential gives electrochemical stability in aqueous
environments.
""")

st.write("")
st.write("")

# Showcase
def card_title(header: str) -> None:
    """Centered card header with normal-weight subtext beneath."""
    st.markdown(f"### {header}", text_alignment="center")

st.markdown("""## See it work""")

show1, show2 = st.columns(2)
with show1, st.container(border=True):
    card_title(
        "Cross-Database Duplicates")
    st.components.v1.html(
        load_html(str(ASSETS / "duplicate_network_example.html")),
        height=560,
    )
with show2, st.container(border=True):
    card_title(
        "Interactive Convex Hulls",
    )
    st.components.v1.html(
        load_html(str(ASSETS / "e_above_hull_example.html")),
        height=560,
    )

show3, show4 = st.columns(2)
with show3, st.container(border=True, height=590):
    card_title(
        "Pourbaix Diagrams"
    )
    st.image(str(ASSETS / "pourbaix_example.png"), width="stretch")
with show4, st.container(border=True, height=590):
    card_title(
        "Structures in 3D",
    )
    show_material_preview()

st.write("")
st.write("")

# Why it matters
def why_card(color: str, header: str, body: str) -> None:
    """Render a why-it-matters card with a coloured left accent bar."""
    st.markdown(
        f"<div style='border-left:4px solid {color}; padding:0.75rem 1rem; "
        f"margin-bottom:1rem;'>"
        f"<h4 style='margin:0 0 0.4rem 0;'>{header}</h4>"
        f"<p style='margin:0;'>{body}</p></div>",
        unsafe_allow_html=True,
    )


st.markdown("## Why This Workflow Matters")
st.markdown(
    "Materials science increasingly relies on large-scale data mining, but public "
    "databases pose challenges that can quietly compromise machine learning and "
    "computational screening."
)

why_card(
    STAGE_COLORS["pipeline"],
    "Eliminating redundancy and bias",
    "Aggregating data from multiple OPTIMADE providers pulls in the same structure "
    "under different IDs, and redundancy exists within a single provider too. Left in, "
    "it skews statistics and overrepresents whichever compounds happen to be popular. "
    "MatCollect matches on geometry, so each structure is counted once.",
)

why_card(
    STAGE_COLORS["dedup"],
    "Standardizing heterogeneous data",
    "Databases differ in naming, units, and metadata, and each computes formation "
    "energy against its own elemental references. MatCollect harmonizes the attributes "
    "and calibrates the energies onto a common scale, so energies, band gaps, and "
    "lattices can be compared directly.",
)

why_card(
    STAGE_COLORS["calibration"],
    "Beyond thermodynamics",
    "Formation energy alone does not determine real-world stability. A compound sitting "
    "exactly on the convex hull can still dissolve on contact with water at operating "
    "potential. Combining hull and Pourbaix analysis identifies the materials that "
    "survive the conditions they will actually meet.",
)

why_card(
    STAGE_COLORS["stability"],
    "Accelerating discovery",
    "Manual curation is slow and rarely reproducible twice. MatCollect automates the "
    "full pipeline, from API retrieval to a deduplicated, stability-filtered dataset, "
    "and records the parameters it used along the way.",
)

st.markdown("""---""")

# Links
link1, link2 = st.columns(2)
with link1:
    st.markdown(f"""
#### Project
- [Documentation]({URL_DOCS})
- [Paper]({URL_PAPER})
- [Source code]({URL_REPO})
- [Research group]({URL_GROUP})
""")
with link2:
    st.markdown(f"""
#### Built on
- [OPTIMADE]({URL_OPTIMADE})
- [pymatgen](https://pymatgen.org/)
- [Materials Project](https://materialsproject.org/)
- [Streamlit](https://streamlit.io/)
""")

# TODO: add contact and citation once the paper reference is final.
