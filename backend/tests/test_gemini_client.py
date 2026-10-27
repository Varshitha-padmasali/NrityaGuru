import pytest

from app.core.enums import TutorFallbackReason as R
from app.services.gemini_client import (
    GeminiAuthOrModelError,
    GeminiNotConfiguredError,
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiTextGenerator,
    GeminiTimeoutError,
    GeminiUnavailableError,
    classify_error,
)


class _Err(Exception):
    def __init__(self, code=None, status=None):
        super().__init__("upstream text that must never be kept: key=SECRET123")
        self.code = code
        self.status = status


class ReadTimeout(Exception):  # name-based detection, like httpx.ReadTimeout
    pass


@pytest.mark.parametrize(
    "code,expected",
    [
        (429, GeminiRateLimitError),
        (401, GeminiAuthOrModelError),
        (403, GeminiAuthOrModelError),
        (404, GeminiAuthOrModelError),
        (408, GeminiTimeoutError),
        (504, GeminiTimeoutError),
        (500, GeminiUnavailableError),
        (503, GeminiUnavailableError),
        (400, GeminiRequestError),
        (422, GeminiRequestError),
    ],
)
def test_http_codes_are_classified(code, expected):
    assert isinstance(classify_error(_Err(code=code)), expected)


@pytest.mark.parametrize(
    "status,expected",
    [
        ("RESOURCE_EXHAUSTED", GeminiRateLimitError),
        ("DEADLINE_EXCEEDED", GeminiTimeoutError),
        ("NOT_FOUND", GeminiAuthOrModelError),
        ("UNAVAILABLE", GeminiUnavailableError),
    ],
)
def test_status_strings_are_classified_when_code_missing(status, expected):
    assert isinstance(classify_error(_Err(status=status)), expected)


def test_timeout_by_exception_name():
    assert isinstance(classify_error(ReadTimeout("x")), GeminiTimeoutError)


def test_unknown_exception_becomes_unavailable():
    assert isinstance(classify_error(RuntimeError("boom")), GeminiUnavailableError)


def test_classified_error_never_contains_upstream_text():
    assert "SECRET123" not in str(classify_error(_Err(code=500)))


def test_reasons_map_to_fallback_enum():
    assert classify_error(_Err(code=429)).reason == R.RATE_LIMITED
    assert classify_error(_Err(code=404)).reason == R.AUTH_OR_MODEL_ERROR


def test_missing_api_key_is_a_configuration_error():
    with pytest.raises(GeminiNotConfiguredError):
        GeminiTextGenerator(api_key="", model="m")


class _Response:
    text = '{"ok":true}'


class _Models:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _Client:
    def __init__(self, outcomes):
        self.models = _Models(outcomes)


def test_transient_gateway_timeout_is_retried_once(monkeypatch):
    client = _Client([_Err(code=504), _Response()])
    generator = GeminiTextGenerator(api_key="fake-test-key", model="m", client=client)
    monkeypatch.setattr(generator, "_build_config", lambda _: object())
    monkeypatch.setattr("app.services.gemini_client.time.sleep", lambda _: None)

    assert generator.generate(system_instruction="system", prompt="prompt") == '{"ok":true}'
    assert client.models.calls == 2


def test_auth_error_is_not_retried():
    client = _Client([_Err(code=403), _Response()])
    generator = GeminiTextGenerator(api_key="fake-test-key", model="m", client=client)

    with pytest.raises(GeminiAuthOrModelError):
        generator.generate(system_instruction="system", prompt="prompt")
    assert client.models.calls == 1
