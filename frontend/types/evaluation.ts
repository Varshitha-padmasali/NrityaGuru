/** Evaluation + feedback types (see docs/api-contract.md). */
import type { PracticeSession } from "./practice";

/** One stretch of frames the MLP classified as a single label. */
export interface Prediction {
  label: string;
  /** Model probability between 0 and 1 (not "correctness"). */
  confidence: number;
  frame_start: number;
  frame_end: number;
}

export interface DtwResult {
  /** Raw DTW alignment cost. Lower = more similar to the reference. No fixed upper bound. */
  distance: number;
  /** Optional normalised value defined by the backend (e.g. distance / path length). */
  normalized: number | null;
  path_length: number;
}

export type DeviationKind =
  | "wrong_label"
  | "feature_deviation"
  | "high_alignment_cost"
  | "insufficient_landmarks";

export interface Deviation {
  kind: DeviationKind;
  message: string;
  frame_start: number | null;
  frame_end: number | null;
  expected_label: string | null;
  predicted_label: string | null;
}

export interface EvaluationResult {
  reference: { id: number; name: string };
  predictions: Prediction[];
  dtw: DtwResult | null;
  frames_total: number;
  frames_with_landmarks: number;
  fps: number | null;
  deviations: Deviation[];
  warnings: string[];
  model_version: string;
  feature_schema: string;
  created_at: string;
}

/** POST /api/practice/sessions/{id}/evaluate */
export interface EvaluateResponse {
  session_id: number;
  status: "evaluated" | "processing" | "failed";
  result: EvaluationResult | null;
  error: string | null;
}

export interface Feedback {
  text: string;
  model_name: string;
  created_at: string;
}

/** GET /api/practice/sessions/{id}/results */
export interface SessionResults {
  session: PracticeSession;
  result: EvaluationResult | null;
  feedback: Feedback | null;
}
