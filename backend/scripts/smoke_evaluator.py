"""Isolated native-runtime check before enabling evaluation in the API process."""
import argparse
from pathlib import Path
import sys

import cv2

from app.core.config import get_settings
from app.services.practice_evaluator import _load_bundle_cached, _make_landmarker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-image", type=Path, required=True,
                        help="a real dataset/reference image used to exercise MediaPipe")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.nrityaguru_hand_task or not Path(settings.nrityaguru_hand_task).is_file():
        parser.error("NRITYAGURU_HAND_TASK must point to a readable task file")
    if not settings.nrityaguru_mlp_bundle or not Path(settings.nrityaguru_mlp_bundle).is_file():
        parser.error("NRITYAGURU_MLP_BUNDLE must point to a trusted locally trained bundle")
    image = cv2.imread(str(args.sample_image))
    if image is None:
        parser.error("sample image could not be decoded")
    model_path = Path(settings.nrityaguru_mlp_bundle).resolve()
    bundle = _load_bundle_cached(str(model_path), model_path.stat().st_mtime_ns)
    mp, vision, landmarker = _make_landmarker(str(Path(settings.nrityaguru_hand_task).resolve()))
    try:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        result = landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), 0
        )
        print("Native MediaPipe runtime initialized and processed one sample image.")
        print(f"Trained model bundle loaded; supported class count: {len(bundle['metadata']['classes'])}.")
        print(f"Hands detected in smoke image: {len(result.hand_landmarks)}.")
        print("Only now may EVALUATION_RUNTIME_VERIFIED=true be considered; it is not changed by this script.")
    finally:
        landmarker.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Evaluator smoke test failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
