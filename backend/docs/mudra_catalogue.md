# Mudra catalogue, dataset, and model coverage

## Canonical catalogue

`backend/data/seed/mudras.json` is the database seed source and contains 52 stable
`mudra_*` IDs: 28 Asamyuta Hasta and 24 Samyuta Hasta. Names and categories are cited to
NCERT Kriti-I, Grade 6, Chapter 12. The chapter gives a teaching list; it does not establish
every lineage's spelling, gesture detail, or meaning. Entries without individually sourced
meaning or usage keep those fields empty and are not marked verified.

The exact dataset-folder crosswalk is maintained separately in
`backend/data/seed/dataset_mapping.json`. Dataset folder strings are preserved as source labels
and never used as canonical IDs. Database seeding upserts by stable ID and is safe to repeat;
no schema migration or database reset is needed. The catalog list/detail endpoints return
dataset image counts and a recognition support flag. No recognition model is currently loaded,
so `recognition_supported` is false for every record.

## Dataset inspection

The downloaded Kaggle archive is at the development path in `dataset_mapping.json`; other
machines can set `NRITYAGURU_DATASET_DIR`. A fresh scan found **50 folders and 28,431 supported
images**, all decodable by OpenCV. It found 1,342 groups with byte-identical images and 3,568
extra duplicate copies. No unsupported files or unknown folder labels were found.

The 50 folders map to **48 canonical IDs**. `Katakamukha_1`, `Katakamukha_2`, and
`Katakamukha_3` retain separate dataset labels and variant IDs, but map to the same canonical
`mudra_katakamukha`. One sample from each folder shows visibly different configurations. A
dance-school article describes three Katakamukha variants in Kathak, supporting the idea that
these are variants of one named hasta; because the article is about Kathak, it does not
independently verify the Bharatanatyam dataset's subdivision. The variant mapping is documented
and should receive a Bharatanatyam teacher's review before recognition results are presented
as expert-validated.

All Asamyuta entries except Samdamsha have images: **27 mapped single-hand labels can be used
for the current one-hand MLP**. The 21 Samyuta entries present in the dataset are excluded by
that model. Four catalogue records have no dataset images: Samdamsha, Dola, Utsanga, and
Avahitta. These are data coverage counts, not a claim that a model has been trained.

The extracted archive `LICENSE.md` declares CC BY-SA 4.0. Preserve the attribution and
ShareAlike requirements for any adapted or redistributed dataset material. Images are not
copied into or committed with the repository.

Regenerate counts, the compact JSON summary, and the ignored JSONL file manifest with:

```bash
python -m pip install -r evaluation_module/requirements.txt
python -m evaluation_module.data_prep.validate_dataset --update-mapping --require-all
```

Use `--dataset /path/to/class-folders` or set `NRITYAGURU_DATASET_DIR` on another machine.
Each JSONL entry records a relative file path, source label, canonical ID, variant ID,
SHA-256, dimensions, and image decode status. The scanner streams one file at a time and reports
unknown/missing folders, corrupt images, unsupported files, and exact duplicates.

## Database and API

Seed the catalogue from `backend/`:

```bash
python -m app.db.seed
```

Source-cited records stay out of concept retrieval unless both the server setting
`ALLOW_UNVERIFIED_RECORDS=true` and the request's `include_unverified=true` are set. List all 52
entries with:

```bash
curl 'http://127.0.0.1:8000/api/mudras?limit=100&include_unverified=true'
curl 'http://127.0.0.1:8000/api/mudras?q=kapota&include_unverified=true'
```

The UI requests the catalogue entries and shows their verification status, image coverage,
and recognition support separately. Reference images are displayed only if a path points to a
file served by the backend. Dataset photos are not exposed as a static gallery.

## Recognition pipeline

The landmark extractor requires an exact folder mapping and stores both the original source
folder and canonical label, plus exact and perceptual hashes. It refuses unknown folders. The
MLP uses one hand (63 coordinates transformed into 78 `hand-v1` features), maps its labels via
the canonical catalogue, and excludes two-hand Samyuta rows. Its train/validation/test split is
grouped by perceptual image hash so repeated/near-identical images stay in one split. The
classifier will train only on represented Asamyuta classes; it does not claim 52-class
recognition. Its artifact metadata binds the class order and preprocessing version to the
canonical catalogue digest.

Training also requires a MediaPipe HandLandmarker task file, which is not present in the
repository. After placing one at `evaluation_module/hand_landmarker.task`:

```bash
python -m evaluation_module.data_prep.extract_hand_landmarks --model evaluation_module/hand_landmarker.task --out evaluation_module/data/hand_landmarks.csv
python -m evaluation_module.mudra_mlp.train --csv evaluation_module/data/hand_landmarks.csv --out evaluation_module/models
```

The old checked-in metrics file reports a historical 12-label experiment, but its model
artifact, source dataset, and split manifest are absent. It is not evidence for current
recognition quality. Model retraining and measured accuracy remain pending.

## References

- NCERT, *Kriti-I*, Grade 6, Chapter 12, “My Body in Motion”: [official textbook portal](https://ncert.nic.in/textbook.php?fekr1=1-2).
- Dataset license copied in the downloaded archive: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- Cross-tradition context on multiple Katakamukha forms: [Edogawa Kathak Society article](https://edoriver.wixsite.com/kathak/%E7%A0%94%E7%A9%B6/%E3%82%A4%E3%83%B3%E3%83%89%E8%88%9E%E8%B8%8A%E3%81%AE%E7%BE%8E%E3%82%92%E8%B1%A1%E5%BE%B4%E3%81%99%E3%82%8B%E6%89%8B%E3%81%AE%E3%81%8B%E3%81%9F%E3%81%A1-%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%A0%E3%82%AB%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6).
