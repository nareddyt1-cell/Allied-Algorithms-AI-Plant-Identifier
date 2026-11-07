import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO

import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

from plantnet_client import identify_with_plantnet
from consent_store import (
    claim_notification, create_consent, get_consent, init_db, is_active,
    list_public_sightings, list_sightings, mark_notification,
    revoke_consent, save_sighting, utc_now,
)
from cutter_recommendations import get_multiflora_rose_guidance
from email_notifier import send_environmental_notification
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Allied Algorithms AI Plant Identifier",
    description="AI-powered invasive plant identification",
    version="1.1.0",
)


@app.on_event("startup")
def startup() -> None:
    init_db()


FRONTEND_INDEX = Path(__file__).resolve().parent / "frontend" / "index.html"


@app.get("/", include_in_schema=False)
def home():
    """Serve the A.I.M. website from the same origin as the API."""
    return FileResponse(FRONTEND_INDEX, media_type="text/html")


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/scan")
async def scan_plant(file: UploadFile = File(...)):
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Upload a JPEG, PNG, or WebP image.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The image is empty.")
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum image size is 10 MB.")

    try:
        image = Image.open(BytesIO(image_bytes))
        image.verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Invalid image file.")

    try:
        result = identify_with_plantnet(
            image_bytes, file.filename or "plant.jpg", file.content_type
        )
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Plant identification timed out.")
    except requests.exceptions.HTTPError as error:
        status_code = error.response.status_code if error.response is not None else 502
        raise HTTPException(status_code=502, detail=f"Pl@ntNet API error: {status_code}")
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="Unable to connect to Pl@ntNet.")
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid response from Pl@ntNet.")

    candidates = result["candidates"]
    top_match = result["top_match"]
    multiflora_candidate = any(c["is_multiflora_rose"] for c in candidates)

    response = {
        "success": True,
        "identification_engine": "Pl@ntNet",
        "species": top_match["scientific_name"] if top_match else "Unknown",
        "confidence": top_match["score"] if top_match else 0,
        "multiflora_rose_candidate": multiflora_candidate,
        "candidates": candidates,
        # Detection is informational only. No location is read, stored, or shared here.
        "location_collection": "not_requested",
    }
    if multiflora_candidate:
        response["prompt_a"] = get_multiflora_rose_guidance()
        response["prompt_b"] = {
            "available": True,
            "message": (
                "Would you like to voluntarily submit this sighting? "
                "Location is collected only after a separate consent request "
                "and explicit confirmation of device location permission."
            ),
            "consent_endpoint": "/consent",
            "note": "Scanning alone never collects or transmits location.",
        }
    return response


class ConsentRequest(BaseModel):
    map_display_opt_in: bool
    environmental_sharing_opt_in: bool
    device_location_permission_confirmed: bool
    duration_days: int = Field(default=7, ge=1, le=30)


class SightingRequest(BaseModel):
    consent_id: str = Field(min_length=20, max_length=128)
    species: str = Field(default="Rosa multiflora", min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RevokeRequest(BaseModel):
    consent_id: str = Field(min_length=20, max_length=128)


def _active_consent(consent_id: str) -> dict:
    consent = get_consent(consent_id)
    if not consent or not is_active(consent):
        raise HTTPException(status_code=403, detail="Consent is missing, expired, or revoked.")
    return consent


@app.post("/consent", status_code=201)
def grant_consent(request: ConsentRequest):
    # Separate opt-ins: either destination can be declined independently.
    if not request.device_location_permission_confirmed:
        raise HTTPException(
            status_code=403,
            detail="Device location permission must be granted before submitting a location.",
        )
    if not (request.map_display_opt_in or request.environmental_sharing_opt_in):
        raise HTTPException(
            status_code=400,
            detail="Choose at least one location use, or cancel without creating consent.",
        )

    now = utc_now()
    consent_id = secrets.token_urlsafe(32)
    expires = now + timedelta(days=request.duration_days)
    create_consent(
        consent_id,
        request.map_display_opt_in,
        request.environmental_sharing_opt_in,
        now.isoformat(),
        expires.isoformat(),
    )
    return {
        "consent_id": consent_id,
        "map_display_opt_in": request.map_display_opt_in,
        "environmental_sharing_opt_in": request.environmental_sharing_opt_in,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "revocable": True,
        "instructions": "Keep this consent ID private. It authorizes only the selected uses until expiry or revocation.",
    }


@app.post("/sightings", status_code=201)
def submit_sighting(request: SightingRequest):
    consent = _active_consent(request.consent_id)
    if not (consent["map_display_opt_in"] or consent["environmental_sharing_opt_in"]):
        raise HTTPException(status_code=403, detail="No location use was authorized.")
    if request.species.casefold() != "rosa multiflora":
        raise HTTPException(status_code=400, detail="Only confirmed Rosa multiflora sightings are accepted.")

    # Coordinates must be explicitly submitted by the client after its permission flow.
    # The backend does not query device GPS or infer coordinates from scan metadata.
    created_at = utc_now().isoformat()
    sighting_id = save_sighting(
        request.consent_id,
        "Rosa multiflora",
        request.latitude,
        request.longitude,
        created_at,
    )
    notification_status = "not_authorized"
    if consent["environmental_sharing_opt_in"]:
        if claim_notification(sighting_id, utc_now().isoformat()):
            notification = send_environmental_notification(
                species="Rosa multiflora",
                latitude=request.latitude,
                longitude=request.longitude,
                created_at=created_at,
                sighting_id=sighting_id,
                expires_at=consent["expires_at"],
            )
            notification_status = notification["status"]
            mark_notification(sighting_id, notification_status, utc_now().isoformat())
        else:
            notification_status = "duplicate_skipped"
    return {
        "sighting_id": sighting_id,
        "stored": True,
        "map_display_enabled": bool(consent["map_display_opt_in"]),
        "environmental_sharing_authorized": bool(consent["environmental_sharing_opt_in"]),
        "environmental_notification_status": notification_status,
        "message": (
            "Sighting stored for the uses selected in consent. "
            + ("Environmental-group email notification status: " + notification_status + "." if consent["environmental_sharing_opt_in"] else "No environmental-group notification was authorized.")
        ),
    }


@app.get("/sightings/public")
def get_public_sightings():
    """Public map feed; expose only map-authorized, active sightings."""
    rows = list_public_sightings()
    return {
        "sightings": [
            {
                "species": row["species"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "reported_at": row["created_at"],
            }
            for row in rows
        ]
    }


@app.get("/sightings")
def get_sightings(consent_id: str | None = None):
    # With a consent ID, return that owner's consent-authorized map entries.
    # Without one, return the community map: only active, non-revoked consents
    # that explicitly opted into public map display are included.
    if consent_id:
        consent = _active_consent(consent_id)
        if not consent["map_display_opt_in"]:
            raise HTTPException(status_code=403, detail="Map display was not authorized.")
        return {"sightings": list_sightings(consent_id)}
    return {"sightings": list_public_sightings()}


@app.post("/consent/revoke")
def revoke_location_consent(request: RevokeRequest):
    _active_consent(request.consent_id)
    revoked = revoke_consent(request.consent_id, utc_now().isoformat())
    return {
        "revoked": revoked,
        "deleted_sightings": True,
        "message": "Consent revoked; associated stored sightings were deleted.",
    }
