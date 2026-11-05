
import requests

from io import BytesIO

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException
)

from PIL import Image, UnidentifiedImageError

from plantnet_client import identify_with_plantnet


app = FastAPI(
    title="Allied Algorithms AI Plant Identifier",
    description="AI-powered invasive plant identification",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "application": "Allied Algorithms AI Plant Identifier",
        "status": "online"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/scan")
async def scan_plant(file: UploadFile = File(...)):

    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp"
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Upload a JPEG, PNG, or WebP image."
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="The image is empty."
        )

    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Maximum image size is 10 MB."
        )

    try:
        image = Image.open(BytesIO(image_bytes))
        image.verify()

    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=400,
            detail="Invalid image file."
        )

    try:
        result = identify_with_plantnet(
            image_bytes,
            file.filename or "plant.jpg",
            file.content_type
        )

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Plant identification timed out."
        )

    except requests.exceptions.HTTPError as error:
        status_code = (
            error.response.status_code
            if error.response is not None else 502
        )

        raise HTTPException(
            status_code=502,
            detail=f"Pl@ntNet API error: {status_code}"
        )

    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to Pl@ntNet."
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Invalid response from Pl@ntNet."
        )

    candidates = result["candidates"]
    top_match = result["top_match"]

    multiflora_candidate = any(
        candidate["is_multiflora_rose"]
        for candidate in candidates
    )

    return {
        "success": True,
        "identification_engine": "Pl@ntNet",
        "species": (
            top_match["scientific_name"]
            if top_match else "Unknown"
        ),
        "confidence": (
            top_match["score"]
            if top_match else 0
        ),
        "multiflora_rose_candidate": multiflora_candidate,
        "candidates": candidates
    }
