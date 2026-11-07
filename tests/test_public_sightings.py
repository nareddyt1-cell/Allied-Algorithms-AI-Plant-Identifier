from datetime import datetime, timedelta, timezone


def test_public_sightings_only_include_active_map_opt_ins(tmp_path, monkeypatch):
    import consent_store

    monkeypatch.setattr(consent_store, "DATABASE_PATH", str(tmp_path / "public.db"))
    consent_store.init_db()
    now = datetime.now(timezone.utc)
    created = now.isoformat()
    future = (now + timedelta(days=1)).isoformat()
    past = (now - timedelta(seconds=1)).isoformat()

    consent_store.create_consent("public-map-token-00000001", True, False, created, future)
    consent_store.create_consent("private-group-token-00000002", False, True, created, future)
    consent_store.create_consent("expired-map-token-00000003", True, False, created, past)
    consent_store.create_consent("revoked-map-token-00000004", True, False, created, future)

    for token, lat in [
        ("public-map-token-00000001", 41.12345),
        ("private-group-token-00000002", 41.2),
        ("expired-map-token-00000003", 41.3),
        ("revoked-map-token-00000004", 41.4),
    ]:
        consent_store.save_sighting(token, "Rosa multiflora", lat, -73.34567, created)

    consent_store.revoke_consent("revoked-map-token-00000004", now.isoformat())
    results = consent_store.list_public_sightings()

    assert len(results) == 1
    assert results[0]["species"] == "Rosa multiflora"
    assert results[0]["latitude"] == 41.123
    assert results[0]["longitude"] == -73.346
    assert set(results[0]) == {"id", "species", "latitude", "longitude", "created_at"}


def test_notification_claim_is_idempotent(tmp_path, monkeypatch):
    import consent_store

    monkeypatch.setattr(consent_store, "DATABASE_PATH", str(tmp_path / "notifications.db"))
    consent_store.init_db()
    now = datetime.now(timezone.utc).isoformat()
    consent_store.create_consent("notify-token-00000000001", False, True, now,
                                 (datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    sighting_id = consent_store.save_sighting(
        "notify-token-00000000001", "Rosa multiflora", 41.0, -73.0, now
    )

    assert consent_store.claim_notification(sighting_id, now) is True
    assert consent_store.claim_notification(sighting_id, now) is False
    consent_store.mark_notification(sighting_id, "failed", now)
