"""Where Member 2 gets evaluation results from, and a MOCK stand-in for development.

TRUST RULE: evaluation evidence is fetched by session id from a trusted store. There is NO
endpoint that accepts evaluation results typed in by the browser, because a learner (or an
attacker) could then fake "evidence" and make the feedback say anything.

  EvaluationStore           interface the real integration must implement (Part 9: PostgreSQL)
  MockEvaluationStore       fixed, clearly labelled MOCK scenarios. Dev/demo only.
  UnavailableEvaluationStore  used when no real integration exists and mock is disabled

Everything the mock returns has is_mock=True and says MOCK in its warnings and descriptions.
"""
from typing import TYPE_CHECKING, Any, Protocol

from app.schemas.evaluation import (
    Deviation,
    DtwSummary,
    EvaluationResult,
    FrameInterval,
    LandmarkQuality,
    PredictedLabel,
)

if TYPE_CHECKING:
    from app.core.config import Settings

IS_MOCK = True  # kept for continuity with the Part 1 stub

MOCK_WARNING = "MOCK DATA: not produced by a real evaluation."


class EvaluationUnavailableError(RuntimeError):
    """The evaluation integration is not configured or not reachable."""


class EvaluationStore(Protocol):
    def get(self, db: Any, session_id: str) -> EvaluationResult | None:
        """Return the stored result for this session, or None if there is none.
        `db` is a SQLAlchemy session; stores that do not use the database ignore it."""
        ...


def _base(session_id: str, **over) -> EvaluationResult:
    data = dict(
        schema_version="1.0",
        session_id=session_id,
        reference_mudra_id="mudra_pataka",
        expected_labels=["pataka"],
        warnings=[MOCK_WARNING],
        is_mock=True,
    )
    data.update(over)
    return EvaluationResult(**data)


def _good_landmarks() -> LandmarkQuality:
    return LandmarkQuality(
        hand_detection_rate=0.97, pose_detection_rate=0.95,
        frames_total=90, frames_analysed=88, reliable=True,
    )


def _dtw(within: bool) -> DtwSummary:
    return DtwSummary(
        distance=12.5, normalized_distance=0.14 if within else 0.42, threshold=0.3,
        within_threshold=within, reference_sequence_id="MOCK-SEQ-001", feature_schema_version="MOCK-1",
    )


def _scenario_match(sid):
    return _base(
        sid,
        predicted_labels=[PredictedLabel(label="pataka", confidence=0.92,
                                         interval=FrameInterval(start_frame=0, end_frame=89))],
        dtw=_dtw(True), landmark_quality=_good_landmarks(),
    )


def _scenario_deviation(sid):
    return _base(
        sid,
        predicted_labels=[PredictedLabel(label="pataka", confidence=0.71)],
        dtw=_dtw(False), landmark_quality=_good_landmarks(),
        deviations=[Deviation(
            deviation_id="MOCK-D1", kind="finger", body_part="index_finger",
            description="MOCK: index finger angle differs from the reference.",
            measured_value=28.0, reference_value=5.0, unit="degrees", severity="moderate",
            interval=FrameInterval(start_frame=10, end_frame=40), source_module="landmark_rules",
        )],
    )


def _scenario_mismatch(sid):
    return _base(
        sid,
        predicted_labels=[PredictedLabel(label="tripataka", confidence=0.64)],
        dtw=_dtw(False), landmark_quality=_good_landmarks(),
    )


def _scenario_poor_landmarks(sid):
    return _base(
        sid,
        predicted_labels=[PredictedLabel(label="pataka", confidence=0.4)],
        landmark_quality=LandmarkQuality(hand_detection_rate=0.31, reliable=False,
                                         notes=["MOCK: hand often out of frame"]),
    )


def _scenario_empty(sid):
    return _base(sid)  # nothing usable: no predictions, no DTW, no deviations, no landmark info


MOCK_SCENARIOS = {
    "mock-session-match": _scenario_match,
    "mock-session-deviation": _scenario_deviation,
    "mock-session-mismatch": _scenario_mismatch,
    "mock-session-poor-landmarks": _scenario_poor_landmarks,
    "mock-session-empty": _scenario_empty,
}


class MockEvaluationStore:
    """Builds a fresh MOCK result per call, so callers cannot mutate shared state."""

    def get(self, db: Any, session_id: str) -> EvaluationResult | None:
        builder = MOCK_SCENARIOS.get(session_id)
        return builder(session_id) if builder else None


class UnavailableEvaluationStore:
    def get(self, db: Any, session_id: str) -> EvaluationResult | None:
        raise EvaluationUnavailableError("The evaluation integration is not configured.")


def build_evaluation_store(settings: "Settings") -> EvaluationStore:
    if settings.use_mock_evaluation:
        return MockEvaluationStore()
    from app.integrations.database_evaluation_store import DatabaseEvaluationStore

    return DatabaseEvaluationStore()


def get_mock_evaluation_result(session_id: str) -> EvaluationResult | None:
    """Convenience for tests/demos."""
    return MockEvaluationStore().get(None, session_id)
