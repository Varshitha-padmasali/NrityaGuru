"use client";

/**
 * Shows GET /api/practice/sessions/{id}/results exactly as returned.
 * - While the session is still processing it re-checks every few seconds.
 * - Every number shown comes from the backend; the frontend calculates no scores.
 * - Feedback is requested separately, so a Gemini outage never hides the
 *   computer-vision results.
 */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { getSessionResults, requestFeedback } from "@/services/evaluation-service";
import type { Deviation, EvaluationResult, Feedback } from "@/types/evaluation";
import { ApiError } from "@/types/api";
import { Badge, Card } from "@/components/ui/Card";
import { Button, ButtonLink } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState, Notice } from "@/components/ui/StatusStates";
import { IconAlert, IconArrowLeft, IconCamera, IconChart, IconInfo, IconRefresh, IconSparkle } from "@/components/ui/Icons";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/progress/StatusBadge";
import { formatDateTime, formatFrameRange, formatProbability } from "@/lib/utils";
import { PredictionTimeline } from "./PredictionTimeline";

const POLL_MS = 3000;
const MAX_POLLS = 40;

const DEVIATION_TITLES: Record<Deviation["kind"], string> = {
  wrong_label: "Different gesture detected",
  feature_deviation: "Hand shape differed from the reference",
  high_alignment_cost: "This part differed most from the reference",
  insufficient_landmarks: "Hands not clearly visible",
};

export function ResultsView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { data, error, loading, reload } = useApiQuery((signal) => getSessionResults(sessionId, signal), [sessionId]);

  // Poll while processing.
  const [polls, setPolls] = useState(0);
  const stillProcessing = Boolean(data && !data.result && (data.session.status === "processing" || data.session.status === "uploaded"));
  const pollingGaveUp = polls >= MAX_POLLS;
  useEffect(() => {
    if (!stillProcessing || pollingGaveUp || loading) return;
    const t = setTimeout(() => {
      setPolls((n) => n + 1);
      reload();
    }, POLL_MS);
    return () => clearTimeout(t);
  }, [stillProcessing, pollingGaveUp, loading, reload]);

  if (loading && !data) return <LoadingState label="Loading your results…" className="min-h-80" />;
  if (error && !data) return <ErrorState error={error} title="Couldn't load these results" onRetry={reload} />;
  if (!data) return null;

  const { session, result } = data;

  return (
    <div>
      <Link href="/progress" className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-maroon hover:underline">
        <IconArrowLeft width={16} height={16} /> Practice history
      </Link>

      <header className="mb-8 mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-gold">Session #{session.session_id}</p>
          <h1 className="font-display text-4xl font-semibold text-maroon-dark sm:text-5xl">{result?.reference.name ?? "Practice results"}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-ink-muted">
            <StatusBadge status={session.status} />
            <span>{formatDateTime(session.created_at)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <ButtonLink href={`/practice/${session.reference_id}`} icon={<IconCamera width={18} height={18} />}>
            Practise again
          </ButtonLink>
          <ButtonLink href="/progress" variant="secondary" icon={<IconChart width={18} height={18} />}>
            View progress
          </ButtonLink>
        </div>
      </header>

      {stillProcessing ? (
        <Card className="flex items-center gap-4 p-6">
          <Spinner size={28} />
          <div>
            <p className="font-semibold text-maroon">Your recording is still being analysed.</p>
            <p className="text-sm text-ink-muted">
              {!pollingGaveUp ? "This page will update automatically." : "This is taking longer than usual."}
            </p>
          </div>
          {pollingGaveUp ? (
            <Button variant="secondary" size="sm" className="ml-auto" onClick={() => {
                setPolls(0);
                reload();
              }} icon={<IconRefresh width={16} height={16} />}>
              Check again
            </Button>
          ) : null}
        </Card>
      ) : null}

      {session.status === "failed" ? (
        <EmptyState
          title="This evaluation could not be completed"
          description="This usually happens when the hands weren't visible in enough frames. Check the recording tips and try again."
          action={<ButtonLink href={`/practice/${session.reference_id}`}>Record again</ButtonLink>}
        />
      ) : null}

      {session.status === "created" ? (
        <EmptyState title="No recording yet" description="This session was started but no video was submitted." action={<ButtonLink href={`/practice/${session.reference_id}`}>Record now</ButtonLink>} />
      ) : null}

      {result ? <EvaluationDetails sessionId={session.session_id} result={result} initialFeedback={data.feedback} /> : null}
    </div>
  );
}

