import pytest

from app.core.enums import MatchType
from app.db.models import ConceptMapping, Mudra, Source, VerificationStatus
from app.db.seed import load_seed
from app.schemas.concepts import ConceptSupportStatus
from app.services.knowledge_retrieval import MULTIPLE_NOTE, retrieve_for_text
from app.services.text_processing import InputValidationError

V = VerificationStatus


def _concept(resp, norm):
    return next(c for c in resp.concepts if c.concept.normalized == norm)


def _src(db):
    db.add(Source(id="src_t", source_name="TEST SOURCE (test data)", source_type="test"))
    db.flush()


def _mudra(db, mid, name, status=V.VERIFIED, **extra):
    db.add(Mudra(id=mid, name=name, category="TEST", source_id="src_t",
                 verification_status=status, **extra))
    db.flush()


def _map(db, mapid, concept, mudra_id, status=V.VERIFIED):
    db.add(ConceptMapping(id=mapid, concept=concept, mudra_id=mudra_id,
                          interpretation_type="TEST", source_id="src_t",
                          verification_status=status))
    db.flush()


def test_source_cited_seeded_records_are_visible_by_default(db_session):
    load_seed(db_session)
    resp = retrieve_for_text(db_session, "The river and the clouds")
    assert resp.supported_count == 2
    assert resp.unsupported_count == 0


@pytest.mark.parametrize(
    ("text", "supported"),
    [
        ("The river flows.", {"river": "mudra_pataka"}),
        ("A tree and a crown.", {"tree": "mudra_tripataka", "crown": "mudra_tripataka"}),
        ("The lotus blooms by the river.", {"river": "mudra_pataka"}),
        (
            "Krishna is singing and dancing in the garden.",
            {"sing": "mudra_hamsasya", "dance": "mudra_allapadma"},
        ),
    ],
)
def test_audit_sentence_examples_use_only_explicit_seeded_evidence(db_session, text, supported):
    load_seed(db_session)
    response = retrieve_for_text(db_session, text, include_unverified=True)
    for concept, mudra_id in supported.items():
        assert _concept(response, concept).references[0].record_id == mudra_id
    if text.startswith("Krishna"):
        assert _concept(response, "krishna").status == ConceptSupportStatus.UNSUPPORTED
        assert _concept(response, "garden").status == ConceptSupportStatus.UNSUPPORTED


def test_explicit_mapping_returns_reference_with_provenance(db_session):
    load_seed(db_session)
    resp = retrieve_for_text(db_session, "The river", include_unverified=True)
    ref = _concept(resp, "river").references[0]
    assert ref.record_id == "mudra_pataka"
    assert ref.match_type == MatchType.CONCEPT_MAPPING
    assert ref.mapping_ids == ["map_river_pataka"]
    assert ref.verification_status == V.SOURCE_CITED
    assert ref.source.source_name.startswith("The Mirror of Gesture")
    assert ref.mapping_source.id == "src_mirror_of_gesture_1917"
    assert any("not been teacher-verified" in n for n in ref.limitations)
    assert ref.reference_media_path == "/static/mudras/pataka.png"
    assert _concept(resp, "river").contains_unverified is True


def test_plural_concept_found_through_singular_key(db_session):
    load_seed(db_session)
    resp = retrieve_for_text(db_session, "clouds", include_unverified=True)
    assert _concept(resp, "cloud").references[0].mapping_ids == ["map_cloud_pataka"]


def test_listed_usage_without_mapping(db_session):
    load_seed(db_session)
    resp = retrieve_for_text(db_session, "horse", include_unverified=True)
    ref = _concept(resp, "horse").references[0]
    assert ref.match_type == MatchType.CONCEPT_MAPPING
    assert ref.mapping_ids == ["map_horse_pataka"]
    assert ref.mapping_source.id == "src_mirror_of_gesture_1917"


def test_keyword_matching_needs_opt_in(db_session):
    load_seed(db_session)
    without = retrieve_for_text(db_session, "hill", include_unverified=True)
    assert _concept(without, "hill").status == ConceptSupportStatus.UNSUPPORTED
    with_kw = retrieve_for_text(
        db_session, "hill", include_unverified=True, include_keyword_matches=True
    )
    ref = _concept(with_kw, "hill").references[0]
    assert ref.match_type == MatchType.USAGE_KEYWORD
    assert any("weaker" in n for n in ref.limitations)


