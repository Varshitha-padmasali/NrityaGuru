"""Video-to-result orchestration for installed, locally trusted evaluation assets.

This code is gated by EVALUATION_RUNTIME_VERIFIED. Set that flag only after a
separate smoke test has established that MediaPipe can safely initialize in the
deployment environment. Uploaded video is processed from a temporary path and is
never persisted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import sys

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Movement, Mudra, PracticeSession, ReferenceSequence
from app.repositories.session_repository import save_evaluation_result
from app.schemas.evaluation import (
    DtwSummary,
    EvaluationResult,
    FrameInterval,
    LandmarkQuality,
    PredictedLabel,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class PracticeEvaluationUnavailable(RuntimeError):
    """A required local evaluator asset or compatible reference is unavailable."""


def _trusted_evaluation_modules():
    # The sklearn/joblib bundle is executable data and must only be loaded from a
    # locally controlled path, never from a learner upload.
    from evaluation_module.mudra_mlp.features import FEATURE_SCHEMA_VERSION, hand_features
    from evaluation_module.mudra_mlp.predict import load_bundle, predict_hand
    from evaluation_module.sequence.dtw import dtw

    return FEATURE_SCHEMA_VERSION, hand_features, load_bundle, predict_hand, dtw


@lru_cache(maxsize=2)
def _load_bundle_cached(path: str, mtime_ns: int):
    _, _, load_bundle, _, _ = _trusted_evaluation_modules()
    return load_bundle(path)


def _make_landmarker(task_path: str):
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(
            model_asset_path=task_path,
            delegate=mp_python.BaseOptions.Delegate.CPU,
        ),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.35,
        min_hand_presence_confidence=0.35,
        min_tracking_confidence=0.35,
    )
    return mp, vision, vision.HandLandmarker.create_from_options(options)


def evaluate_video(path: str | Path, session: PracticeSession, db: Session, settings: Settings, source_fps: float) -> EvaluationResult:
    if not settings.evaluation_runtime_verified:
        raise PracticeEvaluationUnavailable("native_evaluator_not_verified")
    if not settings.nrityaguru_hand_task or not Path(settings.nrityaguru_hand_task).is_file():
        raise PracticeEvaluationUnavailable("mediapipe_task_missing")
    if not settings.nrityaguru_mlp_bundle or not Path(settings.nrityaguru_mlp_bundle).is_file():
        raise PracticeEvaluationUnavailable("trained_model_missing")

    try:
        feature_schema, hand_features, _, predict_hand, dtw = _trusted_evaluation_modules()
        task_path = str(Path(settings.nrityaguru_hand_task).resolve())
        model_path = Path(settings.nrityaguru_mlp_bundle).resolve()
        bundle = _load_bundle_cached(str(model_path), model_path.stat().st_mtime_ns)
        target = db.get(Mudra, session.mudra_id) if session.mudra_id else db.get(Movement, session.movement_id)
        if target is None:
            raise PracticeEvaluationUnavailable("practice_target_missing")
        if session.movement_id:
            raise PracticeEvaluationUnavailable("movement_classifier_not_available")

        reference = db.scalars(
            select(ReferenceSequence)
            .where(
                ReferenceSequence.review_status == "teacher_verified",
                ReferenceSequence.feature_schema == feature_schema,
                ReferenceSequence.evaluator_version == bundle["metadata"]["model_version"],
                ReferenceSequence.feature_dimensions == 78,
                ReferenceSequence.mudra_id == session.mudra_id if session.mudra_id else ReferenceSequence.movement_id == session.movement_id,
            )
            .order_by(ReferenceSequence.created_at, ReferenceSequence.id)
        ).first()

        mp, vision, landmarker = _make_landmarker(task_path)
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            landmarker.close()
            capture.release()
            raise PracticeEvaluationUnavailable("video_decode_failed")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        sample_interval = max(1, round(fps / 5))
        frame_index = 0
        analyzed = 0
        learner_features = []
        frame_predictions: list[tuple[int, str, float]] = []
        try:
            while True:
                ok, bgr = capture.read()
                if not ok:
                    break
                current = frame_index
                frame_index += 1
                if current % sample_interval:
                    continue
                analyzed += 1
                rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                    int(current * 1000 / fps),
                )
                if not result.hand_landmarks:
                    continue
                hands = []
                for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
                    coords = np.asarray([[lm.x * bgr.shape[1], lm.y * bgr.shape[0], lm.z * bgr.shape[1]] for lm in landmarks], dtype=float)
                    score = float(handedness[0].score) if handedness else 0.0
                    hands.append((score, coords))
                _, coords = max(hands, key=lambda item: item[0])
                predicted = predict_hand(bundle, coords)
                try:
                    learner_features.append(hand_features(coords).tolist())
                except ValueError:
                    continue
                if predicted.get("status") == "success" and predicted.get("predicted_label"):
                    frame_predictions.append((current, predicted["predicted_label"], float(predicted["confidence"])))
        finally:
            capture.release()
            landmarker.close()

        if analyzed == 0:
            raise PracticeEvaluationUnavailable("no_frames_analyzed")
        if not learner_features:
            raise PracticeEvaluationUnavailable("no_reliable_hand_landmarks")

        expected = [target.name]
        predictions: list[PredictedLabel] = []
        if frame_predictions:
            start = previous = frame_predictions[0][0]
            label = frame_predictions[0][1]
            scores = [frame_predictions[0][2]]
            for idx, next_label, score in frame_predictions[1:]:
                if next_label != label:
                    predictions.append(PredictedLabel(label=label, confidence=float(np.mean(scores)), interval=FrameInterval(start_frame=start, end_frame=previous)))
                    start, label, scores = idx, next_label, [score]
                else:
                    scores.append(score)
                previous = idx
            predictions.append(PredictedLabel(label=label, confidence=float(np.mean(scores)), interval=FrameInterval(start_frame=start, end_frame=previous)))

        dtw_result = None
        if reference is not None:
            try:
                aligned = dtw(reference.frames, learner_features)
            except ValueError as exc:
                raise PracticeEvaluationUnavailable("reference_sequence_invalid") from exc
            dtw_result = DtwSummary(
                distance=aligned.raw_cost,
                normalized_distance=aligned.normalized_cost,
                threshold=reference.threshold,
                within_threshold=(aligned.normalized_cost <= reference.threshold) if reference.threshold is not None else None,
                reference_sequence_id=reference.id,
                feature_schema_version=reference.feature_schema,
                path_length=len(aligned.path),
            )

        result = EvaluationResult(
            schema_version="1.0",
            session_id=session.id,
            reference_mudra_id=session.mudra_id,
            reference_movement_id=session.movement_id,
            expected_labels=expected,
            predicted_labels=predictions,
            dtw=dtw_result,
            landmark_quality=LandmarkQuality(
                hand_detection_rate=len(learner_features) / analyzed,
                frames_total=frame_index,
                frames_analysed=analyzed,
                frames_with_landmarks=len(learner_features),
                reliable=bool(learner_features),
                notes=["MediaPipe Hands detected one or more hands in analyzed frames."],
            ),
            warnings=[] if reference is not None else ["No compatible teacher-verified reference sequence exists; DTW was not computed."],
            mlp_model_version=bundle["metadata"]["model_version"],
            source_fps=source_fps,
            created_at=datetime.now(timezone.utc),
        )
        save_evaluation_result(db, result)
        session.status = "evaluated"
        session.failure_reason = None
        db.commit()
        return result
    except PracticeEvaluationUnavailable:
        raise
    except Exception as exc:
        db.rollback()
        # Do not leak native/runtime exception details through the API.
        raise PracticeEvaluationUnavailable("evaluator_runtime_error") from exc
