/**
 * Knowledge-base types. These mirror the FastAPI/Pydantic schemas documented
 * in docs/api-contract.md. If the backend schema changes, update both.
 */

export type HastaType = "asamyuta" | "samyuta";
export type VerificationStatus = "verified" | "unverified" | "needs_review";

/** GET /api/mudras (list item) and embedded mudra references. */
export interface MudraSummary {
  id: number;
  name: string;
  hasta_type: HastaType | null;
  meaning: string | null;
  /** Absolute URL or a path relative to the backend, e.g. "/static/mudras/pataka.jpg". */
  image_url: string | null;
}

/** GET /api/mudras/{id} */
export interface MudraDetail extends MudraSummary {
  alt_names: string[];
  usage: string | null;
  instructions: string | null;
  source: string | null;
  verification_status: VerificationStatus;
  /** ID of a practice reference (GET /api/movements) for this mudra, or null if it cannot be evaluated yet. */
  practice_reference_id: number | null;
}

/** A mudra matched to a concept, with the knowledge base's reason for the match. */
export interface ConceptMudraMatch extends MudraSummary {
  rationale: string | null;
  source: string | null;
}

export interface ConceptResult {
  concept: string;
  /** false = the knowledge base has no supported mapping for this concept. */
  supported: boolean;
  /** More than one match = alternative interpretations. */
  matches: ConceptMudraMatch[];
}

/** POST /api/knowledge/retrieve */
export interface RetrieveRequest {
  text: string;
}
export interface RetrieveResponse {
  query: string;
  concepts: ConceptResult[];
}

/** POST /api/tutor/explain */
export interface ExplainRequest {
  text: string;
  mudra_ids: number[];
}
export interface ExplainResponse {
  explanation: string;
  used_mudra_ids: number[];
  unsupported_concepts: string[];
  model_name: string;
}

/** POST /api/knowledge/sequence: ordered semantic interpretation of input text. */
export interface SequenceTranslation {
  position: number;
  original_sentence: string;
  english_translation: string | null;
  translated: boolean;
  note: string | null;
}
export interface SequenceCitation {
  source_id: string;
  title: string;
  url: string | null;
  claim_scope: string;
}
export interface SequenceStep {
  position: number;
  event_order: number;
  original_text: string;
  language: string;
  phrase: string;
  related_phrases: string[];
  event_orders: number[];
  concepts: string[];
  mudra_id: string;
  mudra_name: string;
  alternate_names: string[];
  hand_position_description: string | null;
  selection_reason: string;
  additional_selection_reasons: string[];
  context: string;
  source_citations: SequenceCitation[];
  verification_status: string;
  image_url: string | null;
  selection_type: "teacher_verified" | "source_supported" | "ai_inferred";
  confidence: number;
  confidence_meaning: string;
  uncertainty_notes: string[];
}
export interface UnmappedSequenceConcept {
  event_order: number;
  phrase: string;
  concept: string;
  reason: string;
}
export interface SequenceResponse {
  original_input: string;
  detected_language: { code: string; name: string; confidence: number | null; detection_method: string };
  sentence_translations: SequenceTranslation[];
  events: Array<{ order: number; phrase: string; event_type: string; concepts: string[]; lookup_terms: string[]; negated: boolean; tense: string; relations: string[]; context: string }>;
  ordered_sequence: SequenceStep[];
  unmapped_concepts: UnmappedSequenceConcept[];
  interpretation_caveats: string[];
  gemini_used: boolean;
  mode: "knowledge_base" | "ai_assisted";
  catalogue_mode: "all" | "eight_mudra";
  disclaimer: string;
}
