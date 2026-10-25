import type { ExplainResponse } from "@/types/knowledge";
import { ErrorState, LoadingState } from "@/components/ui/StatusStates";
import { IconSparkle } from "@/components/ui/Icons";

/** Displays the backend's grounded Gemini explanation as plain paragraphs. */
export function TutorExplanation({ data, loading, error, onRetry }: { data: ExplainResponse | null; loading: boolean; error: unknown; onRetry: () => void }) {
  return (
    <section aria-labelledby="tutor-heading" className="rounded-2xl border border-gold/40 bg-gradient-to-br from-gold-soft/50 to-paper p-6 sm:p-8">
      <div className="mb-4 flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-maroon text-gold-soft">
          <IconSparkle />
        </span>
        <div>
          <h2 id="tutor-heading" className="font-display text-2xl font-semibold text-maroon-dark">
            Your AI tutor explains
          </h2>
          <p className="text-xs text-ink-muted">Generated from the knowledge-base entries above. Check with your teacher when in doubt.</p>
        </div>
      </div>

      {loading ? <LoadingState label="The tutor is preparing an explanation…" className="min-h-24 justify-start" /> : null}
      {!loading && error ? <ErrorState error={error} title="The AI tutor is unavailable right now" onRetry={onRetry} /> : null}
      {!loading && !error && data ? (
        <div className="space-y-3 text-[17px] leading-relaxed text-ink">
          {data.explanation
            .split(/\n{2,}/)
            .map((p) => p.trim())
            .filter(Boolean)
            .map((paragraph, i) => (
              <p key={i} className="whitespace-pre-line">
                {paragraph}
              </p>
            ))}
        </div>
      ) : null}
    </section>
  );
}
