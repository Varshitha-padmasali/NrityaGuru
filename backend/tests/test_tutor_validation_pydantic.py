"""Needs the real pydantic library: checks the schema constraints."""
import pytest

from app.services.tutor_validation import MalformedOutputError, validate_explanation
from tests.factories import make_reference, make_retrieval


def _retrieval():
    return make_retrieval([("river", [make_reference(record_id="m1", source_id="s1", mapping_source_id=None)])])


def _ok(**over):
    data = {
        "summary": "TEST",
        "concepts": [{"concept": "river", "supported": True, "explanation": "T", "source_ids": ["m1"]}],
        "source_ids": ["m1"],
    }
    data.update(over)
    return data


def test_valid_dict_is_accepted():
    assert validate_explanation(_ok(), _retrieval()).summary == "TEST"


def test_missing_summary_is_rejected():
    data = _ok()
    del data["summary"]
    with pytest.raises(MalformedOutputError):
        validate_explanation(data, _retrieval())


@pytest.mark.parametrize(
    "over",
    [
        {"summary": ""},
        {"summary": "x" * 1501},
        {"concepts": "not a list"},
        {"source_ids": [1, 2]},
        {"suggestions": ["x"] * 11},
    ],
)
def test_constraint_violations_are_rejected(over):
    with pytest.raises(MalformedOutputError):
        validate_explanation(_ok(**over), _retrieval())


def test_unexpected_extra_keys_are_ignored():
    assert validate_explanation(_ok(extra_field="x"), _retrieval()).summary == "TEST"