def test_exact_name_retrieval(db_session):
    load_seed(db_session)
    resp = retrieve_for_text(db_session, "show pataka", include_unverified=True)
    assert _concept(resp, "pataka").references[0].match_type == MatchType.EXACT_NAME


def test_alternate_name_retrieval(db_session):
    _src(db_session)
    _mudra(db_session, "m1", "TestMudra", alternate_names=["aliasword"])
    resp = retrieve_for_text(db_session, "aliasword")
    assert _concept(resp, "aliasword").references[0].match_type == MatchType.ALTERNATE_NAME


def test_multiple_interpretations_returned_with_note(db_session):
    _src(db_session)
    _mudra(db_session, "m1", "TestOne")
    _mudra(db_session, "m2", "TestTwo")
    _map(db_session, "map1", "moon", "m1")
    _map(db_session, "map2", "moon", "m2")
    c = _concept(retrieve_for_text(db_session, "moon"), "moon")
    assert [r.record_id for r in c.references] == ["m1", "m2"]
    assert c.note == MULTIPLE_NOTE
    assert c.contains_unverified is False


def test_source_cited_target_is_visible_with_source_cited_status(db_session):
    _src(db_session)
    _mudra(db_session, "m1", "TestOne", status=V.SOURCE_CITED)
    _map(db_session, "map1", "lamp", "m1", status=V.VERIFIED)
    resp = retrieve_for_text(db_session, "lamp")
    concept = _concept(resp, "lamp")
    assert concept.status == ConceptSupportStatus.SUPPORTED
    assert concept.references[0].verification_status == V.SOURCE_CITED


def test_reference_status_is_weakest_of_record_and_mapping(db_session):
    _src(db_session)
    _mudra(db_session, "m1", "TestOne", status=V.VERIFIED)
    _map(db_session, "map1", "lamp", "m1", status=V.SOURCE_CITED)
    resp = retrieve_for_text(db_session, "lamp", include_unverified=True)
    assert _concept(resp, "lamp").references[0].verification_status == V.SOURCE_CITED


def test_missing_image_file_is_dropped_and_flagged(db_session, tmp_path):
    _src(db_session)
    _mudra(db_session, "m1", "TestOne", reference_image_path="missing.png")
    _map(db_session, "map1", "lamp", "m1")
    ref = _concept(retrieve_for_text(db_session, "lamp", assets_dir=tmp_path), "lamp").references[0]
    assert ref.reference_media_path is None
    assert any("not found" in n for n in ref.limitations)


def test_existing_image_file_is_kept(db_session, tmp_path):
    (tmp_path / "ok.png").write_bytes(b"x")
    _src(db_session)
    _mudra(db_session, "m1", "TestOne", reference_image_path="ok.png")
    _map(db_session, "map1", "lamp", "m1")
    ref = _concept(retrieve_for_text(db_session, "lamp", assets_dir=tmp_path), "lamp").references[0]
    assert ref.reference_media_path == "/static/ok.png"


def test_path_traversal_is_not_treated_as_available(db_session, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("x")
    assets = tmp_path / "assets"
    assets.mkdir()
    _src(db_session)
    _mudra(db_session, "m1", "TestOne", reference_image_path="../secret.txt")
    _map(db_session, "map1", "lamp", "m1")
    ref = _concept(retrieve_for_text(db_session, "lamp", assets_dir=assets), "lamp").references[0]
    assert ref.reference_media_path is None


def test_unsupported_concept_gets_honest_note(db_session):
    resp = retrieve_for_text(db_session, "Krishna is dancing")
    k = _concept(resp, "krishna")
    assert k.status == ConceptSupportStatus.UNSUPPORTED
    assert "does not prove" in k.note
    assert resp.disclaimer


@pytest.mark.parametrize("bad", ["", "   ", "1234"])
def test_invalid_input_raises(db_session, bad):
    with pytest.raises(InputValidationError):
        retrieve_for_text(db_session, bad)
