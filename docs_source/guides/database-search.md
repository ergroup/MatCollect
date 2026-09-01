# Database search

This page walks you through finding materials in OPTIMADE-compliant databases and the Materials Project, filtering the results, and passing them to the next step in your workflow.

## 1. Select providers

Open the **Database Search** page. MatCollect uses the following OPTIMADE-compliant databases:

| Name | ID | Description | Homepage |
|------|----|-------------|----------|
| Alexandria | alexandria | A collection of databases from the group of Prof Miguel A. L. Marques at Ruhr University Bochum. | https://alexandria.icams.rub.de |
| Computational materials repository (CMR) | cmr | CMR is a collection of materials repositories from different projects such as C2DB, QPOD and many more | https://cmr.fysik.dtu.dk |
| Materials Cloud | mcloud | A platform for Open Science built for seamless sharing of resources in computational materials science | https://www.materialscloud.org |
| The Materials Project | mp | An open database of computed materials properties to accelerate materials discovery and design | https://www.materialsproject.org |
| novel materials discovery (NOMAD) | nmd | A FAIR data sharing platform for materials science data | https://nomad-lab.eu |
| open database of xtals | odbx | A public database of crystal structures mostly derived from ab initio structure prediction from the group of Dr Andrew Morris at the University of Birmingham https://ajm143.github.io | https://odbx.science |
| Open Materials Database | omdb | The Open Materials Database (omdb) is a database of materials properties maintained by the developers of the High-Throughput Toolkit (httk). It enables easy access to useful materials data, in particular via programmatic interaction using this toolkit. | https://openmaterialsdb.se |
| The Open Quantum Materials Database (OQMD) | oqmd | The OQMD is a database of DFT calculated thermodynamic and structural properties of materials | https://oqmd.org |
| Physical Sciences Data Infrastructure (PSDI) | psdi | The Physical Sciences Data Infrastructure (PSDI) is an integrated data infrastructure that directly supports researchers in the physical sciences in the UK to manage, transform and share their data led by the Science and Technology Facilities Council (STFC) and the University of Southampton. As part of this ecosystem, PSDI serves as an OPTIMADE provider to make some data sources available via OPTIMADE endpoints. | https://www.psdi.ac.uk |
| 2DMatpedia | twodmatpedia | 2DMatpedia, an open computational database of two-dimensional materials from top-down and bottom-up approaches | http://2dmatpedia.org |

- Use **Select All** or **Clear All** to manage your selection quickly, or pick providers individually from the dropdown
- A table shows each selected provider's ID, description, and homepage link

## 2. Define your chemical system

Type your chemical system in the **Enter the chemical system(s)** field using element symbols separated by hyphens, for example `Fe-O` or `Ir-Ru-O`.

You can search multiple systems at once by separating them with commas: `Fe-O, Li-Fe-P-O, Ir-Ru-O`. These are fetched in parallel.

### Exact system vs broad search

The **Exact system only** toggle controls what gets returned:

- **On (default)** — only materials whose elements match exactly what you entered. `Fe-O` returns Fe-O binaries only
- **Off** — returns any material containing your elements, including supersets like Fe-Mn-O. This can be slow for common elements and return thousands of results

!!! note

    Broad search is unavailable in multi-system mode, which always uses exact matching.


### Number of elements

When exact system is off, the **number of elements slider** lets you restrict results to a range of element counts. For example, searching `Fe-O` with a range of 2-4 returns binaries, ternaries, and quaternaries that contain both Fe and O.

!!! note

    This slider is unavailable in multi-system mode.


### Per-provider limit

Set a **Max materials per database** to cap how many results each provider returns. For simple systems like `Fe-O`, leaving this empty can return thousands of entries and cause long load times. Setting a limit of a few hundred is strongly recommended for exploratory searches.

!!! note

    If doing a multi-system search, this limit will apply to each chemical system separately. 


## 3. Run the search

![Database Search](/assets/gifs/database_search.gif)

Click **Search Materials**. MatCollect connects to each selected provider, retrieves matching entries, and normalises the results into a unified format. A success message shows how many materials were retrieved and how long it took.

Any provider that fails (rate limits, downtime, missing endpoints) shows an error below the results without cancelling results from other providers.

## 4. Filter results

Once results load, the **Filter Materials** section lets you narrow them down:

- **Contains elements** — keep only materials whose composition includes any of the selected elements
- **From these databases** — restrict to specific providers
- **Formation energy per atom** — set a numeric range
- **Band gap** — same as above
- **Number of sites** and **number of elements** — integer range sliders

The table updates live as you adjust filters, showing how many of the total results remain.

!!! warning

    The "include missing values" toggle can be used to keep entries where the value of a parameter is unavailable. This can be applied to formation energy per atom, band gap, and number of sites. It is **ON** by default.

## 5. Inspect a material

![Material Retrieval](/assets/gifs/material_retrieval.gif)

Click any row in the results table to open a 3D structure viewer for that entry. This uses the lattice vectors and atomic positions retrieved from the database.

!!! note

    You can access the material viewer wherever there is a table of materials available at any page.

## 6. Export or continue

At the bottom of the page you have three options:

- **Download** — export the filtered results as a JSON file, or collection of POSCAR, CIF, or ASE atoms files
- **Duplicate Removal** — pass the results directly to the duplicate removal page; this is recommended before stability analysis
- **Stability Analysis** — skip straight to stability analysis; a warning is shown because duplicates can skew downstream calculations