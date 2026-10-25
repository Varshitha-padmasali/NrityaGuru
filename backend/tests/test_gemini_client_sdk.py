"""Needs the real google-genai SDK (skipped automatically if it is not installed)."""
import pytest

pytest.importorskip("google.genai")

from app.services.gemini_client import GeminiEmptyResponseError, GeminiRateLimitError, GeminiTextGenerator


class _Resp:
    def __init__(self, text):
        self.text = text


class _Models:
    def __init__(self, behaviour):
        self.behaviour, self.kwargs = behaviour, None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return _Resp(self.behaviour)


class _Client:
    def __init__(self, behaviour):
        self.models = _Models(behaviour)


class _RateLimited(Exception):
    code = 429


def _gen(behaviour, **kw):
    return GeminiTextGenerator(api_key="fake-test-key", model="test-model", client=_Client(behaviour), **kw)


def test_returns_text_and_passes_model_and_prompt():
    gen = _gen('{"ok": true}')
    assert gen.generate(system_instruction="SYS", prompt="PROMPT") == '{"ok": true}'
    sent = gen._client.models.kwargs
    assert sent["model"] == "test-model" and sent["contents"] == "PROMPT"


def test_sampling_parameters_are_not_sent():
    gen = _gen("{}")
    gen.generate(system_instruction="SYS", prompt="P")
    config = gen._client.models.kwargs["config"]
    for name in ("temperature", "top_p", "top_k"):
        assert getattr(config, name, None) is None


def test_json_mime_type_and_system_instruction_are_set():
    gen = _gen("{}")
    gen.generate(system_instruction="SYS", prompt="P")
    config = gen._client.models.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.system_instruction == "SYS"


def test_thinking_level_is_sent_only_when_configured():
    gen = _gen("{}", thinking_level="LOW")
    gen.generate(system_instruction="S", prompt="P")
    assert gen._client.models.kwargs["config"].thinking_config is not None
    gen2 = _gen("{}")
    gen2.generate(system_instruction="S", prompt="P")
    assert gen2._client.models.kwargs["config"].thinking_config is None


def test_empty_text_raises_empty_response():
    with pytest.raises(GeminiEmptyResponseError):
        _gen("   ").generate(system_instruction="S", prompt="P")


def test_sdk_errors_are_translated():
    with pytest.raises(GeminiRateLimitError):
        _gen(_RateLimited("x")).generate(system_instruction="S", prompt="P")


def test_failed_calls_log_only_the_exception_type_and_code(caplog):
    import logging

    class _Boom(Exception):
        code = 500

    caplog.set_level(logging.DEBUG)
    with pytest.raises(Exception):
        _gen(_Boom("key=TOPSECRET password=hunter2")).generate(system_instruction="S", prompt="P")
    assert caplog.records, "nothing was logged"
    assert "TOPSECRET" not in caplog.text and "hunter2" not in caplog.text
