# Mudra catalogue, dataset, and model coverage

## Canonical catalogue

`backend/data/seed/mudras.json` is the single version-controlled catalogue and remains the
database seed source. It now contains 52 stable `mudra_*` IDs: 28 entries in `Asamyuta Hasta`
and 24 in `Samyuta Hasta`. The spellings and category assignment are cited to the NCERT
Kriti-I Grade 6 dance chapter. That chapter supplies a teaching list; it does not establish
every lineage's preferred spelling, gesture details, or meanings. New rows therefore have
empty meanings, usages, descriptions, image paths, and instructions, and are marked
`source_cited`, not `verified`. Existing source-cited Pataka entries and their documented
concept mappings remain in place.

The 12 names used in the checked-in historical MLP metadata are retained as aliases for the
corresponding canonical IDs. Their mapping is documented as a legacy project label mapping,
not proof that the Kaggle dataset currently uses those spellings. The seed validator rejects
duplicate canonical names and ambiguous aliases. `id` is the stable normalized identifier;
no database migration is needed because the existing `mudras` table already stores the
required fields and supports JSON aliases.

## Database and API

From `backend/`, seed the expanded catalogue with:

```bash
python -m app.db.seed
```

Seeding is an upsert by stable ID and safe to repeat. Existing installations need no table
reset or destructive migration. The ordinary verification guard remains active: the catalogue
rows are source-cited and stay hidden unless the server setting allows unverified access and
the request explicitly opts in.

```bash
curl 'http://127.0.0.1:8000/api/mudras?limit=100&include_unverified=true'
curl 'http://127.0.0.1:8000/api/mudras?q=kapota&include_unverified=true'
curl 'http://127.0.0.1:8000/api/mudras/Kapota?include_unverified=true'
```

The list endpoint returns up to 100 by default (maximum 200), and `q` matches canonical
names and approved aliases. Detail lookup accepts the stable ID, canonical name, or an
unambiguous alias. Every result still carries its verification status, source, and limitations.

## Kaggle image data

There is no Kaggle download, image directory, image manifest, or license record in this
checkout. The earlier evaluation README reports a 49-folder dataset run, but it does not
include the folder names or a reproducible manifest; that report is not enough to claim the
dataset has 49 or 52 verified classes. The Kaggle page could not be inspected through the
available access, and Kaggle CLI is not installed. Dataset license is therefore **unknown**;
check the dataset page before redistribution, training for commercial use, or committing any
images. [Kaggle's dataset guidance](https://www.kaggle.com/docs/datasets) says licensing is
specified per dataset, so do not infer a license from public availability.

After installing Kaggle CLI and configuring its existing local authentication, download
outside Git:

```bash
cd evaluation_module
mkdir -p data/mudra_dataset
kaggle datasets download -d geethikanambiar/mudra-dataset -p data/mudra_dataset --unzip
```

Point validation at the directory whose immediate children are class folders. The validator
does not copy or rename the original images:

```bash
python -m data_prep.validate_dataset --dataset data/mudra_dataset
```

It writes `data/mudra_dataset_manifest.json` with canonical ID matches, per-class image and
valid-image counts, absent catalogue classes, unknown class folders, unsupported files,
corrupt images, and duplicate-content groups. Unknown class names fail the landmark extraction
step until their spelling is reviewed and added explicitly as an alias. The manifest records
the license as unknown rather than inventing one. Dataset images and generated CSV/manifests
are ignored by `evaluation_module/.gitignore`.

## Model and vision limits

The landmark CSV extractor now maps approved folder labels to canonical display names. The
existing classifier uses one hand (63 raw coordinates transformed into 78 `hand-v1` features),
so training infers all represented **Asamyuta** labels from the catalogue and excludes two-hand
Samyuta rows. It rejects unknown labels and missing/undersized classes rather than silently
training a partial mapping. A 52-class model requires a separately designed two-hand feature
representation and verified dataset labels; this change does not claim that capability.

Training runs from `evaluation_module/` after dependencies, dataset, and MediaPipe task file
are supplied:

```bash
pip install -r requirements.txt
python -m data_prep.extract_hand_landmarks --dataset data/mudra_dataset --model hand_landmarker.task --out data/hand_landmarks.csv
python -m mudra_mlp.train --csv data/hand_landmarks.csv --out models
```

Saved metadata binds model classes and class ordering to a digest of the canonical catalogue.
Inference rejects bundles trained against changed catalogue data or without the strict label
mapping. Retrain after changing canonical names, aliases, or categories. The checked-in metrics
file reports an older 12-class image-level experiment, but its `.joblib` bundle, dataset,
split manifest, and license are absent; those metrics do not establish 52-class recognition.

## Sources and contribution process

- NCERT, *Kriti-I*, Grade 6, Chapter 12, “My Body in Motion” lists the hand gesture names and
  categories: [official NCERT textbook portal](https://ncert.nic.in/textbook.php?fekr1=1-2).
- Existing meanings and concept-mapping examples remain attributed to their existing
  source records. Add descriptions or usages only after citing a source and keeping the
  verification status appropriate.
- To add an alternate spelling, edit the canonical row's `alternate_names` in
  `backend/data/seed/mudras.json`, ensure it is not ambiguous, then rerun the seed and tests.
