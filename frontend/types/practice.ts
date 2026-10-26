/** Practice reference + session types (see docs/api-contract.md). */

export type ReferenceType = "mudra" | "sequence";

/** GET /api/movements — references that can actually be practised and evaluated. */
export interface PracticeReference {
  id: number;
  name: string;
  reference_type: ReferenceType;
  description: string | null;
  /** Ordered mudra IDs. One item for a single mudra, several for a sequence. */
  mudra_ids: number[];
  image_url: string | null;
  /** Optional per-reference recording limit; falls back to the app config. */
  max_duration_seconds: number | null;
}

export type SessionStatus = "created" | "uploaded" | "processing" | "evaluated" | "failed";

/** POST /api/practice/sessions */
export interface CreateSessionRequest {
  reference_id: number;
}

/** Returned by session creation and video upload. */
export interface PracticeSession {
  session_id: number;
  reference_id: number;
  status: SessionStatus;
  created_at: string;
}
