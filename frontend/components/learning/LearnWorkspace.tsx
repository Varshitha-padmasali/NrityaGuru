"use client";

/**
 * Learn page logic:
 * 1. Learner types text → validate → POST /api/knowledge/retrieve
 * 2. Show the concepts and mudras exactly as returned
 * 3. If any mudras matched, ask POST /api/tutor/explain for a grounded explanation
 *    (a tutor failure never hides the knowledge-base results)
 */
import { useEffect, useRef, useState, type FormEvent } from "react";
import { explainConcepts, generateMudraSequence, MAX_QUERY_LENGTH, retrieveKnowledge, validateLearningQuery } from "@/services/knowledge-service";
import type { ExplainResponse, RetrieveResponse, SequenceResponse } from "@/types/knowledge";
import { ApiError } from "@/types/api";
import { resolveMediaUrl } from "@/lib/config";
import { Button } from "@/components/ui/Button";
import { Badge, Card } from "@/components/ui/Card";
import { ErrorState, LoadingState, Notice } from "@/components/ui/StatusStates";
import { IconSearch } from "@/components/ui/Icons";
import { MudraImage } from "@/components/mudras/MudraImage";
import { ConceptResults } from "./ConceptResults";
import { TutorExplanation } from "./TutorExplanation";

const EXAMPLES = ["Krishna is singing and dancing in the garden.", "The lotus blooms by the river.", "A peacock dances in the rain."];

