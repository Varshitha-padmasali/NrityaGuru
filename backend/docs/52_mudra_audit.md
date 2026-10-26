# 52-mudra knowledge base and sequence audit

Audit updated 2026-10-26 from the seed files, SQLAlchemy model/retrieval code, sequence tests, and the previously queried PostgreSQL state. This report distinguishes source-cited material from teacher verification.

## Coverage and evidence

- Stable catalogue retained: 52 existing IDs, 28 Asamyuta and 24 Samyukta. The 1917 Abhinaya Darpana translation’s Chapter 12 lists 28 single hands and Chapter 13 lists 24 combined hands. The current NCERT Kriti-I PDF presents 28 and 23; these are different teaching/catalogue conventions. The project retains its existing 28/24 catalogue without claiming the two sources are identical.
- 52 records remain `source_cited`; 0 are teacher-verified. 51 records have a sourced, paraphrased hand-form description and selected usages; 49 have a meaning/gloss; 0 have supported practice-instruction text. These are source summaries, not complete description of each tradition.
- `Kangula` is the unresolved name: the consulted 1917 chapter gives `Lāṅgula`; NCERT gives `Kāṅgula`. Its description/usage and association are intentionally not asserted pending teacher/source review. All original IDs and categories remain.
- Seed now contains 165 source-cited concept mappings targeting 45 distinct mudras. Each mapping has a source ID and evidence note; multi-match concepts are returned as alternatives. Mappings derived from “According to another book” passages remain attached to that qualification in evidence notes rather than being represented as universal tradition.
- Source coverage is uneven: description/usage prose is based on a single accessible translation; usages are selected examples and not exhaustive. Chatura/Berunda lack a meaning gloss. The data does not claim a complete Sanskrit etymology.
- Three reference images are registered and locally inspected; all three are attributed to Arpitha05 on Wikimedia Commons under CC BY-SA 4.0. The remaining 49 have no registered image. No training-set photos are treated as verified reference images.
- Gemini was not used as an authority. Sequence generation is deterministic over retrieved database evidence, returns `ai_enhanced=false`, and works without Gemini credentials. It does not create inferred steps.

## Per-record state

