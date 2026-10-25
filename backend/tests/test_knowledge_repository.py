import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import ConceptMapping, Mudra, Source, VerificationStatus
from app.repositories import knowledge_repository as repo

V = VerificationStatus


def _source(db, sid="src_test"):
    db.add(Source(id=sid, source_name="TEST SOURCE (test data)", source_type="test"))
    db.flush()


def _mudra(db, mid, name, status, category="TEST_CATEGORY"):
    db.add(
        Mudra(
            id=mid,
            name=name,
            category=category,
            meaning="TEST MEANING",
            source_id="src_test",
            verification_status=status,
        )
    )
    db.flush()


def test_verified_mudra_is_returned(db_session):
    _source(db_session)
    _mudra(db_session, "m1", "TestMudraOne", V.VERIFIED)
    assert repo.get_mudra(db_session, "m1").name == "TestMudraOne"


def test_unverified_and_source_cited_hidden_by_default(db_session):
    _source(db_session)
    _mudra(db_session, "m2", "TestMudraTwo", V.SOURCE_CITED)
    _mudra(db_session, "m3", "TestMudraThree", V.UNVERIFIED)
    assert repo.get_mudra(db_session, "m2") is None
    assert repo.get_mudra(db_session, "m3") is None
    assert repo.list_mudras(db_session) == []


def test_include_unverified_shows_everything(db_session):
    _source(db_session)
    _mudra(db_session, "m2", "TestMudraTwo", V.SOURCE_CITED)
    _mudra(db_session, "m3", "TestMudraThree", V.UNVERIFIED)
    assert repo.get_mudra(db_session, "m2", include_unverified=True) is not None
    assert len(repo.list_mudras(db_session, include_unverified=True)) == 2


def test_missing_mudra_returns_none(db_session):
    assert repo.get_mudra(db_session, "does_not_exist", include_unverified=True) is None


def test_get_by_name_is_case_insensitive(db_session):
    _source(db_session)
    _mudra(db_session, "m1", "TestMudraOne", V.VERIFIED)
    assert repo.get_mudra_by_name(db_session, "  testmudraone ") is not None
    assert repo.get_mudra_by_name(db_session, "nothing") is None


def test_list_filters_by_category(db_session):
    _source(db_session)
    _mudra(db_session, "m1", "A", V.VERIFIED, category="CAT_A")
    _mudra(db_session, "m2", "B", V.VERIFIED, category="CAT_B")
    result = repo.list_mudras(db_session, category="CAT_B")
    assert [m.id for m in result] == ["m2"]


def test_mapping_lookup_normalizes_and_supports_multiple(db_session):
    _source(db_session)
    _mudra(db_session, "m1", "A", V.VERIFIED)
    _mudra(db_session, "m2", "B", V.VERIFIED)
    for i, mid in enumerate(["m1", "m2"]):
        db_session.add(
            ConceptMapping(
                id=f"map{i}",
                concept="test concept",
                mudra_id=mid,
                interpretation_type="TEST",
                verification_status=V.VERIFIED,
            )
        )
    db_session.flush()
    found = repo.get_mappings_for_concept(db_session, "  Test   CONCEPT ")
    assert len(found) == 2
    assert repo.get_mappings_for_concept(db_session, "unmapped") == []


def test_mapping_requires_a_target(db_session):
    db_session.add(
        ConceptMapping(id="bad", concept="x", interpretation_type="TEST")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_foreign_key_is_enforced(db_session):
    db_session.add(
        Mudra(id="m1", name="A", category="C", source_id="no_such_source")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_duplicate_mudra_name_rejected(db_session):
    _source(db_session)
    _mudra(db_session, "m1", "Same", V.VERIFIED)
    db_session.add(Mudra(id="m2", name="Same", category="C"))
    with pytest.raises(IntegrityError):
        db_session.flush()
