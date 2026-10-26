/** Evaluation, results and feedback. */
import { apiRequest } from "@/lib/api-client";
import { endpoints } from "@/lib/api-endpoints";
import { config } from "@/lib/config";
import { isEvaluateResponse, isFeedback, isSessionResults } from "@/lib/validators";
import { ApiError } from "@/types/api";
import type { EvaluateResponse, Feedback, SessionResults } from "@/types/evaluation";

export function startEvaluation(sessionId: number, signal?: AbortSignal): Promise<EvaluateResponse> {
  return apiRequest(endpoints.sessionEvaluate(sessionId), {
    method: "POST",
    json: {},
    validate: isEvaluateResponse,
    timeoutMs: config.longRequestTimeoutMs,
    signal,
  });
}

export function getSessionResults(sessionId: number | string, signal?: AbortSignal): Promise<SessionResults> {
  return apiRequest(endpoints.sessionResults(sessionId), { validate: isSessionResults, signal });
}

export function requestFeedback(sessionId: number | string, signal?: AbortSignal): Promise<Feedback> {
  return apiRequest(endpoints.sessionFeedback(sessionId), {
    method: "POST",
    json: {},
    validate: isFeedback,
    timeoutMs: config.longRequestTimeoutMs,
    signal,
  });
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new ApiError("aborted", "Polling cancelled"));
    }, { once: true });
  });

/**
 * Start evaluation and, if the backend answers "processing", poll the results
 * endpoint until it is evaluated, failed, or we give up.
 */
export async function evaluateAndWait(sessionId: number, signal?: AbortSignal): Promise<SessionResults> {
  const first = await startEvaluation(sessionId, signal);
  if (first.status === "failed") {
    throw new ApiError("http", "Evaluation failed", null, first.error ?? "The evaluation could not be completed.");
  }

  const deadline = Date.now() + config.evaluationPollTimeoutMs;
  for (;;) {
    const results = await getSessionResults(sessionId, signal);
    if (results.session.status === "evaluated" && results.result) return results;
    if (results.session.status === "failed") {
      throw new ApiError("http", "Evaluation failed", null, "The evaluation could not be completed. Try recording again.");
    }
    if (Date.now() > deadline) {
      throw new ApiError("timeout", "Evaluation is still processing", null, null);
    }
    await sleep(config.evaluationPollIntervalMs, signal);
  }
}