| ID | Name | Alternate terms | Category | Description / selected usages | Source | Verification | Image |
|---|---|---|---|---|---|---|---|
| `mudra_pataka` | Pataka | pathaka, Patāka | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_tripataka` | Tripataka | tripathaka, Tripatāka | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_ardhapataka` | Ardhapataka | arthapataka, Ardha-patāka | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_kartarimukha` | Kartarimukha | kartharimukaham, Kartarī-mukha | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_mayura` | Mayura | mayooram, Mayūra | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_ardhachandra` | Ardhachandra | arthachandran, Ardha-candra | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | mudras/ardhachandra.jpg |
| `mudra_arala` | Arala | Arāla | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | mudras/arala.jpg |
| `mudra_sukhatunda` | Sukhatunda | Śuka-tuṇḍaka | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_mushti` | Mushti | mushti, Muṣṭi | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_shikhara` | Shikhara | shikaram, Śikhara | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_kapitha` | Kapitha | kapitham, Kapittha | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_katakamukha` | Katakamukha | Kaṭaka-mukha | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_suchi` | Suchi | soochi, Sūci | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_chandrakala` | Chandrakala | Candra-kalā | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_padmakosha` | Padmakosha | Padma-kośa | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_sarpasirsha` | Sarpasirsha | Sarpa-śīrṣa | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_mrigasirsha` | Mrigasirsha | Mṛga-śīrṣa | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_simhamukham` | Simhamukham | simhamugham, Siṃha-mukha | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_kangula` | Kangula | — | Asamyuta Hasta | Unresolved; no hand form or usage | src_ncert_kriti_i_dance | source_cited | Missing |
| `mudra_allapadma` | Allapadma | Sola-padma, Ala-padma | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | mudras/allapadma.jpg |
| `mudra_chatura` | Chatura | Catura | Asamyuta Hasta | Hand form and selected usage sourced | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_bhramara` | Bhramara | — | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_hamsasya` | Hamsasya | Haṃsāsya | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_hamsapaksha` | Hamsapaksha | Haṃsa-pakṣa | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_samdamsha` | Samdamsha | Saṃdaṃsa | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_mukula` | Mukula | — | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_tamrachuda` | Tamrachuda | Tāmracūḍa | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_trishula` | Trishula | trishoolam, Triśūla | Asamyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_anjali` | Anjali | Añjali | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_kapota` | Kapota | — | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_karkata` | Karkata | Karkaṭa | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_swastika` | Swastika | Svastika | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_dola` | Dola | Ḍola | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_puspaputa` | Puspaputa | Puṣpapuṭa | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_utsanga` | Utsanga | Utsaṅga | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_shivlinga` | Shivlinga | Śiva-liṅga | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_katakavardana` | Katakavardana | Kaṭaka-vardhana | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_kartariswastika` | Kartariswastika | Kartarī-svastika | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_shakata` | Shakata | Śakaṭa | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_shanka` | Shanka | Śaṅkha | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_chakra` | Chakra | Cakra | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_samputa` | Samputa | Sampuṭa | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_pasha` | Pasha | Pāśa | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_keelaka` | Keelaka | Kīlaka | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_matsya` | Matsya | — | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_kurma` | Kurma | Kūrma | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_varaha` | Varaha | Varāha | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_garuda` | Garuda | Garuḍa | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_nagabandha` | Nagabandha | Nāga-bandha | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_khatwa` | Khatwa | Khaṭvā | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_berunda` | Berunda | Bheruṇḍa | Samyuta Hasta | Hand form and selected usage sourced | src_mirror_of_gesture_1917 | source_cited | Missing |
| `mudra_avahitta` | Avahitta | Avahittha | Samyuta Hasta | Hand form and selected usage sourced; meaning gloss present | src_mirror_of_gesture_1917 | source_cited | Missing |

## Sequence generation

`app.services.sequence_generation.generate_mudra_sequence` is the deterministic helper over existing retrieval results. The additive `POST /api/knowledge/sequence` route uses `app.services.multilingual_sequence` to translate sentences when Gemini is configured, extract ordered semantic events, retrieve source-backed matches, and label any catalogue-only AI suggestions. It does not change the existing `/api/knowledge/retrieve` response. Both paths label results as a learning aid, not canonical choreography. The frontend learning page now calls the sequence route and presents translation and ordered steps.

### Required examples (backend service tests)

| Input | Ordered source-backed steps | Unmapped concepts | Result |
|---|---|---|---|
| “The river flows.” | Pataka (river; flow is an additional mapped word where retrieved) | — | Pass; source citation retained, source-cited not teacher-verified |
| “A tree and a crown.” | Tripataka | — | Pass; both concepts resolve to the same mudra |
| “The lotus blooms by the river.” | Allapadma (lotus), Pataka (river) | blooms | Pass; preserves word order, no invented bloom mapping |
| “Krishna is singing and dancing in the garden.” | Hamsasya (singing), Allapadma (dancing) | Krishna, garden | Pass; only curated mappings returned |
| “A zephyr dances.” | Allapadma (dance) | zephyr | Pass; unknown concept remains visible |
| “A river flows. Then clouds cover the river.” | Pataka once; related words include river, flows, clouds | — | Pass; deduplicates repeated mudra and preserves first sentence index |

Each emitted step has source ID/URL and `source_cited` verification status, is marked `source_supported` (cited, not teacher-verified), and `inferred=false`. The test suite also verifies alternate spellings/plurals through extraction and retrieval tests. No test claims canonical choreography or model/Gemini inference.

## Sources and discrepancy notes

