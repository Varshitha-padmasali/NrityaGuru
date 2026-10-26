"use client";

/**
 * Learn page logic:
 * 1. Learner types text → validate → POST /api/knowledge/retrieve
 * 2. Show the concepts and mudras exactly as returned
 * 3. If any mudras matched, ask POST /api/tutor/explain for a grounded explanation
 *    (a tutor failure never hides the knowledge-base results)
 */
import { useEffect, useRef, useState, type FormEvent } from "react";
import { explainConcepts, MAX_QUERY_LENGTH, retrieveKnowledge, validateLearningQuery } from "@/services/knowledge-service";
import type { ExplainResponse, RetrieveResponse } from "@/types/knowledge";
import { ApiError } from "@/types/api";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingState } from "@/components/ui/StatusStates";
import { IconSearch } from "@/components/ui/Icons";
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

  const controllerRef = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const runExplain = async (query: string, retrieved: RetrieveResponse, signal: AbortSignal) => {
    void retrieved; // The backend RAG endpoint retrieves and grounds its own references.
    setExplaining(true);
    setExplainError(null);
    try {
      setExplanation(await explainConcepts(query, signal));
    } catch (err) {
      if (!(err instanceof ApiError && err.kind === "aborted")) setExplainError(err);
    } finally {
      if (!signal.aborted) setExplaining(false);
    }
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (retrieving) return; // prevent duplicate submissions
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
  };

  const retryExplain = () => {
    if (!result) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    void runExplain(text, result, controller.signal);
  };

  const hasMatches = result?.concepts.some((c) => c.matches.length > 0) ?? false;

  return (
    <div>
      <form onSubmit={submit} noValidate className="rounded-3xl border border-line bg-paper p-5 shadow-[var(--shadow-card)] sm:p-7">
        <label htmlFor="learn-input" className="font-display text-2xl font-semibold text-maroon-dark">
          What would you like to express?
        </label>
        <p id="learn-help" className="mt-1 text-sm text-ink-muted">
          Enter a sentence, a line of lyrics, or a concept. We&apos;ll find mudras from the knowledge base that can represent it.
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
          <Button type="submit" size="lg" loading={retrieving} icon={<IconSearch width={18} height={18} />}>
            Find mudras
          </Button>
        </div>
      </form>

      <div ref={resultsRef} tabIndex={-1} className="mt-12 outline-none" aria-live="polite">
        {retrieving ? <LoadingState label="Searching the knowledge base…" /> : null}
        {retrieveError ? <ErrorState error={retrieveError} title="Couldn't search the knowledge base" onRetry={() => void submit()} /> : null}
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
