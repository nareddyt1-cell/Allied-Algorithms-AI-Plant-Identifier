"""SQLite persistence for explicit, time-limited location consent.

The consent_id is a bearer capability in this prototype. Production deployments
must bind consent and sighting records to an authenticated user account.
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/consent.db")


def _connect() -> sqlite3.Connection:
    path = Path(DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS consents (
                consent_id TEXT PRIMARY KEY,
                map_display_opt_in INTEGER NOT NULL,
                environmental_sharing_opt_in INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS sightings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consent_id TEXT NOT NULL REFERENCES consents(consent_id),
                species TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS notification_deliveries (
                sighting_id INTEGER PRIMARY KEY REFERENCES sightings(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                attempted_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_sightings_consent ON sightings(consent_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_consents_map_expiry ON consents(map_display_opt_in, expires_at, revoked_at)")
        _purge_expired_sightings(db)


def create_consent(consent_id: str, map_opt_in: bool, sharing_opt_in: bool,
                   created_at: str, expires_at: str) -> None:
    with _connect() as db:
        db.execute(
            """INSERT INTO consents
               (consent_id, map_display_opt_in, environmental_sharing_opt_in,
                created_at, expires_at, revoked_at)
               VALUES (?, ?, ?, ?, ?, NULL)""",
            (consent_id, int(map_opt_in), int(sharing_opt_in), created_at, expires_at),
        )


def _purge_expired_sightings(db: sqlite3.Connection) -> None:
    """Remove location records whose consent has expired; retain consent audit metadata."""
    now = utc_now()
    rows = db.execute("SELECT consent_id, expires_at FROM consents WHERE revoked_at IS NULL").fetchall()
    expired_ids = []
    for row in rows:
        expiry = datetime.fromisoformat(row["expires_at"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= now:
            expired_ids.append(row["consent_id"])
    if expired_ids:
        db.executemany("DELETE FROM sightings WHERE consent_id = ?", [(item,) for item in expired_ids])


def get_consent(consent_id: str) -> dict[str, Any] | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM consents WHERE consent_id = ?", (consent_id,)).fetchone()
        if row:
            expiry = datetime.fromisoformat(row["expires_at"])
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= utc_now():
                db.execute("DELETE FROM sightings WHERE consent_id = ?", (consent_id,))
        return dict(row) if row else None


def save_sighting(consent_id: str, species: str, latitude: float,
                  longitude: float, created_at: str) -> int:
    with _connect() as db:
        cursor = db.execute(
            """INSERT INTO sightings
               (consent_id, species, latitude, longitude, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (consent_id, species, latitude, longitude, created_at),
        )
        return int(cursor.lastrowid)


def list_sightings(consent_id: str) -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute(
            """SELECT id, species, latitude, longitude, created_at
               FROM sightings WHERE consent_id = ? ORDER BY created_at DESC""",
            (consent_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_public_sightings() -> list[dict[str, Any]]:
    """Return only active public-map opt-ins, with coordinates coarsened to ~100 m."""
    with _connect() as db:
        _purge_expired_sightings(db)
        now = utc_now().isoformat()
        rows = db.execute(
            """SELECT s.id, s.species,
                      ROUND(s.latitude, 3) AS latitude,
                      ROUND(s.longitude, 3) AS longitude,
                      s.created_at
               FROM sightings AS s
               JOIN consents AS c ON c.consent_id = s.consent_id
               WHERE c.map_display_opt_in = 1
                 AND c.revoked_at IS NULL
                 AND c.expires_at > ?
               ORDER BY s.created_at DESC""",
            (now,),
        ).fetchall()
    return [dict(row) for row in rows]


def claim_notification(sighting_id: int, attempted_at: str) -> bool:
    """Atomically reserve one notification attempt per sighting."""
    with _connect() as db:
        cursor = db.execute(
            """INSERT OR IGNORE INTO notification_deliveries
               (sighting_id, status, attempted_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (sighting_id, "sending", attempted_at, attempted_at),
        )
        return cursor.rowcount == 1


def mark_notification(sighting_id: int, status: str, updated_at: str) -> None:
    with _connect() as db:
        db.execute(
            "UPDATE notification_deliveries SET status = ?, updated_at = ? WHERE sighting_id = ?",
            (status, updated_at, sighting_id),
        )


def revoke_consent(consent_id: str, revoked_at: str) -> bool:
    with _connect() as db:
        cursor = db.execute(
            "UPDATE consents SET revoked_at = ? WHERE consent_id = ? AND revoked_at IS NULL",
            (revoked_at, consent_id),
        )
        if cursor.rowcount:
            db.execute("DELETE FROM sightings WHERE consent_id = ?", (consent_id,))
            return True
    return False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_active(consent: dict[str, Any], now: datetime | None = None) -> bool:
    if consent.get("revoked_at"):
        return False
    expiry = datetime.fromisoformat(consent["expires_at"])
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry > (now or utc_now())
