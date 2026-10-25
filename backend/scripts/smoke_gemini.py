"""Quick live check that your key, model id and SDK work.  Run from backend/:
    python -m scripts.smoke_gemini
Sends one tiny prompt (no learner data). Prints only success/failure, never the key."""
from app.core.config import get_settings
from app.services.gemini_client import GeminiError, build_text_generator


def main() -> None:
    settings = get_settings()
    print("model:", settings.gemini_model)
    try:
        generator = build_text_generator(settings)
        text = generator.generate(
            system_instruction="Reply with one JSON object only.",
            prompt='Return {"ok": true}.',
        )
    except GeminiError as exc:
        print("FAILED:", exc.reason.value, "-", exc)
        raise SystemExit(1)
    print("OK. Model replied with", len(text), "characters.")


if __name__ == "__main__":
    main()
