from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def _client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_health_ok_without_secrets():
    client = _client(Settings(_env_file=None, gemini_api_key=None, database_url=None))
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["gemini_configured"] is False
    assert body["database_configured"] is False


def test_health_never_returns_secret_values():
    client = _client(Settings(_env_file=None, gemini_api_key="fake-test-key"))
    r = client.get("/health")
    assert r.json()["gemini_configured"] is True
    assert "fake-test-key" not in r.text
