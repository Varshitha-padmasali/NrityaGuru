"""Practice reference discovery and persisted progress history.

The current checkout has no validated reference sequences or compatible trained
classifier. Therefore it deliberately publishes no practice targets until both
are installed; dataset image presence alone is not sufficient for evaluation.
"""
import math
import hmac
import secrets
import tempfile
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.reviewer_auth import reviewer_token_matches
from app.api.deps import enforce_tutor_rate_limit, get_feedback_workflow, require_development_session_access
from app.db.database import get_db
from app.db.models import EvaluationRecord, FeedbackRecord, Movement, Mudra, PracticeSession, ReferenceSequence
from app.repositories import session_repository
from app.schemas.evaluation import EvaluationResult
from app.schemas.practice import (
    CreatePracticeSessionIn,
    PracticeReferenceOut,
    PracticeSessionOut,
    ProgressEntryOut,
    ProgressResponse,
)
from app.schemas.references import ReferenceSequenceIn, ReferenceSequenceOut
from app.services.frontend_contract import external_id, external_session_id, resolve_reference_id, resolve_session_id
from app.services.practice_evaluator import PracticeEvaluationUnavailable, evaluate_video
from app.services.feedback_workflow import FeedbackWorkflow
from app.services.knowledge_retrieval import media_url_path

router = APIRouter(prefix="/api", tags=["practice"])
SAMPLE_FPS = 5


