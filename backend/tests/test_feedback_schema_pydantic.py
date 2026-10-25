"""Needs the REAL pydantic (constraints). Not runnable in the authoring sandbox."""
import pytest
from pydantic import ValidationError

from app.schemas.feedback import FeedbackExplanation, FeedbackRequest

OK = {"overall_summary": "TEST", "observations": [{"text": "t", "evidence_ids": ["label"]}]}


def test_valid_output_parses_and_extra_keys_are_ignored():
    exp = FeedbackExplanation.model_validate({**OK, "limitations": ["ignored"], "surprise": 1})
    assert exp.overall_summary == "TEST"


@pytest.mark.parametrize(
    "bad",
    [
        {"overall_summary": ""},
        {"overall_summary": "x" * 1001},
        {"observations": [{"text": "t", "evidence_ids": []}]},
        {"observations": [{"text": "", "evidence_ids": ["a"]}]},
        {"observations": [{"text": "t", "evidence_ids": ["a"]}] * 9},
        {"suggestions": [{"text": "t", "evidence_ids": ["a"]}] * 6},
        {"observations": "not a list"},
    ],
)
def test_constraint_violations_are_rejected(bad):
    with pytest.raises(ValidationError):
        FeedbackExplanation.model_validate({**OK, **bad})


@pytest.mark.parametrize("bad", ["", "ab", "../etc/passwd", "a b c", "x" * 65, "id;drop"])
def test_request_rejects_bad_session_ids(bad):
    with pytest.raises(ValidationError):
        FeedbackRequest(session_id=bad)


def test_request_accepts_normal_ids():
    assert FeedbackRequest(session_id="9f1c2b7e-aaaa-bbbb-cccc-1234567890ab").session_id.startswith("9f1c")
