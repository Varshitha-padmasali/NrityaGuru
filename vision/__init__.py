"""NrityaGuru Computer Vision Module (Member 3).

Provides video ingestion, MediaPipe Tasks pose and hand landmark detection,
normalization, fixed-schema (260-dim) feature extraction, quality reporting,
and sequence export for Member 4's MLP and DTW evaluators.
"""

from vision.adapter_member4 import (
    AdapterInputError,
    check_sequence_readiness_for_member4,
    sequence_to_dtw_matrix,
    sequence_to_member4_frames,
)
from vision.detectors.base import (
    BaseHandBackend,
    BasePoseBackend,
    HandDetectionResult,
    MockHandBackend,
    MockPoseBackend,
    PoseDetectionResult,
)
from vision.exporter import (
    EXPORT_FORMAT_VERSION,
    export_sequence,
    load_sequence,
)
from vision.feature_extractor import (
    ExtractedFrameFeatures,
    extract_frame_features,
    extract_hand_for_mlp,
    feature_names,
)
from vision.hand_detector import HandDetector
from vision.normalization import normalize_hand_landmarks, normalize_pose_landmarks
from vision.pose_detector import PoseDetector
from vision.schemas import (
    DataQualityReport,
    FEATURE_DIM,
    FrameData,
    FrameLandmarks,
    HandLandmarkSet,
    Point3D,
    PoseLandmarkSet,
    VideoMetadata,
)
from vision.sequence_builder import ProcessedSequence, VisionPipeline
from vision.video_reader import VideoReader, create_synthetic_video

__all__ = [
    "FEATURE_DIM",
    "Point3D",
    "HandLandmarkSet",
    "PoseLandmarkSet",
    "VideoMetadata",
    "FrameData",
    "FrameLandmarks",
    "DataQualityReport",
    "VideoReader",
    "create_synthetic_video",
    "HandDetector",
    "PoseDetector",
    "HandDetectionResult",
    "PoseDetectionResult",
    "BaseHandBackend",
    "BasePoseBackend",
    "MockHandBackend",
    "MockPoseBackend",
    "normalize_hand_landmarks",
    "normalize_pose_landmarks",
    "extract_frame_features",
    "ExtractedFrameFeatures",
    "feature_names",
    "extract_hand_for_mlp",
    "VisionPipeline",
    "ProcessedSequence",
    "export_sequence",
    "load_sequence",
    "EXPORT_FORMAT_VERSION",
    "AdapterInputError",
    "sequence_to_member4_frames",
    "sequence_to_dtw_matrix",
    "check_sequence_readiness_for_member4",
]
