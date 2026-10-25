/**
 * Shared API error type. Every failure from the API layer is converted into an
 * ApiError so components can show one consistent, friendly message.
 */

export type ApiErrorKind =
  | "network" // backend unreachable / CORS / offline
  | "timeout" // request took longer than the configured timeout
  | "validation" // 422 from FastAPI (bad input)
  | "not_found" // 404
  | "too_large" // 413 (video too big)
  | "unavailable" // 503 (e.g. Gemini temporarily unavailable)
  | "http" // any other non-2xx status
  | "malformed" // 2xx response whose body does not match the agreed schema
  | "aborted"; // cancelled by the UI (navigation, retake)

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly detail: string | null;

  constructor(kind: ApiErrorKind, message: string, status: number | null = null, detail: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

export interface HealthResponse {
  status: "ok" | "degraded";
  db?: "ok" | "error";
  model_loaded?: boolean;
}

/** Turn any thrown value into a sentence suitable for the UI. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.kind) {
      case "network":
        return "Could not reach the NrityaGuru server. Check that the backend is running and try again.";
      case "timeout":
        return "The server took too long to respond. Please try again in a moment.";
      case "validation":
        return error.detail ? `Please check your input: ${error.detail}` : "Please check your input and try again.";
      case "not_found":
        return error.detail ?? "We couldn't find what you were looking for.";
      case "too_large":
        return "The recording is too large to upload. Try a shorter recording.";
      case "unavailable":
        return error.detail ?? "This service is temporarily unavailable. Please try again shortly.";
      case "malformed":
        return "The server sent a response the app didn't understand. This is a bug — please report it.";
      case "aborted":
        return "The request was cancelled.";
      default:
        return error.detail ?? `Something went wrong (status ${error.status ?? "unknown"}).`;
    }
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
