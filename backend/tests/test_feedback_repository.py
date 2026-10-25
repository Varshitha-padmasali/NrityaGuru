"""Needs SQLAlchemy (not runnable in the authoring sandbox)."""
import pytest
from sqlalchemy import select

from app.db.models import FeedbackRecord, Mudra
from app.db.seed import load_seed
from app.repositories import session_repository as sessions
from app.repositories.errors import PersistenceError
from app.repositories.feedback_repository import SqlFeedbackStore
from app.services.feedback_service import FeedbackService
from tests.factories import make_evidence

SID = "mock-session-deviation"  # valid id format; used here only as a label for test rows


def _result(summary=None):
    r = FeedbackService(None).generate(make_evidence(SID))
    if summary:
        r.feedback.overall_summary = summary
    return r


@pytest.fixture
def seeded(db_session):
    load_seed(db_session)
    sessions.create_session(db_session, SID, mudra_id="mudra_pataka")
    return db_session


def test_save_then_latest_round_trip(seeded):
    store = SqlFeedbackStore()
    original = _result()
    store.save(seeded, original)
    loaded = store.latest(seeded, SID)
    assert loaded.feedback.overall_summary == original.feedback.overall_summary
    assert loaded.saved is True and loaded.reused is True
    assert loaded.fallback_reason == original.fallback_reason
    assert [e.evidence_id for e in loaded.supporting_evidence] == [e.evidence_id for e in original.supporting_evidence]


def test_latest_returns_the_newest_row(seeded):
    store = SqlFeedbackStore()
    store.save(seeded, _result("first"))
    store.save(seeded, _result("second"))
    assert store.latest(seeded, SID).feedback.overall_summary == "second"


def test_no_feedback_is_none(seeded):
    assert SqlFeedbackStore().latest(seeded, SID) is None


def test_metadata_columns_are_filled(seeded):
    SqlFeedbackStore().save(seeded, _result())
    row = seeded.scalars(select(FeedbackRecord)).one()
    assert row.mode == "evidence_only" and row.fallback_reason == "not_configured"
    assert row.is_mock is True and row.evidence_level == "sufficient"


def test_a_corrupt_stored_row_is_ignored_not_trusted(seeded):
    seeded.add(FeedbackRecord(session_id=SID, mode="ai", evidence_level="sufficient", result_json={"bad": 1}))
    seeded.commit()
    assert SqlFeedbackStore().latest(seeded, SID) is None


def test_saving_for_a_missing_session_raises_and_leaves_the_session_usable(db_session):
    load_seed(db_session)
    with pytest.raises(PersistenceError) as e:
        SqlFeedbackStore().save(db_session, _result())
    assert "foreign key" not in str(e.value).lower()  # no SQL internals
    assert db_session.get(Mudra, "mudra_pataka") is not None  # rolled back, still usable
