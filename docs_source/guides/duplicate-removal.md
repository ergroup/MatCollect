# Duplicate removal

When querying multiple providers for the same chemical system, the same crystal structure often appears under different IDs across databases. The duplicate removal page identifies these and keeps one representative entry per unique structure.

It is strongly recommended to run this step before stability analysis, as duplicates can skew convex hull calculations.

## 1. Load your data

The duplicate removal page picks up directly from the database search results. If you arrive here without having run a search first, the page will prompt you to go back and do that.

You can also navigate here by clicking **Duplicate Removal** at the bottom of the database search page, which carries your filtered results over automatically.

## 2. Set database priority

The priority list determines which database "wins" when two entries are identified as duplicates of each other. The entry from the higher-priority database is kept; the one from the lower-priority database is removed.

![Adjusting database priority](/assets/gifs/duplicate_priority.gif)

Drag databases up or down to reflect your trust in their data quality, calculation methodology, or relevance to your use case. For example, if you trust Materials Project energies more than OQMD for your system, place it above OQMD in the list.

## 3. Set tolerances

Duplicate detection uses PyMatGen's `StructureMatcher` under the hood. Three tolerances control how strictly two structures must match to be considered duplicates:

| Tolerance | Default | What it controls |
|---|---|---|
| Fractional length tolerance | 0.2 | How much lattice vector lengths can differ |
| Site tolerance | 0.3 | Maximum allowed atomic displacement, normalised to average free length per atom |
| Angle tolerance | 5° | Maximum allowed difference in lattice angles |

If you are unsure, the defaults work well for most DFT-relaxed structures from standard databases. Tighten them if you want to be conservative about what counts as a duplicate; loosen them if you are working with structures from methods that produce slightly different geometries for the same phase.

## 4. Run duplicate removal

Click **Remove Duplicates**. A spinner shows progress and the elapsed time is reported on completion.

## 5. Inspect the results

### Duplicate graphs

Each chemical system gets a network graph showing how entries across databases relate to each other. Nodes are individual materials; edges connect entries identified as duplicates. The kept entry (from the highest-priority database) is visually distinct from the removed ones.

![Interactive Duplicate Network](/assets/gifs/duplicate_network.gif)

Use the chemical system dropdown to switch between systems. You can download all graphs as a ZIP file.

### Unique materials table

The **Show all unique materials** expander shows the deduplicated dataset with a count of how many entries were retained out of the total. Click any row to open the 3D structure viewer for that entry.

## 6. Export or continue

- **Download** — export the unique materials as a JSON file or other formats
- **Stability Analysis** — pass the deduplicated dataset to the stability analysis page
