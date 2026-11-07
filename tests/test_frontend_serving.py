def test_root_serves_bundled_aim_frontend():
    import main

    response = main.home()

    assert response.media_type == "text/html"
    assert response.path == main.FRONTEND_INDEX
    assert main.FRONTEND_INDEX.is_file()


def test_bundled_frontend_uses_same_origin_api_routes():
    import main

    html = main.FRONTEND_INDEX.read_text(encoding="utf-8")

    assert "fetch(path, options)" in html
    assert "fetch('/api'+path" not in html
    assert "PLANT_IDENTIFIER_API_URL" not in html
    assert "api('/scan'" in html
    assert "api('/sightings/public'" in html
