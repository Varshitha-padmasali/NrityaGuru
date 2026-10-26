/** Knowledge base + AI tutor calls. All Gemini access happens on the backend. */
import { apiRequest } from "@/lib/api-client";
import { endpoints } from "@/lib/api-endpoints";
import { isBackendRetrievalResponse, isCatalogueMudra, isCatalogueMudraList, isExplainResponse, isHealth } from "@/lib/validators";
import { config } from "@/lib/config";
import type { HealthResponse } from "@/types/api";
import type { BackendRetrievalResponse, CatalogueMudra, ExplainResponse, RetrieveResponse } from "@/types/knowledge";

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
  return apiRequest<BackendRetrievalResponse>(endpoints.retrieve(), {
    method: "POST", json: { text: text.trim(), include_unverified: true },
    validate: isBackendRetrievalResponse, signal,
  }).then((response) => ({
    query: response.original_text,
    concepts: response.concepts.map((item) => ({
      concept: item.concept.text,
      supported: item.status === "supported",
      matches: item.references.filter((ref) => ref.record_type === "mudra").map((ref) => ({
        id: ref.record_id,
        name: ref.name,
        hasta_type: ref.category.toLowerCase().includes("asamyuta") ? "asamyuta" : "samyuta",
        meaning: ref.meaning,
        image_url: ref.reference_media_path,
        rationale: ref.evidence_notes.join("; ") || ref.match_type,
        source: ref.source?.source_name ?? null,
      })),
    })),
  }));
}

export function listMudras(signal?: AbortSignal): Promise<CatalogueMudra[]> {
  return apiRequest(`${endpoints.mudras()}?include_unverified=true&limit=100`, { validate: isCatalogueMudraList, signal });
}

export function getMudra(id: number | string, signal?: AbortSignal): Promise<CatalogueMudra> {
  return apiRequest(`${endpoints.mudra(id)}?include_unverified=true`, { validate: isCatalogueMudra, signal });
}

export function explainConcepts(text: string, signal?: AbortSignal): Promise<ExplainResponse> {
  return apiRequest(endpoints.explain(), {
    method: "POST",
    json: { text: text.trim(), include_unverified: true },
    validate: isExplainResponse,
    timeoutMs: config.longRequestTimeoutMs, // LLM calls can be slow
    signal,
  });
}
