from types import SimpleNamespace

from app.core.enums import MatchType, VerificationStatus
from app.services.knowledge_matching import build_limitations, match_record, weakest_status

V = VerificationStatus


def _rec(name="TestMudra", aliases=None, usage=None):
    return SimpleNamespace(name=name, alternate_names=aliases or [], usage=usage or [])


def test_exact_name_match_ignores_case_and_spacing():
    assert match_record(_rec("Pataka"), ["  PATAKA "]) == MatchType.EXACT_NAME


def test_alternate_name_match():
    rec = _rec("Pataka", aliases=["Flag Hand"])
    assert match_record(rec, ["flag hand"]) == MatchType.ALTERNATE_NAME


def test_listed_usage_match():
    rec = _rec(usage=["river", "sprinkling water"])
    assert match_record(rec, ["river"]) == MatchType.USAGE_LISTED


def test_keyword_match_is_opt_in():
    rec = _rec(usage=["sprinkling water"])
    assert match_record(rec, ["water"]) is None
    assert match_record(rec, ["water"], include_keyword=True) == MatchType.USAGE_KEYWORD


def test_keyword_must_be_a_whole_word():
    rec = _rec(usage=["sprinkling water"])
    assert match_record(rec, ["wat"], include_keyword=True) is None


def test_strongest_match_across_keys_wins():
    rec = _rec("Pataka", usage=["horse"])
    assert match_record(rec, ["horse", "pataka"]) == MatchType.EXACT_NAME


def test_no_match_returns_none():
    assert match_record(_rec("Pataka", usage=["river"]), ["tiger"], include_keyword=True) is None


def test_record_without_alias_or_usage_attributes_is_handled():
    movement_like = SimpleNamespace(name="TestAdavu")  # movements have no aliases/usage
    assert match_record(movement_like, ["testadavu"]) == MatchType.EXACT_NAME
    assert match_record(movement_like, ["other"]) is None


def test_empty_keys_never_match():
    assert match_record(_rec("Pataka"), ["", "   "]) is None


def test_weakest_status():
    assert weakest_status([V.VERIFIED, V.SOURCE_CITED]) == V.SOURCE_CITED
    assert weakest_status([V.VERIFIED, V.VERIFIED]) == V.VERIFIED
    assert weakest_status([V.SOURCE_CITED, V.UNVERIFIED]) == V.UNVERIFIED


def _limits(**over):
    args = dict(
        status=V.VERIFIED, has_source=True, media_listed=True,
        media_available=True, has_instructions=True, match_type=None,
    )
    args.update(over)
    status = args.pop("status")
    return build_limitations(status, **args)


def test_fully_complete_verified_record_has_no_limitations():
    assert _limits() == []


def test_unverified_and_source_cited_are_flagged():
    assert any("no supporting source" in n for n in _limits(status=V.UNVERIFIED))
    assert any("not been teacher-verified" in n for n in _limits(status=V.SOURCE_CITED))


def test_missing_source_image_and_instructions_are_flagged():
    notes = _limits(has_source=False, media_listed=False, has_instructions=False)
    assert any("No source" in n for n in notes)
    assert any("No reference image" in n for n in notes)
    assert any("No verified practice instructions" in n for n in notes)


def test_listed_but_missing_file_is_flagged():
    assert any("not found" in n for n in _limits(media_available=False))


def test_weak_match_types_are_explained():
    assert any("listed usages" in n for n in _limits(match_type=MatchType.USAGE_LISTED))
    assert any("weaker" in n for n in _limits(match_type=MatchType.USAGE_KEYWORD))
