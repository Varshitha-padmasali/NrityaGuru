# NrityaGuru: Member 4 module (MLP classification + DTW evaluation)

Prototype evaluation module: classifies single-hand mudra images with an MLP, compares movement
sequences with Dynamic Time Warping (DTW), and builds a result in the backend's
`EvaluationResult` v1.0 format (`backend/docs/evaluation_contract.md`).

## Folder map
| Path | Purpose |
|---|---|
| `sequence/dtw.py` | DTW (Euclidean local distance, alignment path, raw and normalised cost) |
| `data_prep/extract_hand_landmarks.py` | MediaPipe HandLandmarker on a folder-per-class image dataset, writes `data/hand_landmarks.csv` |
| `mudra_mlp/features.py` | 78 features per hand: wrist-relative, size-normalised coordinates + fingertip distances |
| `mudra_mlp/train.py` | Trains and evaluates the MLP, saves model and metrics to `models/` |
| `mudra_mlp/predict.py` | Loads the saved model and predicts one hand |
| `mudra_eval/build_result.py` | Combines MLP + DTW into the contract JSON |
| `demo/run_demo.py` | Simulated-sequence demo (see warning below) |
| `tests/` | 33 tests |

## Setup and run (Windows PowerShell, from `evaluation_module`)
```powershell
pip install numpy pandas scikit-learn opencv-python mediapipe pydantic pytest joblib
# download hand_landmarker.task (MediaPipe model) into this folder
python -m data_prep.extract_hand_landmarks --dataset "<dataset folder>" --model hand_landmarker.task --out data\hand_landmarks.csv
python -m mudra_mlp.train --csv data\hand_landmarks.csv --out models
python -m demo.run_demo
python -m pytest tests -q
```
Dataset target: Kaggle `geethikanambiar/mudra-dataset`. The actual archive, class folders, counts,
and license are absent from this checkout and have not been re-verified. An earlier run recorded
49 folders but did not preserve a manifest; do not treat that as verified coverage. Use
`python -m data_prep.validate_dataset` to inventory a local download before extraction.
Not committed to git: dataset images, `hand_landmarker.task`, generated CSV/manifests, or
`models/*.joblib`.

## Historical results (12 single-hand classes; artifacts unavailable)
- 600 images in the selected classes, 515 with a detected hand, 9 exact duplicates removed, 506 used.
- Split (stratified, by image, seed 42): train 303 (606 with mirrored copies), validation 101, test 102.
- Model chosen on validation macro-F1: MLP (128, 64), alpha 0.0001.
- Test: accuracy 0.902 (chance 0.083), macro precision/recall/F1 = 0.914 / 0.904 / 0.901.
- Weakest classes: mayooram (recall 0.56), arthachandran and kapitham (recall 0.75). Similar mudras (pathaka, tripathaka, arthapataka) were occasionally confused.
- Full per-class table and confusion matrix: `models/mudra_mlp_metrics.json`, `models/mudra_mlp_confusion_matrix.csv`.

## Design notes
- **Features:** wrist moved to origin, divided by wrist-to-middle-finger-base distance, so hand position and size do not matter. Coordinates are first converted to pixel units to avoid aspect-ratio distortion.
- **Mirrored copies** are added to the training set only, so left and right hands are both handled (handedness labels of still images are unreliable).
- **Scaler** is fitted on training data only (inside a scikit-learn Pipeline).
- **DTW** compares sequences of per-frame features and tolerates different speeds. It returns an alignment cost, not a diagnosis.
- **Result builder:** frames without a detected hand are dropped and counted, not zero-filled. Label mismatches are reported as general deviations. No finger-level claims are made.

## Limitations (state these in reviews)
1. The split is by image and the dataset has no performer ids, so accuracy on new people or webcam video is untested and probably lower.
2. 85 of 600 images (14%) had no hand detected and were excluded from training and testing.
3. The test set has 102 images; one image is about 1% accuracy.
4. MLP scores are raw model outputs, not calibrated probabilities.
5. The DTW threshold is not validated, so `threshold` and `within_threshold` are left empty.
6. The demo uses SIMULATED sequences (interpolated between real still-image hands), not real video.
7. `reliable` (hand detected in at least 80% of frames) and the deviation filters (at least 3 frames, mean confidence at least 0.6) are prototype assumptions.
8. Single-hand mudras only; double-hand mudras and body pose are not used.

## Status
| Item | Status |
|---|---|
| DTW + tests | Implemented, tested |
| Landmark extraction | Implemented, tested (logic), run on the real dataset |
| MLP training, evaluation, saving, prediction | Implemented, tested, real metrics above |
| Result builder (contract v1.0) + tests | Implemented, tested |
| Demo | Implemented, run |
| Backend adapter for the 260-value frame format | Not implemented: no 260-value producer or sample is present in this checkout. `vision/adapter_member4.py` supplies the 63 raw single-hand coordinates used by the evaluator. |
| Writing results to PostgreSQL and feedback integration | Backend already has a trusted database read/store and feedback workflow, but no current capture-to-persistence orchestration service. |
| DTW threshold from real recordings, webcam validation | Pending |
| Finger-level deviations | Not implemented |
