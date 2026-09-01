"""Function for processing the list of available providers from the Optimade API."""

import requests
import streamlit as st


@st.cache_data
def load_providers() -> dict:
    """Fetch the available providers from the Optimade database.
    Returns:
        dict: A dictionary where the keys are the names of the providers
        and the values are dictionaries containing
        the ID, description, and homepage of the provider.
    Notes:
        The providers are fetched from the URL https://providers.optimade.org/providers.json.
        The providers 'exmpl', 'aflow', 'cod', 'matcloud', 'mcloudarchive',
        'mpdd', 'mpds', 'mpod', 'matterverse', 'jarvis', and 'tcod' are excluded.
    """
    response = requests.get("https://providers.optimade.org/providers.json", timeout=10)
    response.raise_for_status()
    data = response.json()  # Parse JSON
    providers = {}
    included_providers = [
        "alexandria",
        "mcloud",
        "mcloudarchive",
        "mp",
        "nmd",
        "odbx",
        "omdb",
        "oqmd",
        "jarvis",
        "twodmatpedia",
    ]

    for provider in data.get("data", []):
        attributes = provider.get("attributes", {})
        # Skip entries without a base URL (non-functional)
        if attributes.get("base_url") is None:
            continue
        provider_id = provider.get("id")
        if provider_id not in included_providers:
            continue
        name = attributes.get("name")
        description = attributes.get("description")
        homepage = attributes.get("homepage")
        providers[name] = {
            "id": provider_id,
            "description": description,
            "homepage": homepage,
        }
    return providers
