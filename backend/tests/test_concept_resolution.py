from app.db.models import ConceptMapping, Mudra, Source, VerificationStatus
from app.db.seed import load_seed
from app.schemas.concepts import ConceptSupportStatus
from app.services.concept_extraction import extract_concepts
from app.services.concept_resolution import resolve_concepts

V = VerificationStatus


def _by_norm(result):
    return {r.concept.normalized: r for r in result.concepts}


def test_source_cited_seeded_mappings_resolve_with_provenance_by_default(db_session):
    load_seed(db_session)
    result = resolve_concepts(db_session, extract_concepts("The river and the clouds"))
    assert result.supported_count == 2
    assert result.unsupported_count == 0
    assert all(r.contains_unverified for r in result.concepts)


def test_include_unverified_resolves_seeded_mappings(db_session):
    load_seed(db_session)
    extraction = extract_concepts("The river and the clouds, Krishna is dancing.")
    result = resolve_concepts(db_session, extraction, include_unverified=True)
    r = _by_norm(result)
    assert r["river"].status == ConceptSupportStatus.SUPPORTED
    assert r["river"].mudra_ids == ["mudra_pataka"]
    assert r["cloud"].mapping_ids == ["map_cloud_pataka"]  # found via singular key
    assert r["river"].contains_unverified is True
    assert r["krishna"].status == ConceptSupportStatus.UNSUPPORTED
    assert r["dance"].status == ConceptSupportStatus.SUPPORTED
    assert r["dance"].mudra_ids == ["mudra_allapadma"]
    assert result.supported_count == 3
    assert result.unsupported_count == 1


def _add_verified_mudra(db, mid, name):
    db.add(Mudra(id=mid, name=name, category="TEST", source_id="src_t", verification_status=V.VERIFIED))


def test_verified_mapping_is_returned_by_default(db_session):
    db_session.add(Source(id="src_t", source_name="TEST SOURCE (test data)", source_type="test"))
    db_session.flush()
    _add_verified_mudra(db_session, "m1", "TestMudra")
    db_session.flush()
    db_session.add(
        ConceptMapping(
            id="map1", concept="lamp", mudra_id="m1",
            interpretation_type="TEST", source_id="src_t", verification_status=V.VERIFIED,
        )
    )
    db_session.flush()
    result = resolve_concepts(db_session, extract_concepts("a lamp"))
    r = _by_norm(result)["lamp"]
    assert r.status == ConceptSupportStatus.SUPPORTED
    assert r.contains_unverified is False


def test_multiple_interpretations_are_all_returned(db_session):
    db_session.add(Source(id="src_t", source_name="TEST SOURCE (test data)", source_type="test"))
    db_session.flush()
    _add_verified_mudra(db_session, "m1", "TestOne")
    _add_verified_mudra(db_session, "m2", "TestTwo")
    db_session.flush()
    for i, mid in enumerate(["m1", "m2"]):
        db_session.add(
            ConceptMapping(
                id=f"map{i}", concept="moon", mudra_id=mid,
                interpretation_type="TEST", source_id="src_t", verification_status=V.VERIFIED,
            )
        )
    db_session.flush()
    r = _by_norm(resolve_concepts(db_session, extract_concepts("moon")))["moon"]
    assert r.mudra_ids == ["m1", "m2"]
    assert len(r.mapping_ids) == 2


def test_empty_extraction_resolves_to_empty_result(db_session):
    result = resolve_concepts(db_session, extract_concepts("is the of"))
    assert result.concepts == []
    assert result.supported_count == 0
    assert result.unsupported_count == 0
    assert result.warnings
