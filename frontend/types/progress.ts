/** GET /api/progress (see docs/api-contract.md). */
import type { SessionStatus } from "./practice";

export interface ProgressEntry {
  session_id: number | string;
  reference_id: number | string;
  reference_name: string;
  status: SessionStatus;
  created_at: string;
  /** Only present when the backend computed it for this session. */
  dtw_normalized: number | null;
  top_label: string | null;
  top_confidence: number | null;
  feedback_summary: string | null;
}

export interface ProgressResponse {
  scope: "shared_development";
  sessions: ProgressEntry[];
}
