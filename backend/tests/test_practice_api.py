from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.db.seed import load_seed
from app.main import create_app
from app.repositories import session_repository
from app.schemas.evaluation import DtwSummary, EvaluationResult, FrameInterval, LandmarkQuality, PredictedLabel
from tests.factories import make_eval_result


def _client(db_session, settings=None):
    settings = settings or Settings(_env_file=None, allow_unverified_records=True)
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_practice_references_are_empty_until_real_model_and_reference_assets_exist(db_session):
    response = _client(db_session).get("/api/practice/references")
    assert response.status_code == 200
    assert response.json() == []


def test_progress_returns_persisted_results_without_fabricating_missing_fields(db_session):
    load_seed(db_session)
    session_repository.create_session(db_session, "progress-session-1", mudra_id="mudra_pataka")
    session_repository.save_evaluation_result(
        db_session,
        make_eval_result(
            session_id="progress-session-1",
            reference_mudra_id="mudra_pataka",
            expected_labels=["pataka"],
            predicted_labels=[PredictedLabel(label="pataka", confidence=0.91)],
            dtw=DtwSummary(distance=2.5, normalized_distance=0.2),
        ),
    )

    response = _client(db_session).get("/api/progress")
    assert response.status_code == 200
    item = response.json()["sessions"][0]
    assert item["session_id"] == "progress-session-1"
    assert item["reference_id"] == "mudra_pataka"
    assert item["reference_name"] == "Pataka"
    assert item["status"] == "evaluated"
    assert item["dtw_normalized"] == 0.2
    assert item["top_label"] == "pataka"
    assert item["top_confidence"] == 0.91
    assert item["feedback_summary"] is None


def test_progress_includes_unscored_session_without_fabricated_evaluation(db_session):
    load_seed(db_session)
    session_repository.create_session(db_session, "progress-session-2", mudra_id="mudra_pataka")
    item = _client(db_session).get("/api/progress").json()["sessions"][0]
    assert item["status"] == "created"
    assert item["dtw_normalized"] is None
    assert item["top_label"] is None


def test_practice_session_creation_and_empty_results(db_session):
    load_seed(db_session)
    client = _client(db_session)
    created = client.post("/api/practice/sessions", json={"reference_id": "mudra_pataka"})
    assert created.status_code == 201
    session = created.json()
    assert session["reference_id"] == "mudra_pataka"
    assert session["status"] == "created"
    results = client.get(f"/api/practice/sessions/{session['session_id']}/results")
    assert results.status_code == 200
    assert results.json()["result"] is None
    assert results.json()["session"]["status"] == "created"


def test_practice_session_rejects_missing_reference(db_session):
    response = _client(db_session).post("/api/practice/sessions", json={"reference_id": "not-a-real-target"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "reference_not_found"


def test_production_does_not_expose_globally_shared_progress(db_session):
    response = _client(db_session, Settings(_env_file=None, app_env="production")).get("/api/progress")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "user_auth_not_configured"


def test_reference_intake_requires_configured_reviewer_token(db_session):
    response = _client(db_session).post("/api/reference-sequences", json={
        "schema_version": 1,
        "id": "candidate-reference-001",
        "mudra_id": "mudra_pataka",
        "feature_schema": "hand_landmarks_v1",
        "evaluator_version": "0.2-prototype",
        "normalization": "wrist_relative_hand_scale",
        "feature_dimensions": 3,
        "frames": [[0.0, 0.1, 0.2]],
        "source": "consented performance",
        "performer_consent_reference": "consent-001",
        "review_status": "candidate",
    })
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "reference_intake_disabled"


def test_reference_ingestion_and_publication_requires_reviewer_auth(db_session):
    load_seed(db_session)
    settings = Settings(
        _env_file=None,
        reference_review_token="trusted-review-token",
        reference_reviewer_identity="dance-teacher-001",
    )
    client = _client(db_session, settings)
    payload = {
        "schema_version": 1,
        "id": "pataka-reference-001",
        "mudra_id": "mudra_pataka",
        "feature_schema": "hand_landmarks_v1",
        "evaluator_version": "0.1",
        "normalization": "wrist_relative_hand_scale",
        "feature_dimensions": 3,
        "frames": [[0.0, 0.1, 0.2], [0.1, 0.2, 0.3]],
        "source": "consented teacher recording",
        "performer_consent_reference": "consent-001",
        "review_status": "teacher_verified",
        "reviewer_identity": "dance-teacher-001",
        "reviewed_at": "2026-10-26T12:00:00Z",
        "threshold": 0.5,
    }
    denied = client.post("/api/reference-sequences", json=payload)
    assert denied.status_code == 403
    headers = {"X-Reference-Review-Token": "trusted-review-token"}
    saved = client.post("/api/reference-sequences", json=payload, headers=headers)
    assert saved.status_code == 201, saved.text
    assert saved.json()["review_status"] == "teacher_verified"
    assert len(client.get("/api/reference-sequences").json()) == 1


def test_saved_evaluation_is_adapted_for_frontend_without_inventing_metrics(db_session):
    load_seed(db_session)
    session_repository.create_session(db_session, "result-session-1", mudra_id="mudra_pataka")
    result = EvaluationResult(
        schema_version="1.0",
        session_id="result-session-1",
        reference_mudra_id="mudra_pataka",
        expected_labels=["Pataka"],
        predicted_labels=[PredictedLabel(
            label="Pataka", confidence=0.82,
            interval=FrameInterval(start_frame=0, end_frame=8),
        )],
        dtw=DtwSummary(distance=1.2, normalized_distance=0.15, path_length=8),
        landmark_quality=LandmarkQuality(
            hand_detection_rate=0.5, frames_total=10, frames_analysed=10,
            frames_with_landmarks=5, reliable=True,
        ),
        source_fps=30.0,
        mlp_model_version="0.1-prototype",
    )
    session_repository.save_evaluation_result(db_session, result)
    client = _client(db_session)
    output = client.get("/api/practice/sessions/result-session-1/results").json()
    assert output["session"]["status"] == "evaluated"
    assert output["result"]["reference"] == {"id": "mudra_pataka", "name": "Pataka"}
    assert output["result"]["predictions"][0]["frame_end"] == 8
    assert output["result"]["dtw"]["path_length"] == 8
    assert output["result"]["frames_with_landmarks"] == 5
    started = client.post("/api/practice/sessions/result-session-1/evaluate")
    assert started.status_code == 200
    assert started.json()["status"] == "evaluated"