- **List of mudras (dance) - Wikipedia** — Wikipedia contributors; https://en.wikipedia.org/wiki/List_of_mudras_(dance). Secondary, crowd-edited source. The page carries a 'multiple issues' banner. Use only until cross-checked with a primary text or a qualified teacher.
- **The Mirror of Gesture, being the Abhinaya Darpana of Nandikesvara** — Ananda Coomaraswamy and Gopala Kristnayya Duggirala (translators), Harvard University Press; https://www.wisdomlib.org/hinduism/book/the-mirror-of-gesture. English translation of Nandikesvara’s Abhinaya Darpana, Ananda Coomaraswamy and Gopala Kristnayya Duggirala translation/editing, Harvard University Press, 1917. Chapters 12 and 13 were checked: 28 single and 24 combined hands, matching project categories; source entry Lāṅgula differs from catalogue Kangula and remains unresolved. Selected first-form descriptions/usages are source-cited; alternative “According to another book” forms stay distinct. No entry is teacher-verified.
- **Kriti-I, Grade 6, Chapter 12: My Body in Motion** — National Council of Educational Research and Training (NCERT); https://ncert.nic.in/textbook.php?fekr1=1-2. The chapter lists 28 Asamyukta and 24 Samyukta hand gestures by name and identifies them as hasta mudras. It cites Abhinaya Darpana for some gestures. Source citation verifies the catalogue name/category only, not every spelling lineage, hand configuration, meaning, or usage.

- Abhinaya Darpana, translated by Ananda Coomaraswamy and Gopala Kristnayya Duggirala, *The Mirror of Gesture* (1917): [Chapter 12](https://www.wisdomlib.org/hinduism/book/the-mirror-of-gesture/d/doc143269.html) and [Chapter 13](https://www.wisdomlib.org/hinduism/book/the-mirror-of-gesture/d/doc143271.html). The translation includes alternate-form passages; the project summarizes selected first-form descriptions and keeps the unresolved Lāṅgula/Kāṅgula issue visible.
- [NCERT Kriti-I, Chapter 12 PDF](https://ncert.nic.in/textbook/pdf/hekr112.pdf), pp. 1–2, presents an educational 28/23 list and uses Kāṅgula. That is retained as a documented discrepancy, not grounds to delete an existing record.

## Workbook cross-check (2026-10-26)

The user-provided `xl.xlsx` was reviewed as a source of candidate data. Its 52 mudra rows correspond by catalogue order to the existing 52 records, with several transliteration/spelling variants. The workbook's `Verified` labels were not used to change verification status. The existing primary-text source record remains the provenance for source-cited claims.

Seven missing concept mappings were added from claims confirmed in Chapters 12–13 of the cited translation: beginning of a dance → Pataka; thunderbolt → Tripataka; corner of the eye → Kartarimukha; peacock → Mayura; crescent moon → Ardhachandra; salutation → Anjali; and flower offering → Pushpaputa. The peacock and crescent-moon records are explicitly described as name/usage associations. Flower offering is marked as a distinct alternate-form usage. All seven remain `source_cited`, not teacher-verified.

The workbook's sequence recipes were not loaded as authoritative choreography: its `Mandatory`/`Sequential` labels are not established by the cited passages, and the current knowledge model has no reviewed choreography-sequence record type. They require teacher review before being presented as traditional rules. The image rows point to a general Wikimedia category rather than per-image source pages; the listed local paths are not all present in the project. They were not imported or treated as proof of image identity, access, or license.

## Limits and remaining work

- Teacher review is required before promoting any record/mapping to verified, confirming naming variants and traditional practice instructions, or presenting a sequence as canonical.
- Individually sourced and licensed reference images are still needed for 49 records. The three registered image files are relatively large Commons originals and should be reviewed for production appropriateness; no crop or alteration was made.
- Live multilingual translation and AI-inferred suggestions require a configured Gemini API key. Without it, translations are marked unavailable and the backend falls back to deterministic source-backed matches.
- Existing `/api/knowledge/retrieve` responses remain compatible; the sequence feature has its own additive request and response contract.
