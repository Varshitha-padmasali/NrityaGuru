/**
 * Practice workflow state machine.
 *
 * The practice page can only be in ONE of these phases at a time. Every user
 * action becomes an event, and `practiceReducer` only accepts events that make
 * sense in the current phase. Anything else is ignored, which is what stops
 * double uploads, recording before the camera is ready, and so on.
 *
 *   idle ──REQUEST_CAMERA──▶ requesting_camera ──CAMERA_READY──▶ camera_ready
 *   camera_ready ──START_RECORDING──▶ recording ──RECORDING_DONE──▶ recorded
 *   recorded ──RETAKE──▶ camera_ready
 *   recorded ──SUBMIT──▶ uploading ──UPLOAD_DONE──▶ processing ──EVALUATION_DONE──▶ completed
 *   (most phases) ──FAIL──▶ error ──RETRY──▶ previous safe phase
 */

export type PracticePhase =
  | "idle"
  | "requesting_camera"
  | "camera_ready"
  | "recording"
  | "recorded"
  | "uploading"
  | "processing"
  | "completed"
  | "error";

export interface PracticeState {
  phase: PracticePhase;
  /** Upload progress, 0..1 (only meaningful while uploading). */
  uploadProgress: number;
  sessionId: number | null;
  error: string | null;
  /** Where RETRY returns to from the error phase. */
  recoverTo: PracticePhase;
}

export type PracticeEvent =
  | { type: "REQUEST_CAMERA" }
  | { type: "CAMERA_READY" }
  | { type: "START_RECORDING" }
  | { type: "RECORDING_DONE" }
  | { type: "RETAKE" }
  | { type: "SUBMIT" }
  | { type: "UPLOAD_PROGRESS"; progress: number }
  | { type: "UPLOAD_DONE"; sessionId: number }
  | { type: "EVALUATION_DONE"; sessionId: number }
  | { type: "FAIL"; message: string; recoverTo: PracticePhase }
  | { type: "RETRY" }
  | { type: "RESET" };

export const initialPracticeState: PracticeState = {
  phase: "idle",
  uploadProgress: 0,
  sessionId: null,
  error: null,
  recoverTo: "idle",
};

/** Which events each phase accepts (FAIL and RESET are handled separately). */
const ALLOWED: Record<PracticePhase, PracticeEvent["type"][]> = {
  idle: ["REQUEST_CAMERA"],
  requesting_camera: ["CAMERA_READY"],
  camera_ready: ["START_RECORDING"],
  recording: ["RECORDING_DONE"],
  recorded: ["RETAKE", "SUBMIT"],
  uploading: ["UPLOAD_PROGRESS", "UPLOAD_DONE"],
  processing: ["EVALUATION_DONE"],
  completed: ["RETAKE"],
  error: ["RETRY"],
};

export function canTransition(phase: PracticePhase, event: PracticeEvent["type"]): boolean {
  if (event === "RESET") return true;
  if (event === "FAIL") return phase !== "idle" && phase !== "completed" && phase !== "error";
  return ALLOWED[phase].includes(event);
}

export function practiceReducer(state: PracticeState, event: PracticeEvent): PracticeState {
  if (!canTransition(state.phase, event.type)) return state; // invalid → ignore

  switch (event.type) {
    case "REQUEST_CAMERA":
      return { ...state, phase: "requesting_camera", error: null };
    case "CAMERA_READY":
      return { ...state, phase: "camera_ready" };
    case "START_RECORDING":
      return { ...state, phase: "recording", error: null };
    case "RECORDING_DONE":
      return { ...state, phase: "recorded" };
    case "RETAKE":
      return { ...state, phase: "camera_ready", uploadProgress: 0, error: null };
    case "SUBMIT":
      return { ...state, phase: "uploading", uploadProgress: 0, error: null };
    case "UPLOAD_PROGRESS":
      return { ...state, uploadProgress: Math.min(1, Math.max(0, event.progress)) };
    case "UPLOAD_DONE":
      return { ...state, phase: "processing", uploadProgress: 1, sessionId: event.sessionId };
    case "EVALUATION_DONE":
      return { ...state, phase: "completed", sessionId: event.sessionId };
    case "FAIL":
      return { ...state, phase: "error", error: event.message, recoverTo: event.recoverTo };
    case "RETRY":
      return { ...state, phase: state.recoverTo, error: null };
    case "RESET":
      return initialPracticeState;
  }
}
