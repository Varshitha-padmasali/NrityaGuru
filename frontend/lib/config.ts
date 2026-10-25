/**
 * Central frontend configuration.
 *
 * Every value comes from a NEXT_PUBLIC_* environment variable so that it can be
 * changed without touching code. NEXT_PUBLIC_* values are embedded into the
 * browser bundle at build time, so NEVER put secrets (like the Gemini API key)
 * here. All Gemini calls go through the FastAPI backend.
 */

function readNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export const config = {
  /** Base URL of the FastAPI backend, without a trailing slash. */
  apiBaseUrl: (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, ""),

  /**
   * Development-only mock mode. When "true", the API client answers from
   * lib/mock-api.ts instead of the backend and the UI shows a visible banner.
   * Must be "false" for any real demo or evaluation.
   */
  useMockApi: process.env.NEXT_PUBLIC_USE_MOCK_API === "true",

  /** Default timeout for normal JSON requests (ms). */
  requestTimeoutMs: readNumber(process.env.NEXT_PUBLIC_REQUEST_TIMEOUT_MS, 20_000),

  /** Timeout for video upload + evaluation calls (ms). */
  longRequestTimeoutMs: readNumber(process.env.NEXT_PUBLIC_LONG_REQUEST_TIMEOUT_MS, 120_000),

  /** Maximum recording length before the recorder stops automatically (s). */
  maxRecordingSeconds: readNumber(process.env.NEXT_PUBLIC_MAX_RECORDING_SECONDS, 8),

  /** Maximum upload size (MB). Must match the backend limit. */
  maxUploadMb: readNumber(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB, 10),

  /** How long to keep polling when evaluation is still processing (ms). */
  evaluationPollTimeoutMs: readNumber(process.env.NEXT_PUBLIC_EVALUATION_POLL_TIMEOUT_MS, 90_000),
  evaluationPollIntervalMs: 2_000,
} as const;

/**
 * Turn an image/media path returned by the backend into a URL the browser can
 * load. Absolute URLs are used as-is; relative paths ("/static/mudras/x.jpg")
 * are resolved against the backend base URL.
 */
export function resolveMediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path) || path.startsWith("data:") || path.startsWith("blob:")) return path;
  if (config.useMockApi) return null; // mock mode never pretends to have real reference images
  return `${config.apiBaseUrl}${path.startsWith("/") ? "" : "/"}${path}`;
}