@router.get("/practice/references", response_model=list[PracticeReferenceOut])
def list_practice_references(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[PracticeReferenceOut]:
    """Publish only references compatible with explicitly verified local artifacts."""
    if not settings.evaluation_runtime_verified or not settings.nrityaguru_hand_task or not settings.nrityaguru_mlp_bundle:
        return []
    task_path = Path(settings.nrityaguru_hand_task)
    model_path = Path(settings.nrityaguru_mlp_bundle)
    if not task_path.is_file() or not model_path.is_file():
        return []
    try:
        from app.services.practice_evaluator import _load_bundle_cached
        bundle = _load_bundle_cached(str(model_path.resolve()), model_path.stat().st_mtime_ns)
        supported_classes = set(bundle["metadata"]["classes"])
        version = bundle["metadata"]["model_version"]
    except Exception:
        return []

    references = list(db.scalars(
        select(ReferenceSequence)
        .where(
            ReferenceSequence.review_status == "teacher_verified",
            ReferenceSequence.feature_schema == "hand-v1",
            ReferenceSequence.evaluator_version == version,
            ReferenceSequence.feature_dimensions == 78,
            ReferenceSequence.mudra_id.is_not(None),
        )
        .order_by(ReferenceSequence.created_at, ReferenceSequence.id)
    ))
    output = []
    seen = set()
    for reference in references:
        mudra = db.get(Mudra, reference.mudra_id)
        if mudra is None or mudra.name not in supported_classes or mudra.id in seen:
            continue
        seen.add(mudra.id)
        output.append(PracticeReferenceOut(
            id=external_id("mudra", mudra.id),
            canonical_id=mudra.id,
            name=mudra.name,
            reference_type="mudra",
            description=mudra.practice_instructions,
            mudra_ids=[external_id("mudra", mudra.id)],
            image_url=media_url_path(mudra.reference_image_path),
            max_duration_seconds=settings.max_video_duration_seconds,
        ))
    return output


@router.post("/practice/sessions", response_model=PracticeSessionOut, status_code=201, dependencies=[Depends(require_development_session_access)])
def create_practice_session(
    body: CreatePracticeSessionIn, db: Session = Depends(get_db)
) -> PracticeSessionOut:
    resolved = resolve_reference_id(db, body.reference_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail={"code": "reference_not_found", "message": "The requested practice target does not exist."})
    kind, canonical_id = resolved
    mudra = db.get(Mudra, canonical_id) if kind == "mudra" else None
    movement = db.get(Movement, canonical_id) if kind == "movement" else None
    if (mudra is None) == (movement is None):
        raise HTTPException(status_code=404, detail={"code": "reference_not_found", "message": "The requested practice target does not exist."})
    session_id = str(secrets.randbelow((1 << 48) - 1) + 1)
    while db.get(PracticeSession, session_id) is not None:
        session_id = str(secrets.randbelow((1 << 48) - 1) + 1)
    session = session_repository.create_session(
        db,
        session_id,
        mudra_id=mudra.id if mudra else None,
        movement_id=movement.id if movement else None,
    )
    return PracticeSessionOut(
        session_id=session.id,
        reference_id=external_id(kind, canonical_id),
        status="created",
        created_at=session.created_at,
    )


def _decode_video(path: Path, settings: Settings) -> tuple[int, float]:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise HTTPException(status_code=422, detail={"code": "invalid_video", "message": "The video could not be opened by the supported decoder."})
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        declared_frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not math.isfinite(fps) or fps <= 0 or not math.isfinite(declared_frames) or declared_frames <= 0:
            raise HTTPException(status_code=422, detail={"code": "invalid_video_metadata", "message": "The video must report a finite, positive frame rate and frame count."})
        if width <= 0 or height <= 0 or width * height > settings.max_video_frame_pixels:
            raise HTTPException(status_code=413, detail={"code": "video_resolution_limit", "message": "Video frames must be at most 1920×1080."})
        duration = declared_frames / fps
        if duration > settings.max_video_duration_seconds:
            raise HTTPException(status_code=413, detail={"code": "video_duration_limit", "message": f"Video duration must not exceed {settings.max_video_duration_seconds} seconds."})
        decoded = 0
        sampled = 0
        sample_interval = max(1, round(fps / SAMPLE_FPS))
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            decoded += 1
            if decoded > settings.max_video_decoded_frames:
                raise HTTPException(status_code=413, detail={"code": "video_frame_limit", "message": "The video contains too many decoded frames."})
            if (decoded - 1) % sample_interval == 0:
                sampled += 1
        if decoded == 0 or sampled == 0:
            raise HTTPException(status_code=422, detail={"code": "empty_video", "message": "The recording contains no decodable frames."})
        return sampled, fps
    finally:
        capture.release()


async def upload_practice_video(
    session_id: str,
    reference_id: int = Form(...),
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PracticeSessionOut:
    stored_session_id = resolve_session_id(db, session_id)
    session = db.get(PracticeSession, stored_session_id) if stored_session_id else None
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": "Practice session was not found."})
    actual_reference_id = session.mudra_id or session.movement_id
    actual_reference = resolve_reference_id(db, reference_id)
    if actual_reference is None or actual_reference[1] != actual_reference_id:
        raise HTTPException(status_code=409, detail={"code": "reference_mismatch", "message": "The uploaded clip target does not match this session."})
    allowed_types = {"video/mp4", "video/webm", "video/quicktime"}
    if video.content_type not in allowed_types:
        raise HTTPException(status_code=415, detail={"code": "unsupported_video_type", "message": "Upload an MP4, WebM, or QuickTime recording."})

    size = 0
    first_bytes = b""
    try:
        with tempfile.TemporaryDirectory(prefix="nrityaguru-upload-") as temp_dir:
            path = Path(temp_dir) / "upload"
            with path.open("wb") as output:
                while chunk := await video.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_video_upload_mb * 1024 * 1024:
                        raise HTTPException(status_code=413, detail={"code": "upload_size_limit", "message": f"Video uploads are limited to {settings.max_video_upload_mb} MB."})
                    if len(first_bytes) < 16:
                        first_bytes += chunk[: 16 - len(first_bytes)]
                    output.write(chunk)
            is_mp4 = len(first_bytes) >= 12 and first_bytes[4:8] == b"ftyp"
            is_webm = first_bytes.startswith(b"\x1aE\xdf\xa3")
            if size == 0 or not (is_mp4 or is_webm):
                raise HTTPException(status_code=422, detail={"code": "invalid_video_container", "message": "The uploaded file is empty or is not a supported MP4/WebM container."})
            sampled_frames, fps = _decode_video(path, settings)
            model_path = Path(settings.nrityaguru_mlp_bundle or "")
            task_path = Path(settings.nrityaguru_hand_task or "")
            if not model_path.is_file() or not task_path.is_file():
                session.status = "failed"
                session.failure_reason = "evaluator_unavailable"
                db.commit()
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "evaluator_unavailable",
                        "message": "The clip passed upload and frame-decoding checks, but compatible MediaPipe and trained MLP files are not installed.",
                        "requirements": ["NRITYAGURU_HAND_TASK", "NRITYAGURU_MLP_BUNDLE", "runtime smoke test"],
                        "decoded_sample_frames": sampled_frames,
                        "source_fps": fps,
                    },
                )
            try:
                evaluate_video(path, session, db, settings, fps)
            except PracticeEvaluationUnavailable as exc:
                session.status = "failed"
                session.failure_reason = str(exc)[:80]
                db.commit()
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "evaluator_unavailable",
                        "reason": str(exc),
                        "message": "The clip was decoded, but the evaluation runtime could not produce a supported result.",
                    },
                ) from exc
    finally:
        await video.close()

    return PracticeSessionOut(
        session_id=session.id,
        reference_id=external_id("mudra" if session.mudra_id else "movement", actual_reference_id),
        status=session.status,
        created_at=session.created_at,
    )