export function LearnWorkspace() {
  const [text, setText] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const [result, setResult] = useState<RetrieveResponse | null>(null);
  const [retrieving, setRetrieving] = useState(false);
  const [retrieveError, setRetrieveError] = useState<unknown>(null);

  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<unknown>(null);
  const [sequence, setSequence] = useState<SequenceResponse | null>(null);
  const [sequenceLoading, setSequenceLoading] = useState(false);
  const [sequenceError, setSequenceError] = useState<unknown>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const runExplain = async (query: string, retrieved: RetrieveResponse, signal: AbortSignal) => {
    const mudraIds = [...new Set(retrieved.concepts.flatMap((c) => c.matches.map((m) => m.id)))];
    if (mudraIds.length === 0) return;
    setExplaining(true);
    setExplainError(null);
    try {
      setExplanation(await explainConcepts(query, mudraIds, signal));
    } catch (err) {
      if (!(err instanceof ApiError && err.kind === "aborted")) setExplainError(err);
    } finally {
      if (!signal.aborted) setExplaining(false);
    }
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (retrieving || sequenceLoading) return; // prevent duplicate submissions
    const problem = validateLearningQuery(text);
    setValidationError(problem);
    if (problem) return;

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setRetrieving(true);
    setRetrieveError(null);
    setResult(null);
    setExplanation(null);
    setExplainError(null);
    setSequence(null);
    setSequenceError(null);
    setSequenceLoading(true);
    const sequenceTask = generateMudraSequence(text, controller.signal)
      .then(setSequence)
      .catch((err: unknown) => {
        if (!(err instanceof ApiError && err.kind === "aborted")) setSequenceError(err);
      })
      .finally(() => {
        if (!controller.signal.aborted) setSequenceLoading(false);
      });
    try {
      const retrieved = await retrieveKnowledge(text, controller.signal);
      setResult(retrieved);
      setRetrieving(false);
      requestAnimationFrame(() => resultsRef.current?.focus());
      await runExplain(text, retrieved, controller.signal);
    } catch (err) {
      if (!(err instanceof ApiError && err.kind === "aborted")) setRetrieveError(err);
      setRetrieving(false);
    }
    await sequenceTask;
  };

  const retryExplain = () => {
    if (!result) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    void runExplain(text, result, controller.signal);
  };

  const hasMatches = result?.concepts.some((c) => c.matches.length > 0) ?? false;
  const busy = retrieving || sequenceLoading;

  return (
    <div>
      <form onSubmit={submit} noValidate className="rounded-3xl border border-line bg-paper p-5 shadow-[var(--shadow-card)] sm:p-7">
        <label htmlFor="learn-input" className="font-display text-2xl font-semibold text-maroon-dark">
          What would you like to express?
        </label>
        <p id="learn-help" className="mt-1 text-sm text-ink-muted">
          Enter a sentence, a line of lyrics, or a concept. We&apos;ll translate it when possible and arrange related mudras in performance order.
        </p>
        <textarea
          id="learn-input"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (validationError) setValidationError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void submit();
          }}
          rows={3}
          maxLength={MAX_QUERY_LENGTH}
          aria-describedby={`learn-help${validationError ? " learn-error" : ""}`}
          aria-invalid={validationError ? true : undefined}
          placeholder="e.g. Krishna is singing and dancing in the garden."
          className="mt-4 w-full resize-y rounded-xl border border-line bg-ivory/60 px-4 py-3 text-lg text-ink placeholder:text-ink-muted/60 focus:border-gold focus:outline-none"
        />
        <div className="mt-2 flex items-center justify-between text-xs text-ink-muted">
          {validationError ? (
            <p id="learn-error" role="alert" className="font-medium text-danger">
              {validationError}
            </p>
          ) : (
            <span>Ctrl/⌘ + Enter to search</span>
          )}
          <span>
            {text.length}/{MAX_QUERY_LENGTH}
          </span>
        </div>

        <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Try:</span>
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => {
                  setText(example);
                  setValidationError(null);
                }}
                className="rounded-full border border-line bg-ivory px-3 py-1 text-sm text-ink-muted transition-colors hover:border-gold hover:text-maroon"
              >
                {example}
              </button>
            ))}
          </div>
          <Button type="submit" size="lg" loading={busy} icon={<IconSearch width={18} height={18} />}>
            Build mudra sequence
          </Button>
        </div>
      </form>

      <div ref={resultsRef} tabIndex={-1} className="mt-12 outline-none" aria-live="polite">
        {busy ? <LoadingState label={sequenceLoading ? "Translating and arranging the mudra sequence…" : "Searching the knowledge base…"} /> : null}
        {sequenceError ? <ErrorState error={sequenceError} title="Couldn't build the mudra sequence" onRetry={() => void submit()} /> : null}
        {retrieveError ? <ErrorState error={retrieveError} title="Couldn't search the knowledge base" onRetry={() => void submit()} /> : null}
        {sequence ? <SequenceResults data={sequence} /> : null}
        {result ? (
          <div className="space-y-12">
            <div>
              <p className="text-sm text-ink-muted">Results for</p>
              <p className="font-display text-2xl italic text-maroon">&ldquo;{result.query}&rdquo;</p>
              <div className="temple-rule mt-4" aria-hidden="true" />
            </div>
            {hasMatches ? <TutorExplanation data={explanation} loading={explaining} error={explainError} onRetry={retryExplain} /> : null}
            <ConceptResults concepts={result.concepts} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SequenceResults({ data }: { data: SequenceResponse }) {
  return (
    <section className="mb-12 space-y-6" aria-labelledby="sequence-heading">
      <div>
        <p className="text-sm text-ink-muted">Mudra sequence for</p>
        <h2 id="sequence-heading" className="font-display text-2xl italic text-maroon">&ldquo;{data.original_input}&rdquo;</h2>
        <p className="mt-2 text-sm text-ink-muted">Detected language: {data.detected_language.name}</p>
        <div className="temple-rule mt-4" aria-hidden="true" />
      </div>

      {data.sentence_translations.length > 0 ? (
        <div className="space-y-3" aria-label="Sentence translations">
          {data.sentence_translations.map((translation) => (
            <Card key={translation.position} className="p-4">
              <p className="text-sm text-ink">{translation.original_sentence}</p>
              {translation.english_translation ? (
                <p className="mt-1 font-medium text-maroon-dark">{translation.english_translation}</p>
              ) : (
                <p className="mt-1 text-sm text-ink-muted">Translation unavailable{translation.note ? `: ${translation.note}` : " in this request."}</p>
              )}
            </Card>
          ))}
        </div>
      ) : null}

      {data.ordered_sequence.length ? (
        <ol className="space-y-4" aria-label="Ordered mudra steps">
          {data.ordered_sequence.map((step) => {
            const imageUrl = resolveMediaUrl(step.image_url);
            const tone = step.selection_type === "teacher_verified" ? "success" : step.selection_type === "source_supported" ? "gold" : "warning";
            const label = step.selection_type === "teacher_verified" ? "Teacher verified" : step.selection_type === "source_supported" ? "Source supported" : "AI suggestion";
            return (
              <li key={`${step.position}-${step.mudra_id}`}>
                <Card className="overflow-hidden p-4 sm:p-5">
                  <div className="flex flex-col gap-4 sm:flex-row">
                    <div className="flex h-36 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-ivory-deep sm:w-40">
                      <MudraImage src={step.image_url} name={step.mudra_name} className="h-full w-full" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-display text-lg font-semibold text-gold">{String(step.position).padStart(2, "0")}</span>
                        <h3 className="font-display text-2xl font-semibold text-maroon-dark">{step.mudra_name}</h3>
                        <Badge tone={tone}>{label}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-ink-muted">For &ldquo;{step.phrase}&rdquo;{step.concepts.length ? ` · ${step.concepts.join(", ")}` : ""}</p>
                      <p className="mt-2 text-ink">{step.selection_reason}</p>
                      {step.hand_position_description ? <p className="mt-2 text-sm text-ink-muted">Hand position: {step.hand_position_description}</p> : null}
                      {step.source_citations.length ? (
                        <ul className="mt-3 space-y-1 text-sm">
                          {step.source_citations.map((citation) => (
                            <li key={citation.source_id}>
                              {citation.url ? <a href={citation.url} target="_blank" rel="noreferrer" className="text-maroon underline">{citation.title}</a> : <span>{citation.title}</span>}
                              <span className="text-ink-muted"> — {citation.claim_scope}</span>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {step.uncertainty_notes.length ? <p className="mt-2 text-sm text-warning">{step.uncertainty_notes.join(" ")}</p> : null}
                    </div>
                  </div>
                  {imageUrl ? null : <p className="mt-2 text-xs text-ink-muted">No visual reference is available for this mudra.</p>}
                </Card>
              </li>
            );
          })}
        </ol>
      ) : (
        <Notice tone="warning">No mudras could be matched to this sentence from the available knowledge base or AI suggestions.</Notice>
      )}

      {data.unmapped_concepts.length ? (
        <Notice tone="warning">
          <strong>Some concepts have no mapped mudra:</strong>{" "}
          {data.unmapped_concepts.map((item) => item.concept).filter((value, index, values) => values.indexOf(value) === index).join(", ")}.
        </Notice>
      ) : null}
      {data.interpretation_caveats.map((caveat, index) => <Notice key={`${index}-${caveat}`} tone="info">{caveat}</Notice>)}
      <p className="text-xs leading-relaxed text-ink-muted">{data.disclaimer}</p>
    </section>
  );
}
