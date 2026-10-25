"""Needs real pydantic-settings."""
from app.core.config import Settings


def test_cors_default_is_the_nextjs_dev_server(monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins_list == ["http://localhost:3000"]


def test_cors_origins_are_split_and_trimmed(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", " http://a.test , https://b.test ,")
    assert Settings(_env_file=None).cors_origins_list == ["http://a.test", "https://b.test"]


def test_cors_can_be_disabled(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "")
    assert Settings(_env_file=None).cors_origins_list == []