function EvaluationDetails({ sessionId, result, initialFeedback }: { sessionId: number; result: EvaluationResult; initialFeedback: Feedback | null }) {
  const coverage = result.frames_total > 0 ? result.frames_with_landmarks / result.frames_total : 0;
  const topPrediction = [...result.predictions].sort((a, b) => b.frame_end - b.frame_start - (a.frame_end - a.frame_start))[0] ?? null;

  return (
    <div className="space-y-8">
      {result.warnings.length > 0 ? (
        <Notice tone="warning">
          <ul className="space-y-1">
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Notice>
      ) : null}

      <FeedbackPanel sessionId={sessionId} initialFeedback={initialFeedback} />

      {/* Summary tiles — each value is copied from the backend response */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gold">Reference</p>
          <p className="mt-2 font-display text-2xl font-semibold text-maroon-dark">{result.reference.name}</p>
          <p className="mt-1 text-sm text-ink-muted">What you were practising.</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gold">Mostly detected</p>
          <p className="mt-2 font-display text-2xl font-semibold text-maroon-dark">{topPrediction?.label ?? "—"}</p>
          <p className="mt-1 text-sm text-ink-muted">
            {topPrediction ? `Model confidence ${formatProbability(topPrediction.confidence)} for the longest stretch.` : "No gesture could be classified."}
          </p>
        </Card>
        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gold">Hands visible</p>
          <p className="mt-2 font-display text-2xl font-semibold text-maroon-dark">
            {result.frames_with_landmarks} / {result.frames_total} frames
          </p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ivory-deep" aria-hidden="true">
            <div className="h-full rounded-full bg-gold" style={{ width: `${Math.round(coverage * 100)}%` }} />
          </div>
          <p className="mt-1 text-sm text-ink-muted">Frames where hand landmarks were detected.</p>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="font-display text-2xl font-semibold text-maroon-dark">What the model saw over time</h2>
        <p className="mb-4 mt-1 text-sm text-ink-muted">The trained classifier labels each part of your recording. Confidence is the model&apos;s probability, not a mark for your dancing.</p>
        <PredictionTimeline predictions={result.predictions} framesTotal={result.frames_total} fps={result.fps} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="font-display text-2xl font-semibold text-maroon-dark">Comparison with the reference</h2>
          {result.dtw ? (
            <>
              <dl className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm text-ink-muted">DTW distance</dt>
                  <dd className="font-display text-3xl font-semibold text-maroon">{result.dtw.distance.toFixed(2)}</dd>
                </div>
                {result.dtw.normalized !== null ? (
                  <div>
                    <dt className="text-sm text-ink-muted">Normalised distance</dt>
                    <dd className="font-display text-3xl font-semibold text-maroon">{result.dtw.normalized.toFixed(3)}</dd>
                  </div>
                ) : null}
              </dl>
              <div className="mt-4 flex gap-2 rounded-xl bg-ivory-deep/70 p-4 text-sm leading-relaxed text-ink">
                <IconInfo className="mt-0.5 shrink-0 text-gold" width={18} height={18} />
                <p>
                  Dynamic Time Warping lines your movement up with the reference even if you were faster or slower, then measures how far apart they are.{" "}
                  <strong>Lower means closer to the reference.</strong> It has no fixed maximum, so compare it with your own earlier attempts at the same reference
                  rather than reading it as a percentage.
                </p>
              </div>
            </>
          ) : (
            <p className="mt-3 text-ink-muted">No sequence comparison was run for this recording.</p>
          )}
        </Card>

        <Card className="p-6">
          <h2 className="font-display text-2xl font-semibold text-maroon-dark">Where it differed</h2>
          {result.deviations.length === 0 ? (
            <p className="mt-3 text-ink-muted">The evaluation did not flag any specific differences.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {result.deviations.map((d, i) => (
                <li key={i} className="rounded-xl border border-line p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <IconAlert width={16} height={16} className="text-warning" />
                    <span className="font-semibold text-ink">{DEVIATION_TITLES[d.kind] ?? d.kind}</span>
                    {formatFrameRange(d.frame_start, d.frame_end, result.fps) ? <Badge>{formatFrameRange(d.frame_start, d.frame_end, result.fps)}</Badge> : null}
                  </div>
                  <p className="mt-1.5 text-sm text-ink">{d.message}</p>
                  {d.expected_label || d.predicted_label ? (
                    <p className="mt-1 text-xs text-ink-muted">
                      {d.expected_label ? `Expected: ${d.expected_label}` : ""}
                      {d.expected_label && d.predicted_label ? " · " : ""}
                      {d.predicted_label ? `Detected: ${d.predicted_label}` : ""}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <p className="text-xs text-ink-muted">
        Model {result.model_version} · features {result.feature_schema} · evaluated {formatDateTime(result.created_at)}. These results compare your recording with one reference
        under one feature representation; they don&apos;t judge expression, rhythm or overall technique.
      </p>
    </div>
  );
}

function FeedbackPanel({ sessionId, initialFeedback }: { sessionId: number; initialFeedback: Feedback | null }) {
  const [feedback, setFeedback] = useState<Feedback | null>(initialFeedback);
  const [attempt, setAttempt] = useState(0);
  const [failure, setFailure] = useState<{ attempt: number; error: unknown } | null>(null);

  // Request feedback whenever we don't have it yet. Each attempt is cancelled on
  // cleanup, so React's double-mount in development (and Next.js hiding the
  // route) simply starts a fresh request instead of leaving the panel stuck.
  useEffect(() => {
    if (feedback) return;
    const controller = new AbortController();
    requestFeedback(sessionId, controller.signal)
      .then((f) => {
        if (!controller.signal.aborted) setFeedback(f);
      })
      .catch((err) => {
        if (controller.signal.aborted || (err instanceof ApiError && err.kind === "aborted")) return;
        setFailure({ attempt, error: err });
      });
    return () => controller.abort();
  }, [sessionId, attempt, feedback]);

  const error = failure?.attempt === attempt ? failure.error : null;
  const loading = !feedback && !error;
  const retry = () => setAttempt((n) => n + 1);

  return (
    <section aria-labelledby="feedback-heading" className="rounded-2xl border border-gold/40 bg-gradient-to-br from-gold-soft/50 to-paper p-6 sm:p-8">
      <div className="mb-4 flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-maroon text-gold-soft">
          <IconSparkle />
        </span>
        <div>
          <h2 id="feedback-heading" className="font-display text-2xl font-semibold text-maroon-dark">
            Your feedback
          </h2>
          <p className="text-xs text-ink-muted">Written by the AI tutor from the measurements below — nothing else.</p>
        </div>
      </div>
      {loading ? <LoadingState label="Writing your feedback…" className="min-h-20 justify-start" /> : null}
      {!loading && error ? (
        <ErrorState error={error} title="Feedback isn't available right now" onRetry={retry} className="bg-paper" />
      ) : null}
      {!loading && !error && feedback ? (
        <div className="space-y-3 text-[17px] leading-relaxed text-ink">
          {feedback.text
            .split(/\n{2,}/)
            .filter((p) => p.trim())
            .map((p, i) => (
              <p key={i} className="whitespace-pre-line">
                {p.trim()}
              </p>
            ))}
        </div>
      ) : null}
      {!loading && error ? <p className="mt-3 text-sm text-ink-muted">Your measured results below are still valid.</p> : null}
    </section>
  );
}
