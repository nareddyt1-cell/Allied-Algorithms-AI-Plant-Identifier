# Allied Algorithms AI Plant Identifier

FastAPI application for the A.I.M. (Allied Invasive Mapping) website and plant-identification API. It serves the bundled frontend and backend endpoints from one Render web service.

## Combined website and API deployment

The production website is bundled at `frontend/index.html` and served by FastAPI at `GET /`. API routes remain on the same origin:

- `GET /health`
- `POST /scan`
- `POST /consent`
- `POST /sightings`
- `GET /sightings/public`
- `GET /sightings?consent_id=...`
- `POST /consent/revoke`

The browser calls these paths directly; no second frontend service, CORS setup, or `PLANT_IDENTIFIER_API_URL` proxy is needed.

The canonical editable frontend source is in the [A.I.M. repository](https://github.com/nagellianiketh-crypto/A.I.M.) at `index.html`. When it changes, synchronize it to this repository at `frontend/index.html` on the `backend` branch. **Render deploys this backend repository's `backend` branch only.**

The root `render.yaml` defines the existing single web service, health check, environment variables, and persistent SQLite disk. Keep the disk mounted at `/var/data` so existing sightings persist across restarts. The Render service must have `PLANTNET_API_KEY` configured. SMTP variables are optional unless email notifications are required.

## Current backend features

- Serves the A.I.M. website at `/` and API documentation at `/docs`.
- JPEG, PNG, and WebP image validation (10 MB maximum).
- Pl@ntNet species identification and candidate ranking.
- Multiflora Rose candidate flag.
- Prompt A: general Allied Algorithms net-cutter/removal guidance and safety reminders.
- Prompt B: explicit, time-limited location consent with separate opt-ins for map display and environmental-group sharing.
- SQLite storage for consent records and submitted sightings.
- Community map endpoint returns only active sightings with explicit map-display opt-in; public coordinates are rounded to three decimal places.
- Consent-gated SMTP email notification attempts for environmental groups.
- Consent expiry (1–30 days), revocation, and deletion of sightings associated with revoked consent.

## Run locally

Python 3.10+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your Pl@ntNet API key
uvicorn main:app --reload
```

Set `PLANTNET_API_KEY` in the environment. Set `DATABASE_PATH` to choose the SQLite database location; the default is `data/consent.db`. The bundled frontend is served automatically at `http://127.0.0.1:8000/`.

## Consent and privacy behavior

**A scan never collects location.** The `/scan` response only presents Prompt B as an optional next step. The client must separately obtain the browser/device location permission and show the user independent choices for:

- `map_display_opt_in`
- `environmental_sharing_opt_in`

The client then calls `POST /consent` with those explicit choices and `device_location_permission_confirmed: true`. Consent expires after the selected duration (maximum 30 days). If the user declines, the client must not call the consent or sighting endpoints. Coordinates are accepted only through a subsequent explicit `POST /sightings` request with a valid consent ID. Map retrieval requires map opt-in. Revocation invalidates the consent and deletes its stored sightings.

Example consent request:

```json
{
  "map_display_opt_in": true,
  "environmental_sharing_opt_in": false,
  "device_location_permission_confirmed": true,
  "duration_days": 7
}
```

Example sighting request (only after consent and OS permission):

```json
{
  "consent_id": "the-returned-consent-id",
  "species": "Rosa multiflora",
  "latitude": 41.0,
  "longitude": -73.0
}
```

Use `POST /consent/revoke` with the consent ID to revoke and delete associated sightings.

## Important prototype limitations

- Consent IDs are bearer capabilities, not user authentication. Anyone possessing one can exercise its permissions. Before public production use, bind consent and sighting records to authenticated user accounts, add rate limiting, audit controls, and secure transport.
- `device_location_permission_confirmed` is a client assertion; the backend cannot independently verify the mobile operating system's permission state. The client must enforce the OS permission flow and never submit coordinates after denial.
- Environmental-group email delivery is implemented through SMTP but remains disabled until `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, and `ENVIRONMENTAL_GROUP_EMAILS` are configured in Render. `SMTP_USE_SSL` defaults to `true`; set it to `false` for STARTTLS providers. Failed or unconfigured delivery does not discard the user's saved sighting; the response reports `sent`, `failed`, or `not_configured`.
- `GET /sightings/public` returns exactly `species`, `latitude`, `longitude`, and `reported_at`; it never exposes consent IDs or user/device identifiers. It includes only active, non-revoked consents with `map_display_opt_in=true`; public coordinates are rounded to three decimal places. `GET /sightings?consent_id=...` retains the consent-scoped behavior.
- The net-cutter guidance is general information, not a replacement for manufacturer instructions or qualified land-manager advice.
- The ViT classifier and trained weights are not present. Identification uses Pl@ntNet's `/v2/identify/all` API. Candidate scores are returned by Pl@ntNet and sorted descending; Multiflora Rose is flagged when a candidate's scientific name exactly matches `Rosa multiflora`. This is a candidate signal, not a validated guarantee of reliable identification. No local ViT inference is performed.

Interactive API documentation is available at `/docs`.
