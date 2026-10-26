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
import type { BackendRetrievalResponse, CatalogueMudra, MudraDetail, MudraSummary, RetrieveResponse, ExplainResponse } from "@/types/knowledge";
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
  isObj(v) && (isNum(v.id) || isStr(v.id)) && isStr(v.name) && isNullable(isStr)(v.meaning ?? null) && isNullable(isStr)(v.image_url ?? null);

export const isMudraList: Validator<MudraSummary[]> = (v): v is MudraSummary[] => isArrOf<MudraSummary>(isMudraSummary)(v);

export const isCatalogueMudra: Validator<CatalogueMudra> = (v): v is CatalogueMudra =>
  isObj(v) && isStr(v.id) && isStr(v.name) && Array.isArray(v.alternate_names) &&
  isStr(v.category) && isNullable(isStr)(v.meaning) && Array.isArray(v.usage) &&
  isNullable(isStr)(v.reference_image_path) && isNum(v.dataset_image_count) &&
  typeof v.dataset_images_available === "boolean" && Array.isArray(v.dataset_classes) &&
  typeof v.recognition_supported === "boolean" && isStr(v.verification_status);

export const isCatalogueMudraList: Validator<CatalogueMudra[]> =
  (v): v is CatalogueMudra[] => isArrOf<CatalogueMudra>(isCatalogueMudra)(v);

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

export const isBackendRetrievalResponse: Validator<BackendRetrievalResponse> = (v): v is BackendRetrievalResponse =>
  isObj(v) && isStr(v.original_text) && Array.isArray(v.concepts) && v.concepts.every((item) =>
    isObj(item) && isObj(item.concept) && isStr(item.concept.text) && isStr(item.status) &&
    Array.isArray(item.references) && item.references.every((ref) =>
      isObj(ref) && isStr(ref.record_type) && isStr(ref.record_id) && isStr(ref.name) &&
      isStr(ref.category) && isNullable(isStr)(ref.meaning) && isNullable(isStr)(ref.reference_media_path) &&
      isStr(ref.match_type) && Array.isArray(ref.evidence_notes))
  );

export const isExplainResponse: Validator<ExplainResponse> = (v): v is ExplainResponse =>
  isObj(v) && isStr(v.original_text) && isObj(v.tutor) &&
  (v.tutor.mode === "ai" || v.tutor.mode === "knowledge_only") &&
  isObj(v.tutor.explanation) && isStr(v.tutor.explanation.summary) &&
  isObj(v.retrieval) && isStr(v.disclaimer);

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