try:
    import multipart  # noqa: F401
except ImportError:
    async def upload_without_multipart(session_id: str, request: Request) -> None:
        raise HTTPException(
            status_code=503,
            detail={"code": "multipart_dependency_missing", "message": "Install backend requirements to enable multipart video uploads."},
        )

    router.add_api_route(
        "/practice/sessions/{session_id}/video",
        upload_without_multipart,
        methods=["POST"],
        status_code=503,
        dependencies=[Depends(require_development_session_access)],
    )
else:
    router.add_api_route(
        "/practice/sessions/{session_id}/video",
        upload_practice_video,
        methods=["POST"],
        response_model=PracticeSessionOut,
        dependencies=[Depends(require_development_session_access)],
    )


@router.post("/practice/sessions/{session_id}/evaluate", dependencies=[Depends(require_development_session_access)])
def evaluate_practice_session(session_id: str, db: Session = Depends(get_db)) -> dict:
    stored_session_id = resolve_session_id(db, session_id)
    session = db.get(PracticeSession, stored_session_id) if stored_session_id else None
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": "Practice session was not found."})
    if session.status == "failed":
        raise HTTPException(status_code=503, detail={"code": session.failure_reason or "evaluation_unavailable", "message": "This attempt cannot be evaluated with the currently installed model and reference assets."})
    stored = db.scalars(select(EvaluationRecord).where(EvaluationRecord.session_id == session_id)).first()
    if stored is not None:
        target = db.get(Mudra, session.mudra_id) if session.mudra_id else db.get(Movement, session.movement_id)
        try:
            result = _frontend_evaluation(EvaluationResult.model_validate(stored.result_json), target, session.mudra_id or session.movement_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail={"code": "stored_result_invalid", "message": "The stored evaluation result does not match a supported schema."}) from exc
        return {"session_id": external_session_id(session_id), "status": "evaluated", "result": result, "error": None}
    raise HTTPException(status_code=409, detail={"code": "video_not_processed", "message": "Upload a valid recording before requesting evaluation."})


@router.get("/practice/sessions/{session_id}/results", dependencies=[Depends(require_development_session_access)])
def get_session_results(session_id: str, db: Session = Depends(get_db)) -> dict:
    stored_session_id = resolve_session_id(db, session_id)
    session = db.get(PracticeSession, stored_session_id) if stored_session_id else None
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": "Practice session was not found."})
    evaluation = db.scalars(
        select(EvaluationRecord).where(EvaluationRecord.session_id == session_id)
    ).first()
    feedback = db.scalars(
        select(FeedbackRecord)
        .where(FeedbackRecord.session_id == session_id)
        .order_by(FeedbackRecord.created_at.desc(), FeedbackRecord.id.desc())
        .limit(1)
    ).first()
    reference_id = session.mudra_id or session.movement_id
    target = db.get(Mudra, session.mudra_id) if session.mudra_id else db.get(Movement, session.movement_id)
    result_payload = None
    if evaluation is not None:
        try:
            result_payload = _frontend_evaluation(EvaluationResult.model_validate(evaluation.result_json), target, reference_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail={"code": "stored_result_invalid", "message": "The stored evaluation result does not match a supported schema."}) from exc
    feedback_payload = None
    if feedback is not None and isinstance(feedback.result_json, dict):
        body = feedback.result_json.get("feedback")
        summary = body.get("overall_summary") if isinstance(body, dict) else None
        if isinstance(summary, str):
            feedback_payload = {"text": summary, "model_name": feedback.model or "evidence_only", "created_at": feedback.created_at}
    return {
        "session": {
            "session_id": external_session_id(session.id),
            "reference_id": external_id("mudra" if session.mudra_id else "movement", reference_id),
            "status": "evaluated" if evaluation is not None else session.status,
            "created_at": session.created_at,
        },
        "result": result_payload,
        "feedback": feedback_payload,
    }


