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
