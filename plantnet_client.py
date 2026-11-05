
import os
import requests
from dotenv import load_dotenv

load_dotenv()

PLANTNET_API_KEY = os.getenv("PLANTNET_API_KEY")

PLANTNET_URL = "https://my-api.plantnet.org/v2/identify/all"


def identify_with_plantnet(
    image_bytes: bytes,
    filename: str = "plant.jpg",
    content_type: str = "image/jpeg"
):

    if not PLANTNET_API_KEY:
        raise RuntimeError("PLANTNET_API_KEY is missing")

    files = [
        ("images", (filename, image_bytes, content_type))
    ]

    data = {"organs": "auto"}

    response = requests.post(
        PLANTNET_URL,
        params={"api-key": PLANTNET_API_KEY},
        files=files,
        data=data,
        timeout=45
    )

    response.raise_for_status()

    result = response.json()

    candidates = []

    for item in result.get("results", []):

        species = item.get("species", {})

        scientific_name = species.get(
            "scientificNameWithoutAuthor", ""
        )

        candidates.append({
            "scientific_name": scientific_name,
            "common_names": species.get("commonNames", []),
            "score": float(item.get("score", 0)),
            "is_multiflora_rose": (
                scientific_name.casefold() == "rosa multiflora"
            )
        })

    candidates.sort(
        key=lambda candidate: candidate["score"],
        reverse=True
    )

    return {
        "engine": "Pl@ntNet",
        "candidates": candidates,
        "top_match": candidates[0] if candidates else None
    }
