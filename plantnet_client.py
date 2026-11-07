import os
from pathlib import Path

import requests
from dotenv import load_dotenv

PLANTNET_URL = "https://my-api.plantnet.org/v2/identify/all"
ENV_FILE = Path(__file__).resolve().parent / ".env"


def _get_plantnet_api_key() -> str | None:
    """Read the key from Render's environment, falling back to this repo's .env."""
    # Explicit path avoids depending on Render's process working directory.
    # Existing environment variables (such as Render settings) take precedence.
    load_dotenv(dotenv_path=ENV_FILE, override=False)
    return os.getenv("PLANTNET_API_KEY")


def identify_with_plantnet(
    image_bytes: bytes,
    filename: str = "plant.jpg",
    content_type: str = "image/jpeg",
):
    api_key = _get_plantnet_api_key()
    if not api_key:
        raise RuntimeError(
            "PLANTNET_API_KEY is missing. Configure it in the Render service "
            "environment or provide it in the backend .env file."
        )

    files = [("images", (filename, image_bytes, content_type))]
    data = {"organs": "auto"}

    response = requests.post(
        PLANTNET_URL,
        params={"api-key": api_key},
        files=files,
        data=data,
        timeout=45,
    )
    response.raise_for_status()
    result = response.json()

    candidates = []
    for item in result.get("results", []):
        species = item.get("species", {})
        scientific_name = species.get("scientificNameWithoutAuthor", "")
        candidates.append({
            "scientific_name": scientific_name,
            "common_names": species.get("commonNames", []),
            "score": float(item.get("score", 0)),
            "is_multiflora_rose": scientific_name.casefold() == "rosa multiflora",
        })

    candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
    return {
        "engine": "Pl@ntNet",
        "candidates": candidates,
        "top_match": candidates[0] if candidates else None,
    }
