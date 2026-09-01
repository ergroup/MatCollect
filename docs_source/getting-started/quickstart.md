# Quickstart

This guide walks you through a complete MatCollect session, from launching the app to exporting a set of stable materials. It assumes you have already followed the [installation instructions](installation.md).

## Launch the app

If you installed with pip:

```bash
matcollect
```

If you are using a container, run `docker compose up` or `podman compose up` instead.

Then open your browser at `http://localhost:8501`.

!!! note
    You can use MatCollect without any installation at [matcollect.example.com](https://matcollect.example.com)!

## The workflow at a glance

MatCollect is built around three steps, each with its own page:

1. **Database search** — find materials across multiple databases
2. **Duplicate removal** — collapse the same structure appearing in different databases
3. **Stability analysis** — evaluate thermodynamic and electrochemical stability

Each step passes its results to the next, so a typical session moves through them in order.

## 1. Search for materials

Open the **Database Search** page and:

1. Select one or more data providers.
2. Enter a chemical system, for example `Fe-O`.
3. Set a per-provider limit (a few hundred is sensible for a first run) to avoid long load times.
4. Click **Search Materials**.

Once results load, you can filter them by element, database, formation energy, band gap, and more. Click any row to inspect its 3D structure.

For full detail, see the [database search guide](../guides/database-search.md).

## 2. Remove duplicates

Click **Duplicate Removal** at the bottom of the search page to carry your results forward. Then:

1. Drag the databases into your preferred priority order. Entries from higher-priority databases are kept when duplicates are found.
2. Leave the matching tolerances at their defaults unless you have a reason to change them.
3. Click **Remove Duplicates**.

A network graph shows how entries across databases relate to each other, and a table lists the deduplicated set. Running this step before stability analysis is strongly recommended.

See the [duplicate removal guide](../guides/duplicate-removal.md) for more.

## 3. Analyse stability

Click **Stability Analysis** to continue. Then:

1. Choose whether to analyse the unique set or all filtered materials.
2. Enable the analyses you want: cross-database energy calibration, Pourbaix analysis, energy above hull, or any combination.
3. Enter your Materials Project API key if you enabled Pourbaix analysis.
4. Click **Analyze Stability**.

Results appear as convex hull plots, Pourbaix diagrams, and a calibration report. Use the threshold filters to narrow down to your stable candidates, then download the result as a JSON file.

See the [stability analysis guide](../guides/stability-analysis.md) for a deeper walkthrough.

## Next steps

- Learn the filtering options in detail in the [database search guide](../guides/database-search.md)
- Understand the stability metrics in the [stability analysis guide](../guides/stability-analysis.md)