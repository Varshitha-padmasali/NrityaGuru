"""Thin wrapper around the official Google Gen AI SDK (`google-genai`).

This is the ONLY module that talks to Gemini. It never logs prompts, responses or keys,
and it turns every failure into a small set of safe exceptions.

SDK facts used (verified against Google's current docs/release notes, Oct 2026):
  - package `google-genai`; `genai.Client(api_key=..., http_options=types.HttpOptions(timeout=ms))`
  - `client.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(...))`
  - `system_instruction` and `response_mime_type="application/json"` in the config
  - `thinking_config=types.ThinkingConfig(thinking_level="LOW"|"MEDIUM"|"HIGH")`
  - temperature / top_p / top_k are deprecated and ignored on current models: NOT sent
  - errors: google.genai.errors.APIError (.code, .status), ClientError (4xx), ServerError (5xx)
Not verified by execution: this environment had no network access or API key.
"""
import logging
import time
from typing import TYPE_CHECKING, Any, Protocol

from app.core.enums import TutorFallbackReason

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    reason: TutorFallbackReason = TutorFallbackReason.UNAVAILABLE


class GeminiNotConfiguredError(GeminiError):
    reason = TutorFallbackReason.NOT_CONFIGURED


class GeminiTimeoutError(GeminiError):
    reason = TutorFallbackReason.TIMEOUT


class GeminiRateLimitError(GeminiError):
    reason = TutorFallbackReason.RATE_LIMITED


class GeminiUnavailableError(GeminiError):
    reason = TutorFallbackReason.UNAVAILABLE


class GeminiAuthOrModelError(GeminiError):
    reason = TutorFallbackReason.AUTH_OR_MODEL_ERROR


class GeminiRequestError(GeminiError):
    reason = TutorFallbackReason.REQUEST_ERROR


class GeminiEmptyResponseError(GeminiError):
    reason = TutorFallbackReason.EMPTY_RESPONSE


class TextGenerator(Protocol):
    def generate(self, *, system_instruction: str, prompt: str) -> str: ...


_STATUS_TO_ERROR = {
    "RESOURCE_EXHAUSTED": GeminiRateLimitError,
    "UNAVAILABLE": GeminiUnavailableError,
    "INTERNAL": GeminiUnavailableError,
    "DEADLINE_EXCEEDED": GeminiTimeoutError,
    "NOT_FOUND": GeminiAuthOrModelError,
    "PERMISSION_DENIED": GeminiAuthOrModelError,
    "UNAUTHENTICATED": GeminiAuthOrModelError,
    "INVALID_ARGUMENT": GeminiRequestError,
}


def classify_error(exc: BaseException) -> GeminiError:
    """Map any exception from the SDK/network to a safe GeminiError (no upstream text kept)."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    code = getattr(exc, "code", None)

    if isinstance(code, int):
        if code == 429:
            return GeminiRateLimitError("Gemini rate limit reached.")
        if code in (401, 403, 404):
            return GeminiAuthOrModelError("Gemini rejected the API key or model name.")
        if code in (408, 504):
            return GeminiTimeoutError("Gemini request timed out.")
        if 500 <= code < 600:
            return GeminiUnavailableError("Gemini is temporarily unavailable.")
        if 400 <= code < 500:
            return GeminiRequestError("Gemini rejected the request.")

    status = getattr(exc, "status", None)
    if isinstance(status, str) and status in _STATUS_TO_ERROR:
        return _STATUS_TO_ERROR[status]("Gemini returned an error.")

    if any("Timeout" in n for n in names):
        return GeminiTimeoutError("Gemini request timed out.")
    return GeminiUnavailableError("Gemini could not be reached.")


class GeminiTextGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        fallback_model: str | None = None,
        timeout_seconds: float = 30.0,
        thinking_level: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise GeminiNotConfiguredError("GEMINI_API_KEY is not set.")
        self._model = model
        self._fallback_model = fallback_model if fallback_model and fallback_model != model else None
        self._thinking_level = thinking_level
        if client is None:
            try:
                from google import genai
                from google.genai import types
            except ImportError:
                raise GeminiNotConfiguredError("The google-genai package is not installed.") from None
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
            )
        self._client = client

    def _build_config(self, system_instruction: str) -> Any:
        try:
            from google.genai import types
        except ImportError:
            raise GeminiNotConfiguredError("The google-genai package is not installed.") from None
        kwargs: dict[str, Any] = {
            "system_instruction": system_instruction,
            "response_mime_type": "application/json",
        }
        if self._thinking_level:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=self._thinking_level)
        return types.GenerateContentConfig(**kwargs)

    def generate(self, *, system_instruction: str, prompt: str) -> str:
        config = self._build_config(system_instruction)
        models = [(self._model, 2)]
        if self._fallback_model:
            # The fallback also gets one bounded retry for provider 5xx/timeouts.
            models.append((self._fallback_model, 2))

        last_error: GeminiError | None = None
        for model_index, (model, max_attempts) in enumerate(models):
            for attempt in range(max_attempts):
                try:
                    response = self._client.models.generate_content(
                        model=model, contents=prompt, config=config
                    )
                    try:
                        text = response.text
                    except Exception:  # noqa: BLE001 - blocked response varies by SDK version
                        text = None
                    if not text or not text.strip():
                        raise GeminiEmptyResponseError("Gemini returned no text.")
                    if model_index:
                        logger.info("Gemini primary model unavailable; fallback model responded.")
                    return text
                except GeminiEmptyResponseError:
                    raise
                except GeminiError:
                    raise
                except Exception as exc:  # noqa: BLE001 - never retain provider response text
                    error = classify_error(exc)
                    retryable = isinstance(error, (GeminiTimeoutError, GeminiUnavailableError))
                    logger.warning(
                        "Gemini call failed: %s (code=%s, model_attempt=%s, attempt=%s)",
                        type(exc).__name__, getattr(exc, "code", None), model_index + 1, attempt + 1,
                    )
                    last_error = error
                    if retryable and attempt < max_attempts - 1:
                        time.sleep(0.5 * (2**attempt))
                        continue
                    # A 429 can be specific to one model. Try the configured fallback
                    # once before reporting a provider/quota failure to the application.
                    if (retryable or isinstance(error, GeminiRateLimitError)) and model_index == 0 and self._fallback_model:
                        logger.info("Retrying Gemini request with the configured fallback Flash model.")
                        break
                    raise error from None

        if last_error:
            raise last_error
        raise GeminiUnavailableError("Gemini could not be reached.")


def build_text_generator(settings: "Settings") -> GeminiTextGenerator:
    """Raises GeminiNotConfiguredError if the key or SDK is missing."""
    if not settings.gemini_configured:
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not set.")
    return GeminiTextGenerator(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        fallback_model=settings.gemini_fallback_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        thinking_level=settings.gemini_thinking_level,
    )
