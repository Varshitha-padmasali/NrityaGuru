/** Knowledge base + AI tutor calls. All Gemini access happens on the backend. */
import { apiRequest } from "@/lib/api-client";
import { endpoints } from "@/lib/api-endpoints";
import { isExplainResponse, isHealth, isMudraDetail, isMudraList, isRetrieveResponse } from "@/lib/validators";
import { config } from "@/lib/config";
import type { HealthResponse } from "@/types/api";
import type { ExplainResponse, MudraDetail, MudraSummary, RetrieveResponse } from "@/types/knowledge";

export const MIN_QUERY_LENGTH = 3;
export const MAX_QUERY_LENGTH = 500;

/** Returns an error message, or null if the text is acceptable. */
export function validateLearningQuery(text: string): string | null {
  const trimmed = text.trim();
  if (trimmed.length === 0) return "Enter a sentence, a line of lyrics or a concept to explore.";
  if (trimmed.length < MIN_QUERY_LENGTH) return `Please enter at least ${MIN_QUERY_LENGTH} characters.`;
  if (trimmed.length > MAX_QUERY_LENGTH) return `Please keep it under ${MAX_QUERY_LENGTH} characters.`;
  return null;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest(endpoints.health(), { validate: isHealth, timeoutMs: 5_000, signal });
}

export function retrieveKnowledge(text: string, signal?: AbortSignal): Promise<RetrieveResponse> {
  return apiRequest(endpoints.retrieve(), { method: "POST", json: { text: text.trim() }, validate: isRetrieveResponse, signal });
}

export function listMudras(signal?: AbortSignal): Promise<MudraSummary[]> {
  return apiRequest(endpoints.mudras(), { validate: isMudraList, signal });
}

export function getMudra(id: number | string, signal?: AbortSignal): Promise<MudraDetail> {
  return apiRequest(endpoints.mudra(id), { validate: isMudraDetail, signal });
}

export function explainConcepts(text: string, mudraIds: number[], signal?: AbortSignal): Promise<ExplainResponse> {
  return apiRequest(endpoints.explain(), {
    method: "POST",
    json: { text: text.trim(), mudra_ids: mudraIds },
    validate: isExplainResponse,
    timeoutMs: config.longRequestTimeoutMs, // LLM calls can be slow
    signal,
  });
}
