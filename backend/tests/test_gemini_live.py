"""LIVE test: calls the real Gemini API. Skipped by default; run with:  pytest -m live
Needs GEMINI_API_KEY in backend/.env. It sends only tiny TEST data (no learner data)."""
import pytest

from app.core.config import get_settings
from app.services.tutor_service import build_tutor_service
from tests.factories import make_reference, make_retrieval

pytestmark = pytest.mark.live


def test_real_gemini_returns_grounded_explanation():
    settings = get_settings()
    if not settings.gemini_configured:
        pytest.skip("GEMINI_API_KEY is not set")
    ref = make_reference(record_id="m_test1", name="TestMudra", source_id="src_test", mapping_source_id=None)
    retrieval = make_retrieval([("river", [ref]), ("krishna", [])], original_text="river and Krishna")
    result = build_tutor_service(settings).explain(retrieval)
    # If this fails, fallback_reason tells you exactly why (bad model id, rate limit, ...).
    assert result.mode == "ai", f"fell back: {result.fallback_reason}"
