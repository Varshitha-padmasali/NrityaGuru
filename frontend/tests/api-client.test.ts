import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, parseFastApiDetail } from "@/lib/api-client";
import { isRetrieveResponse } from "@/lib/validators";
import { retrieveKnowledge, validateLearningQuery } from "@/services/knowledge-service";
import { evaluateAndWait } from "@/services/evaluation-service";
import { ApiError, describeError } from "@/types/api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mockFetch(...responses: Array<Response | Error>) {
  const fn = vi.fn();
  responses.forEach((r) => (r instanceof Error ? fn.mockRejectedValueOnce(r) : fn.mockResolvedValueOnce(r)));
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const validRetrieve = {
  query: "a lotus",
  concepts: [{ concept: "lotus", supported: true, matches: [{ id: 1, name: "Alapadma", hasta_type: "asamyuta", meaning: "Lotus", image_url: null, rationale: null, source: "KB" }] }],
};

describe("apiRequest", () => {
  it("returns the validated body on success and posts JSON", async () => {
    const fetchMock = mockFetch(jsonResponse(validRetrieve));
    const result = await retrieveKnowledge("  a lotus ");
    expect(result.concepts[0].matches[0].name).toBe("Alapadma");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/knowledge/retrieve");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ text: "a lotus" });
  });

  it("raises 'malformed' when the body does not match the agreed schema", async () => {
    mockFetch(jsonResponse({ results: [] }));
    await expect(apiRequest("/api/knowledge/retrieve", { validate: isRetrieveResponse })).rejects.toMatchObject({ kind: "malformed" });
  });

  it("parses FastAPI 422 validation errors", async () => {
    mockFetch(jsonResponse({ detail: [{ loc: ["body", "text"], msg: "String should have at least 3 characters" }] }, 422));
    const error = (await apiRequest("/x").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.kind).toBe("validation");
    expect(error.detail).toBe("text: String should have at least 3 characters");
  });

  it("maps 503 to 'unavailable' (e.g. Gemini down)", async () => {
    mockFetch(jsonResponse({ detail: "AI tutor temporarily unavailable" }, 503));
    const error = (await apiRequest("/x").catch((e: unknown) => e)) as ApiError;
    expect(error.kind).toBe("unavailable");
    expect(describeError(error)).toBe("AI tutor temporarily unavailable");
  });

  it("maps a failed fetch to 'network'", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    await expect(apiRequest("/x")).rejects.toMatchObject({ kind: "network" });
  });

  it("times out slow requests", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => new Promise((_, reject) => init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))))),
    );
    const pending = apiRequest("/slow", { timeoutMs: 1000 }).catch((e: unknown) => e as ApiError);
    await vi.advanceTimersByTimeAsync(1001);
    expect(((await pending) as ApiError).kind).toBe("timeout");
  });
});

describe("parseFastApiDetail", () => {
  it("handles string, list and missing details", () => {
    expect(parseFastApiDetail({ detail: "Not found" })).toBe("Not found");
    expect(parseFastApiDetail({ detail: [{ loc: ["body"], msg: "bad" }] })).toBe("bad");
    expect(parseFastApiDetail({})).toBeNull();
    expect(parseFastApiDetail("text")).toBeNull();
  });
});

describe("validateLearningQuery", () => {
  it("rejects empty, too short and too long input", () => {
    expect(validateLearningQuery("   ")).toMatch(/enter a sentence/i);
    expect(validateLearningQuery("ab")).toMatch(/at least 3/);
    expect(validateLearningQuery("a".repeat(501))).toMatch(/under 500/);
    expect(validateLearningQuery("A peacock dances")).toBeNull();
  });
});

describe("evaluateAndWait", () => {
  const session = (status: string) => ({ session_id: 5, reference_id: 1, status, created_at: "2026-10-24T10:00:00Z" });
  const result = {
    reference: { id: 1, name: "Pataka" },
    predictions: [],
    dtw: { distance: 12.5, normalized: 0.2, path_length: 60 },
    frames_total: 60,
    frames_with_landmarks: 58,
    fps: 30,
    deviations: [],
    warnings: [],
    model_version: "mlp-v1",
    feature_schema: "hand_v1",
    created_at: "2026-10-24T10:00:05Z",
  };

  it("polls while processing and returns once evaluated", async () => {
    vi.useFakeTimers();
    mockFetch(
      jsonResponse({ session_id: 5, status: "processing", result: null, error: null }),
      jsonResponse({ session: session("processing"), result: null, feedback: null }),
      jsonResponse({ session: session("evaluated"), result, feedback: null }),
    );
    const pending = evaluateAndWait(5);
    await vi.advanceTimersByTimeAsync(2100);
    const done = await pending;
    expect(done.result?.dtw?.distance).toBe(12.5);
  });

  it("throws with the backend's message when evaluation fails", async () => {
    mockFetch(jsonResponse({ session_id: 5, status: "failed", result: null, error: "No hands detected" }));
    await expect(evaluateAndWait(5)).rejects.toMatchObject({ detail: "No hands detected" });
  });
});
