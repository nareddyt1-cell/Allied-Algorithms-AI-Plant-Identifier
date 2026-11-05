import importlib
from datetime import datetime, timedelta, timezone


def test_consent_expiry_and_revoke(tmp_path, monkeypatch):
    import consent_store

    monkeypatch.setattr(consent_store, "DATABASE_PATH", str(tmp_path / "test.db"))
    consent_store.init_db()

    now = datetime.now(timezone.utc)
    created = now.isoformat()
    expires = (now + timedelta(days=2)).isoformat()
    consent_store.create_consent("capability-token", True, False, created, expires)

    consent = consent_store.get_consent("capability-token")
    assert consent is not None
    assert consent["map_display_opt_in"] == 1
    assert consent["environmental_sharing_opt_in"] == 0
    assert consent_store.is_active(consent, now)

    assert consent_store.save_sighting(
        "capability-token", "Rosa multiflora", 41.0, -73.0, created
    ) > 0
    assert len(consent_store.list_sightings("capability-token")) == 1

    assert consent_store.revoke_consent("capability-token", now.isoformat())
    assert consent_store.list_sightings("capability-token") == []
    assert not consent_store.is_active(consent_store.get_consent("capability-token"), now)


def test_expired_consent_is_inactive():
    import consent_store

    now = datetime.now(timezone.utc)
    consent = {
        "revoked_at": None,
        "expires_at": (now - timedelta(seconds=1)).isoformat(),
    }
    assert not consent_store.is_active(consent, now)
