def test_plantnet_key_loader_uses_explicit_backend_env_file(monkeypatch):
    import plantnet_client

    monkeypatch.delenv("PLANTNET_API_KEY", raising=False)
    seen = {}

    def fake_load_dotenv(*, dotenv_path, override):
        seen["dotenv_path"] = dotenv_path
        seen["override"] = override
        monkeypatch.setenv("PLANTNET_API_KEY", "test-key")

    monkeypatch.setattr(plantnet_client, "load_dotenv", fake_load_dotenv)

    assert plantnet_client._get_plantnet_api_key() == "test-key"
    assert seen["dotenv_path"] == plantnet_client.ENV_FILE
    assert seen["override"] is False


def test_render_environment_key_takes_precedence(monkeypatch):
    import plantnet_client

    monkeypatch.setenv("PLANTNET_API_KEY", "render-environment-key")
    calls = []
    monkeypatch.setattr(
        plantnet_client,
        "load_dotenv",
        lambda **kwargs: calls.append(kwargs),
    )

    assert plantnet_client._get_plantnet_api_key() == "render-environment-key"
    assert calls == [{"dotenv_path": plantnet_client.ENV_FILE, "override": False}]
