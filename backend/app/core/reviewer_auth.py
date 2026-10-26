"""Narrow helper for reading the reference reviewer secret."""
import hmac

from app.core.config import Settings


def reviewer_token_matches(provided: str | None, settings: Settings) -> bool:
    if not provided or not settings.reference_review_configured:
        return False
    return hmac.compare_digest(
        provided,
        settings.reference_review_token.get_secret_value(),
    )
