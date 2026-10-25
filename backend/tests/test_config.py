from app.core.config import Settings


def _clean_env(monkeypatch):
    for key in ("APP_ENV", "LOG_LEVEL", "GEMINI_API_KEY", "GEMINI_MODEL", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)


def test_defaults_without_secrets(monkeypatch):
    _clean_env(monkeypatch)
    s = Settings(_env_file=None)
    assert s.app_env == "development"
    assert s.gemini_configured is False
    assert s.database_configured is False


def test_reads_environment_variables(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")
    monkeypatch.setenv("APP_ENV", "testing")
    s = Settings(_env_file=None)
    assert s.gemini_configured is True
    assert s.app_env == "testing"


def test_secrets_not_exposed_in_repr(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:pw-secret@localhost/db")
    s = Settings(_env_file=None)
    text = repr(s) + str(s)
    assert "fake-test-key" not in text
    assert "pw-secret" not in text


def test_unverified_access_is_off_by_default(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.delenv("ALLOW_UNVERIFIED_RECORDS", raising=False)
    assert Settings(_env_file=None).allow_unverified_records is False


def test_unverified_access_can_be_enabled(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("ALLOW_UNVERIFIED_RECORDS", "true")
    assert Settings(_env_file=None).allow_unverified_records is True
