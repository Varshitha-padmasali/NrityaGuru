/**
 * Lightweight runtime checks for backend responses.
 *
 * TypeScript types disappear at runtime, so a backend that sends the wrong
 * shape would otherwise crash a component deep in the tree. These guards check
 * the fields the UI depends on and let the API client raise a clear
 * "malformed response" error instead. They are intentionally small — no extra
 * validation library is needed.
 */
import type { HealthResponse } from "@/types/api";
import type { MudraDetail, MudraSummary, RetrieveResponse, ExplainResponse, SequenceResponse } from "@/types/knowledge";
import type { PracticeReference, PracticeSession } from "@/types/practice";
import type { EvaluateResponse, EvaluationResult, Feedback, SessionResults } from "@/types/evaluation";
import type { ProgressResponse } from "@/types/progress";

export type Validator<T> = (value: unknown) => value is T;

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isNullable = <T>(guard: (v: unknown) => v is T) => (v: unknown): v is T | null => v === null || guard(v);
const isArrOf = <T>(guard: (v: unknown) => boolean) => (v: unknown): v is T[] => Array.isArray(v) && v.every(guard);

export const isHealth: Validator<HealthResponse> = (v): v is HealthResponse => isObj(v) && isStr(v.status);

export const isMudraSummary: Validator<MudraSummary> = (v): v is MudraSummary =>
  isObj(v) && isNum(v.id) && isStr(v.name) && isNullable(isStr)(v.meaning ?? null) && isNullable(isStr)(v.image_url ?? null);

export const isMudraList: Validator<MudraSummary[]> = (v): v is MudraSummary[] => isArrOf<MudraSummary>(isMudraSummary)(v);

export const isMudraDetail: Validator<MudraDetail> = (v): v is MudraDetail =>
  isMudraSummary(v) &&
  isObj(v) &&
  Array.isArray(v.alt_names) &&
  isStr(v.verification_status) &&
  isNullable(isNum)(v.practice_reference_id ?? null);

export const isRetrieveResponse: Validator<RetrieveResponse> = (v): v is RetrieveResponse =>
  isObj(v) &&
  Array.isArray(v.concepts) &&
  v.concepts.every((c) => isObj(c) && isStr(c.concept) && typeof c.supported === "boolean" && isArrOf(isMudraSummary)(c.matches));

export const isExplainResponse: Validator<ExplainResponse> = (v): v is ExplainResponse =>
  isObj(v) && isStr(v.explanation) && Array.isArray(v.used_mudra_ids) && Array.isArray(v.unsupported_concepts);

export const isSequenceResponse: Validator<SequenceResponse> = (v): v is SequenceResponse =>
  isObj(v) &&
  isStr(v.original_input) && isObj(v.detected_language) && isStr(v.detected_language.code) && isStr(v.detected_language.name) &&
  Array.isArray(v.sentence_translations) && v.sentence_translations.every((t) => isObj(t) && isNum(t.position) && isStr(t.original_sentence) && isNullable(isStr)(t.english_translation) && typeof t.translated === "boolean") &&
  Array.isArray(v.ordered_sequence) && v.ordered_sequence.every((s) => isObj(s) && isNum(s.position) && isStr(s.mudra_id) && isStr(s.mudra_name) && isStr(s.phrase) && isStr(s.selection_reason) && isStr(s.selection_type) && isNum(s.confidence) && Array.isArray(s.source_citations) && s.source_citations.every((c) => isObj(c) && isStr(c.title))) &&
  Array.isArray(v.unmapped_concepts) && v.unmapped_concepts.every((c) => isObj(c) && isStr(c.concept) && isStr(c.reason)) &&
  Array.isArray(v.interpretation_caveats) && v.interpretation_caveats.every(isStr) && typeof v.gemini_used === "boolean" && isStr(v.disclaimer);

export const isPracticeReference: Validator<PracticeReference> = (v): v is PracticeReference =>
  isObj(v) && isNum(v.id) && isStr(v.name) && (v.reference_type === "mudra" || v.reference_type === "sequence") && Array.isArray(v.mudra_ids);

export const isPracticeReferenceList: Validator<PracticeReference[]> = (v): v is PracticeReference[] =>
  isArrOf<PracticeReference>(isPracticeReference)(v);

export const isPracticeSession: Validator<PracticeSession> = (v): v is PracticeSession =>
  isObj(v) && isNum(v.session_id) && isNum(v.reference_id) && isStr(v.status);

export const isEvaluationResult: Validator<EvaluationResult> = (v): v is EvaluationResult =>
  isObj(v) &&
  isObj(v.reference) &&
  Array.isArray(v.predictions) &&
  Array.isArray(v.deviations) &&
  Array.isArray(v.warnings) &&
  isNum(v.frames_total) &&
  isNum(v.frames_with_landmarks) &&
  (v.dtw === null || (isObj(v.dtw) && isNum(v.dtw.distance)));

export const isEvaluateResponse: Validator<EvaluateResponse> = (v): v is EvaluateResponse =>
  isObj(v) &&
  isNum(v.session_id) &&
  (v.status === "evaluated" || v.status === "processing" || v.status === "failed") &&
  (v.result === null || v.result === undefined || isEvaluationResult(v.result));

export const isFeedback: Validator<Feedback> = (v): v is Feedback => isObj(v) && isStr(v.text);

export const isSessionResults: Validator<SessionResults> = (v): v is SessionResults =>
  isObj(v) &&
  isPracticeSession(v.session) &&
  (v.result === null || v.result === undefined || isEvaluationResult(v.result)) &&
  (v.feedback === null || v.feedback === undefined || isFeedback(v.feedback));

export const isProgressResponse: Validator<ProgressResponse> = (v): v is ProgressResponse =>
  isObj(v) && Array.isArray(v.sessions) && v.sessions.every((s) => isObj(s) && isNum(s.session_id) && isStr(s.reference_name) && isStr(s.created_at));
