/**
 * The ONLY place the frontend talks to the backend.
 *
 * Components never call fetch() directly. They call a service function
 * (services/*.ts), which calls apiRequest() or uploadWithProgress() here.
 * This gives us one place for: the base URL, timeouts, cancellation,
 * FastAPI error parsing, response validation and dev mock mode.
 */
import { config } from "./config";
import type { Validator } from "./validators";
import { ApiError, type ApiErrorKind } from "@/types/api";
import { handleMockRequest } from "./mock-api";

export interface RequestOptions<T> {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  /** JSON body (sent with Content-Type: application/json). */
  json?: unknown;
  /** Runtime check for the response body. Strongly recommended. */
  validate?: Validator<T>;
  timeoutMs?: number;
  /** Lets the caller cancel (e.g. when the component unmounts). */
  signal?: AbortSignal;
}

/** Map an HTTP status to an error kind. */
export function kindForStatus(status: number): ApiErrorKind {
  if (status === 404) return "not_found";
  if (status === 413) return "too_large";
  if (status === 422 || status === 400) return "validation";
  if (status === 503 || status === 502 || status === 504) return "unavailable";
  return "http";
}

/**
 * FastAPI errors look like {"detail": "text"} or, for validation errors,
 * {"detail": [{"loc": [...], "msg": "...", ...}]}. Turn either into one line.
 */
export function parseFastApiDetail(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const message = (detail as { message?: unknown }).message;
    return typeof message === "string" ? message : null;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => {
        if (!d || typeof d !== "object") return null;
        const item = d as { msg?: unknown; loc?: unknown };
        const field = Array.isArray(item.loc) ? item.loc.filter((p) => p !== "body").join(".") : "";
        return typeof item.msg === "string" ? (field ? `${field}: ${item.msg}` : item.msg) : null;
      })
      .filter(Boolean);
    return messages.length ? messages.join("; ") : null;
  }
  return null;
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** Combine a caller's AbortSignal with our timeout. */
function withTimeout(timeoutMs: number, external?: AbortSignal) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onExternalAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", onExternalAbort, { once: true });
  }
  return {
    signal: controller.signal,
    didTimeOut: () => timedOut,
    cleanup: () => {
      clearTimeout(timer);
      external?.removeEventListener("abort", onExternalAbort);
    },
  };
}

function checkShape<T>(body: unknown, validate: Validator<T> | undefined, path: string): T {
  if (validate && !validate(body)) {
    // Logged for developers; users see a short message via describeError().
    console.error(`[api] Malformed response from ${path}`, body);
    throw new ApiError("malformed", `Malformed response from ${path}`);
  }
  return body as T;
}

export async function apiRequest<T>(path: string, options: RequestOptions<T> = {}): Promise<T> {
  const method = options.method ?? (options.json !== undefined ? "POST" : "GET");

  if (config.useMockApi) {
    const body = await handleMockRequest(method, path, options.json);
    return checkShape(body, options.validate, path);
  }

  const timer = withTimeout(options.timeoutMs ?? config.requestTimeoutMs, options.signal);
  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, {
      method,
      headers: options.json !== undefined ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
      body: options.json !== undefined ? JSON.stringify(options.json) : undefined,
      signal: timer.signal,
    });
  } catch {
    if (timer.didTimeOut()) throw new ApiError("timeout", `Request to ${path} timed out`);
    if (options.signal?.aborted) throw new ApiError("aborted", "Request cancelled");
    throw new ApiError("network", `Could not reach ${config.apiBaseUrl}`);
  } finally {
    timer.cleanup();
  }

  const body = await readBody(response);
  if (!response.ok) {
    throw new ApiError(kindForStatus(response.status), `HTTP ${response.status} from ${path}`, response.status, parseFastApiDetail(body));
  }
  return checkShape(body, options.validate, path);
}

export interface UploadOptions<T> {
  validate?: Validator<T>;
  timeoutMs?: number;
  /** Called with a number from 0 to 1 as bytes are sent. */
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
}

/**
 * Multipart upload with progress. fetch() cannot report upload progress, so
 * this one function uses XMLHttpRequest instead.
 */
export function uploadWithProgress<T>(path: string, formData: FormData, options: UploadOptions<T> = {}): Promise<T> {
  if (config.useMockApi) {
    return (async () => {
      for (const step of [0.25, 0.5, 0.75, 1]) {
        await new Promise((r) => setTimeout(r, 150));
        options.onProgress?.(step);
      }
      const body = await handleMockRequest("POST", path, null);
      return checkShape(body, options.validate, path);
    })();
  }

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${config.apiBaseUrl}${path}`);
    xhr.timeout = options.timeoutMs ?? config.longRequestTimeoutMs;
    xhr.setRequestHeader("Accept", "application/json");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) options.onProgress?.(event.loaded / event.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = xhr.responseText;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new ApiError(kindForStatus(xhr.status), `HTTP ${xhr.status} from ${path}`, xhr.status, parseFastApiDetail(body)));
        return;
      }
      try {
        resolve(checkShape(body, options.validate, path));
      } catch (e) {
        reject(e);
      }
    };
    xhr.onerror = () => reject(new ApiError("network", `Could not reach ${config.apiBaseUrl}`));
    xhr.ontimeout = () => reject(new ApiError("timeout", `Upload to ${path} timed out`));
    xhr.onabort = () => reject(new ApiError("aborted", "Upload cancelled"));

    if (options.signal) {
      if (options.signal.aborted) {
        xhr.abort();
        return;
      }
      options.signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(formData);
  });
}
