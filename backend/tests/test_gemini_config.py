"""Needs real pydantic-settings."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _clean(monkeypatch):
    for k in ("GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_TIMEOUT_SECONDS", "GEMINI_THINKING_LEVEL"):
        monkeypatch.delenv(k, raising=False)


def test_defaults(monkeypatch):
    _clean(monkeypatch)
    s = Settings(_env_file=None)
    assert s.gemini_model == "gemini-3.8-flash"
    assert s.gemini_timeout_seconds == 30
    assert s.gemini_thinking_level is None


def test_thinking_level_accepts_valid_values(monkeypatch):
    _clean(monkeypatch)
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "LOW")
    assert Settings(_env_file=None).gemini_thinking_level == "LOW"


@pytest.mark.parametrize("bad", ["MINIMAL", "low-ish", "0"])
def test_invalid_thinking_level_is_rejected(monkeypatch, bad):
    _clean(monkeypatch)
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", bad)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("bad", ["0", "-5", "500"])
def test_invalid_timeout_is_rejected(monkeypatch, bad):
    _clean(monkeypatch)
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", bad)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("bad", ["0", "-1", "601"])
def test_invalid_rate_limit_is_rejected(monkeypatch, bad):
    monkeypatch.setenv("TUTOR_RATE_LIMIT_PER_MINUTE", bad)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_rate_limit_default(monkeypatch):
    monkeypatch.delenv("TUTOR_RATE_LIMIT_PER_MINUTE", raising=False)
    assert Settings(_env_file=None).tutor_rate_limit_per_minute == 20


def test_mock_evaluation_is_off_by_default(monkeypatch):
    monkeypatch.delenv("USE_MOCK_EVALUATION", raising=False)
    assert Settings(_env_file=None).use_mock_evaluation is False