@router.post(
    "/practice/sessions/{session_id}/feedback",
    dependencies=[Depends(require_development_session_access), Depends(enforce_tutor_rate_limit)],
)
def request_session_feedback(
    session_id: str,
    db: Session = Depends(get_db),
    workflow: FeedbackWorkflow = Depends(get_feedback_workflow),
) -> dict:
    """Frontend contract adapter over the existing evidence-grounded workflow."""
    stored_session_id = resolve_session_id(db, session_id)
    if stored_session_id is None:
        raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": "Practice session was not found."})
    result = workflow.run(db, stored_session_id)
    latest = db.scalars(
        select(FeedbackRecord)
        .where(FeedbackRecord.session_id == stored_session_id)
        .order_by(FeedbackRecord.created_at.desc(), FeedbackRecord.id.desc())
        .limit(1)
    ).first()
    return {
        "text": result.feedback.overall_summary,
        "model_name": result.model or "evidence_only",
        "created_at": latest.created_at if latest else None,
    }


def _frontend_evaluation(result: EvaluationResult, target: Mudra | Movement | None, reference_id: str) -> dict:
    if target is None:
        raise ValueError("evaluation target is missing")
    quality = result.landmark_quality
    if quality is None or quality.frames_total is None or quality.frames_with_landmarks is None:
        raise ValueError("stored result does not have explicit landmark frame counts")
    predictions = []
    for prediction in result.predicted_labels:
        if prediction.interval is None or prediction.confidence is None:
            continue
        predictions.append({
            "label": prediction.label,
            "confidence": prediction.confidence,
            "frame_start": prediction.interval.start_frame,
            "frame_end": prediction.interval.end_frame,
        })
    return {
        "reference": {"id": external_id("mudra" if isinstance(target, Mudra) else "movement", reference_id), "name": target.name},
        "predictions": predictions,
        "dtw": ({
            "distance": result.dtw.distance,
            "normalized": result.dtw.normalized_distance,
            "path_length": result.dtw.path_length,
        } if result.dtw else None),
        "frames_total": quality.frames_total,
        "frames_with_landmarks": quality.frames_with_landmarks,
        "fps": result.source_fps,
        "deviations": [
            {
                "kind": deviation.kind,
                "message": deviation.description,
                "frame_start": deviation.interval.start_frame if deviation.interval else None,
                "frame_end": deviation.interval.end_frame if deviation.interval else None,
                "expected_label": result.expected_labels[0] if result.expected_labels else None,
                "predicted_label": next((p.label for p in result.predicted_labels if p.interval == deviation.interval), None),
            }
            for deviation in result.deviations
        ],
        "warnings": result.warnings,
        "model_version": result.mlp_model_version or "unknown",
        "feature_schema": result.dtw.feature_schema_version if result.dtw else "hand-v1",
        "created_at": result.created_at,
    }


