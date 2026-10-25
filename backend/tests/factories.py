"""Builders for TEST DATA. Everything here is labelled mock data, not Bharatanatyam knowledge."""
from app.core.enums import MatchType, VerificationStatus
from app.schemas.concepts import ConceptSupportStatus, ConceptType, ExtractedConcept, Span
from app.schemas.knowledge import (
    ConceptRetrieval,
    RetrievalResponse,
    RetrievedReference,
    SourceOut,
)

V = VerificationStatus


def make_source(sid="src_test", name="TEST SOURCE (test data)"):
    return SourceOut(id=sid, source_name=name, source_type="test")


def make_reference(
    record_id="m_test1",
    name="TestMudra",
    status=V.VERIFIED,
    source_id="src_test",
    mapping_source_id="src_map",
    meaning="TEST MEANING",
    usage=None,
    limitations=None,
):
    return RetrievedReference(
        record_type="mudra",
        record_id=record_id,
        name=name,
        category="TEST",
        meaning=meaning,
        usage=usage or [],
        match_type=MatchType.CONCEPT_MAPPING,
        mapping_ids=["map_test"],
        relationships=["TEST relationship"],
        verification_status=status,
        source=make_source(source_id) if source_id else None,
        mapping_source=make_source(mapping_source_id) if mapping_source_id else None,
        limitations=limitations or [],
    )


def make_concept(text, ctype=ConceptType.OTHER):
    norm = text.lower()
    return ExtractedConcept(
        text=text,
        normalized=norm,
        concept_type=ctype,
        lookup_keys=[norm],
        mentions=[Span(start=0, end=len(text))],
        reason="test",
    )


def make_retrieval(concepts, original_text="TEST INPUT"):
    """concepts: list of (concept_text, [RetrievedReference, ...])"""
    items = []
    for text, refs in concepts:
        items.append(
            ConceptRetrieval(
                concept=make_concept(text),
                status=ConceptSupportStatus.SUPPORTED if refs else ConceptSupportStatus.UNSUPPORTED,
                references=refs,
                contains_unverified=any(r.verification_status != V.VERIFIED for r in refs),
            )
        )
    supported = sum(1 for _, refs in concepts if refs)
    return RetrievalResponse(
        original_text=original_text,
        include_unverified=True,
        include_keyword_matches=False,
        concepts=items,
        supported_count=supported,
        unsupported_count=len(concepts) - supported,
    )


class FakeGenerator:
    """Stand-in for Gemini. Returns canned text or raises a canned error."""

    def __init__(self, output=None, error=None):
        self.output, self.error, self.calls, self.last_prompt = output, error, 0, None

    def generate(self, *, system_instruction, prompt):
        self.calls += 1
        self.last_prompt = prompt
        if self.error:
            raise self.error
        return self.output


# ---------- evaluation contract builders (TEST DATA) ----------
from app.schemas.evaluation import (  # noqa: E402
    Deviation,
    DtwSummary,
    EvaluationResult,
    LandmarkQuality,
    PredictedLabel,
    ReferenceInfo,
)


def make_eval_result(**over):
    data = dict(
        schema_version="1.0",
        session_id="test-session-1",
        reference_mudra_id="m_test1",
        expected_labels=["testmudra"],
        predicted_labels=[PredictedLabel(label="testmudra", confidence=0.9)],
        dtw=DtwSummary(distance=10.0, normalized_distance=0.1),
        landmark_quality=LandmarkQuality(hand_detection_rate=0.95, reliable=True),
    )
    data.update(over)
    return EvaluationResult(**data)


def make_reference_info(**over):
    data = dict(
        record_type="mudra", record_id="m_test1", name="TestMudra", category="TEST",
        practice_instructions="TEST INSTRUCTIONS", instructions_available=True,
        verification_status=VerificationStatus.VERIFIED,
    )
    data.update(over)
    return ReferenceInfo(**data)


def make_deviation(**over):
    data = dict(deviation_id="d-1", kind="finger", body_part="index_finger", description="TEST deviation")
    data.update(over)
    return Deviation(**data)


# ---------- feedback helpers (TEST DATA) ----------
from app.integrations.evaluation_stub import MockEvaluationStore  # noqa: E402
from app.schemas.evaluation import EvidenceSource  # noqa: E402
from app.services.evaluation_evidence import build_evidence  # noqa: E402


def make_evidence(session_id="mock-session-match", *, instructions=None,
                  status=VerificationStatus.SOURCE_CITED):
    """ValidatedEvidence built from one of the MOCK scenarios."""
    result = MockEvaluationStore().get(None, session_id)
    ref = make_reference_info(
        record_id="mudra_pataka", name="Pataka", verification_status=status,
        practice_instructions=instructions, instructions_available=bool(instructions),
    )
    return build_evidence(result, ref, source=EvidenceSource.MOCK_STORE)


# ---------- persistence / logging helpers (TEST DATA) ----------
import contextlib  # noqa: E402
import copy  # noqa: E402
import logging  # noqa: E402

from app.repositories.errors import PersistenceError  # noqa: E402


class InMemoryFeedbackStore:
    """Stand-in for the PostgreSQL feedback store."""

    def __init__(self, fail_save=False, fail_latest=False):
        self.rows, self.fail_save, self.fail_latest = [], fail_save, fail_latest

    def latest(self, db, session_id):
        if self.fail_latest:
            raise PersistenceError("read failed")
        mine = [r for r in self.rows if r.session_id == session_id]
        if not mine:
            return None
        stored = copy.deepcopy(mine[-1])
        stored.saved, stored.reused = True, True
        return stored

    def save(self, db, result):
        if self.fail_save:
            raise PersistenceError("write failed")
        self.rows.append(copy.deepcopy(result))


@contextlib.contextmanager
def capture_logs():
    """Collect every log message (logging is force-enabled so the test cannot pass vacuously)."""
    messages: list[str] = []

    class _Handler(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    handler = _Handler(level=logging.DEBUG)
    root = logging.getLogger()
    old_level, old_disable = root.level, logging.root.manager.disable
    logging.disable(logging.NOTSET)
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield messages
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
        logging.disable(old_disable)
