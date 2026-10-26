/**
 * Knowledge-base types. These mirror the FastAPI/Pydantic schemas documented
 * in docs/api-contract.md. If the backend schema changes, update both.
 */

export type HastaType = "asamyuta" | "samyuta";
export type VerificationStatus = "verified" | "unverified" | "needs_review";

export interface CatalogueSource {
  id: string;
  source_name: string;
  source_url: string | null;
}

export interface DatasetClassMapping {
  dataset_folder: string;
  original_label: string;
  variant_id: string | null;
  image_count: number;
  mapping_status: string;
}

/** GET /api/mudras records as returned by the backend's 52-entry catalogue. */
export interface CatalogueMudra {
  id: string;
  name: string;
  alternate_names: string[];
  category: string;
  meaning: string | null;
  usage: string[];
  description: string | null;
  practice_instructions: string | null;
  reference_image_path: string | null;
  dataset_image_count: number;
  dataset_images_available: boolean;
  dataset_classes: DatasetClassMapping[];
  recognition_supported: boolean;
  source: CatalogueSource | null;
  verification_status: "verified" | "source_cited" | "unverified";
  verification_notes: string | null;
  limitations: string[];
}

/** GET /api/mudras (list item) and embedded mudra references. */
export interface MudraSummary {
  id: number | string;
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

export interface BackendRetrievalResponse {
  original_text: string;
  concepts: {
    concept: { text: string };
    status: string;
    references: {
      record_type: string;
      record_id: string;
      name: string;
      category: string;
      meaning: string | null;
      description: string | null;
      reference_media_path: string | null;
      match_type: string;
      evidence_notes: string[];
      verification_status: string;
      source: { source_name: string } | null;
    }[];
  }[];
}

/** POST /api/tutor/explain */
export interface ExplainRequest {
  text: string;
}

export interface TutorExplainResponse {
  original_text: string;
  tutor: {
    mode: "ai" | "knowledge_only";
    explanation: {
      summary: string;
      concepts: { concept: string; supported: boolean; explanation: string; source_ids: string[] }[];
      suggestions: string[];
      alternatives: string[];
      source_ids: string[];
      limitations: string[];
    };
    model: string | null;
    fallback_reason: string | null;
    notice: string | null;
  };
  retrieval: unknown;
  disclaimer: string;
}

export interface ExplainResponse {
  /** Compatibility name retained for current UI component imports. */
  original_text: string;
  tutor: TutorExplainResponse["tutor"];
  retrieval: unknown;
  disclaimer: string;
}
