def test_public_endpoint_returns_only_frontend_fields(monkeypatch):
    import main

    monkeypatch.setattr(main, "list_public_sightings", lambda: [{
        "id": 77,
        "species": "Rosa multiflora",
        "latitude": 41.15,
        "longitude": -73.35,
        "created_at": "2026-11-06T14:30:00+00:00",
        "consent_id": "must-not-leak",
    }])
    response = main.get_public_sightings()

    assert response == {
        "sightings": [{
            "species": "Rosa multiflora",
            "latitude": 41.15,
            "longitude": -73.35,
            "reported_at": "2026-11-06T14:30:00+00:00",
        }]
    }
    assert "consent_id" not in response["sightings"][0]
    assert "id" not in response["sightings"][0]