@router.post("/reference-sequences", response_model=ReferenceSequenceOut, status_code=201)
def ingest_reference_sequence(
    payload: ReferenceSequenceIn,
    x_reference_review_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ReferenceSequenceOut:
    """Privileged intake endpoint; verified rows require the separately configured reviewer token."""
    if not settings.reference_review_configured:
        raise HTTPException(status_code=503, detail={"code": "reference_intake_disabled", "message": "Reference intake is disabled until a reviewer token is configured."})
    if not reviewer_token_matches(x_reference_review_token, settings):
        raise HTTPException(status_code=403, detail={"code": "reviewer_not_authorized", "message": "A valid reviewer authorization token is required."})
    if payload.review_status == "teacher_verified":
        configured_reviewer = settings.reference_reviewer_identity
        if not configured_reviewer or not payload.reviewer_identity or not hmac.compare_digest(payload.reviewer_identity, configured_reviewer):
            raise HTTPException(status_code=403, detail={"code": "reviewer_identity_mismatch", "message": "The recorded reviewer must match the server-configured reviewer identity."})
    if db.get(ReferenceSequence, payload.id) is not None:
        raise HTTPException(status_code=409, detail={"code": "reference_id_exists", "message": "Reference sequence IDs are immutable and must be unique."})
    target = db.get(Mudra, payload.mudra_id) if payload.mudra_id else db.get(Movement, payload.movement_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "reference_target_not_found", "message": "The referenced mudra or movement does not exist."})
    record = ReferenceSequence(
        **payload.model_dump(exclude={"reviewed_at"}),
        reviewed_at=payload.reviewed_at,
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    return ReferenceSequenceOut.model_validate(record, from_attributes=True)


@router.get("/reference-sequences", response_model=list[ReferenceSequenceOut])
def list_reviewed_reference_sequences(
    db: Session = Depends(get_db),
) -> list[ReferenceSequenceOut]:
    rows = list(db.scalars(
        select(ReferenceSequence)
        .where(ReferenceSequence.review_status == "teacher_verified")
        .order_by(ReferenceSequence.created_at, ReferenceSequence.id)
    ))
    return [ReferenceSequenceOut.model_validate(row, from_attributes=True) for row in rows]


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _confidence(value: Any) -> float | None:
    confidence = _positive_number(value)
    return confidence if confidence is not None and confidence <= 1 else None


@router.get("/progress", response_model=ProgressResponse)
def get_progress(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    settings: Settings = Depends(get_settings),
) -> ProgressResponse:
    """Read prior structured practice sessions; no user identity/auth exists yet."""
    if settings.app_env == "production":
        raise HTTPException(
            status_code=503,
            detail={"code": "user_auth_not_configured", "message": "Private progress is unavailable until user authentication and session ownership are configured."},
        )
    sessions = list(
        db.scalars(select(PracticeSession).order_by(PracticeSession.created_at.desc()).limit(limit))
    )
    entries: list[ProgressEntryOut] = []
    for session in sessions:
        reference_id = session.mudra_id or session.movement_id
        if reference_id is None:  # Guard against inconsistent legacy rows.
            continue
        if session.mudra_id:
            reference = db.get(Mudra, session.mudra_id)
        else:
            reference = db.get(Movement, session.movement_id)
        evaluation = db.scalars(
            select(EvaluationRecord).where(EvaluationRecord.session_id == session.id)
        ).first()
        feedback = db.scalars(
            select(FeedbackRecord)
            .where(FeedbackRecord.session_id == session.id)
            .order_by(FeedbackRecord.created_at.desc(), FeedbackRecord.id.desc())
            .limit(1)
        ).first()

        payload = evaluation.result_json if evaluation and isinstance(evaluation.result_json, dict) else {}
        dtw = payload.get("dtw") if isinstance(payload.get("dtw"), dict) else {}
        predictions = payload.get("predicted_labels")
        top = predictions[0] if isinstance(predictions, list) and predictions and isinstance(predictions[0], dict) else {}
        feedback_payload = feedback.result_json if feedback and isinstance(feedback.result_json, dict) else {}
        feedback_body = feedback_payload.get("feedback") if isinstance(feedback_payload.get("feedback"), dict) else {}
        summary = feedback_body.get("overall_summary")

        entries.append(
            ProgressEntryOut(
                session_id=external_session_id(session.id),
                reference_id=external_id("mudra" if session.mudra_id else "movement", reference_id),
                reference_name=reference.name if reference is not None else reference_id,
                status="evaluated" if evaluation else (session.status if session.status in {"created", "uploaded", "processing", "failed"} else "created"),
                created_at=session.created_at,
                dtw_normalized=_positive_number(dtw.get("normalized_distance")),
                top_label=top.get("label") if isinstance(top.get("label"), str) else None,
                top_confidence=_confidence(top.get("confidence")),
                feedback_summary=summary if isinstance(summary, str) else None,
            )
        )
    return ProgressResponse(scope="shared_development", sessions=entries)
