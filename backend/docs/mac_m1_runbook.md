# MacBook Air M1 development and evaluation runbook

## Start the app

From the repository root, with Docker Desktop running:

```bash
docker compose config -q
docker compose up --build
```

Open the frontend at `http://localhost:3000`, the API at `http://localhost:8000`, and Swagger at
`http://localhost:8000/docs`. Compose applies Alembic migrations before seeding. PostgreSQL data
is kept in the named `pgdata` volume; do not use `docker compose down -v` to stop the stack.
Evaluation stays disabled until compatible artifacts and an isolated runtime smoke check are
available. Gemini is optional; set `GEMINI_API_KEY` in the shell before starting Compose for live
tutor calls. The app uses a knowledge-only fallback without the key.

The backend image targets `linux/amd64` so its Python 3.12 MediaPipe wheel matches the installed
runtime. On an M1, Docker Desktop may run that image through CPU emulation. The backend Compose
service mounts the ignored local `artifacts/` folder read-only at `/artifacts/`.

## Prepare the dataset and model in an isolated Linux container

These commands require Docker Desktop and the Kaggle dataset downloaded locally. The existing
folder mapping is candidate data; the three Katakamukha variants are excluded from classifier
training until a teacher reviews them.

```bash
export DATASET_PATH="/path/to/Bharatanatyam-Mudra-Dataset-master"
mkdir -p artifacts evaluation_module/data
curl -L -o artifacts/hand_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
docker build --platform linux/amd64 -f evaluation_module/Dockerfile -t nrityaguru-eval .
docker run --rm --platform linux/amd64 \
  -v "$DATASET_PATH:/data/dataset:ro" \
  -v "$PWD/artifacts/hand_landmarker.task:/artifacts/hand_landmarker.task:ro" \
  -v "$PWD/evaluation_module/data:/data/out" \
  nrityaguru-eval python -m evaluation_module.data_prep.validate_dataset \
  --dataset /data/dataset --output /data/out/dataset_manifest.json \
  --files-output /data/out/dataset_files.json
docker run --rm --platform linux/amd64 \
  -v "$DATASET_PATH:/data/dataset:ro" \
  -v "$PWD/artifacts/hand_landmarker.task:/artifacts/hand_landmarker.task:ro" \
  -v "$PWD/evaluation_module/data:/data/out" \
  nrityaguru-eval python -m evaluation_module.data_prep.extract_hand_landmarks \
  --dataset /data/dataset --model /artifacts/hand_landmarker.task \
  --out /data/out/hand_landmarks.csv
docker run --rm --platform linux/amd64 \
  -v "$PWD/evaluation_module/data:/data/out" \
  nrityaguru-eval python -m evaluation_module.mudra_mlp.train \
  --csv /data/out/hand_landmarks.csv --out /data/out/models
cp evaluation_module/data/models/mudra_mlp.joblib artifacts/mudra_mlp.joblib
```

Training writes held-out metrics and confusion matrix alongside the model. The bundle records
the exact NumPy, scikit-learn, and joblib versions; inference rejects a dependency-version
mismatch. Inspect the full per-class report and label mappings before using it. The reported
split is grouped by perceptual image hash, not performer, so it does not establish generalization
to new dancers.

## Smoke-test the backend evaluator in a separate process

Place one real dataset image at `SAMPLE_IMAGE`, then run:

```bash
export SAMPLE_IMAGE="/path/to/real-dataset-image.jpg"
docker compose run --rm backend python -m scripts.smoke_evaluator \
  --sample-image "$SAMPLE_IMAGE"
```

This initializes MediaPipe and loads the local model in a short-lived container process. Enable
the API runtime only after the command succeeds:

```bash
export EVALUATION_RUNTIME_VERIFIED=true
docker compose up -d --force-recreate backend
```

The flag is not set by the smoke script. A failed native graph must leave it false. Use real video
and camera smoke tests before enabling evaluation outside development.

## Record and review references

Prepare a candidate from a genuine consented performance recording using
`evaluation_module.data_prep.prepare_reference_sequence` as described in
[reference_workflow.md](reference_workflow.md). The video becomes a candidate feature sequence;
it is not teacher-verified automatically. After a qualified teacher reviews and updates the JSON
review metadata, set server-only `REFERENCE_REVIEW_TOKEN` and
`REFERENCE_REVIEWER_IDENTITY`, then submit it to `POST /api/reference-sequences`. Candidate rows
are never offered as practice references.

## Local Python development

Python 3.12 and Node.js are recommended. For a local API process while PostgreSQL runs in Compose:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload
```

In another terminal, run the frontend:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Run tests with `cd backend && ../.venv/bin/pytest -q`,
`cd evaluation_module && ../.venv/bin/pytest -q tests`,
`cd vision && ../.venv/bin/pytest -q tests`, and
`cd frontend && npm test -- --run && npm run typecheck && npm run lint && npm run build`.

This checkout could not run the Compose stack because Docker Desktop was unavailable. Its native
macOS MediaPipe task graph also failed to initialize, and there are currently no trained model
bundles or authentic reference recordings. Until the isolated container pipeline is run on a
Docker-enabled host and passes its checks, the app returns a clear evaluator-unavailable result.
