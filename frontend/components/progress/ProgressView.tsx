"use client";

/**
 * Practice history. Trends are drawn ONLY from dtw_normalized values the
 * backend stored, and only when a reference has at least two of them.
 */
import Link from "next/link";
import { useMemo, useState } from "react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { getProgress } from "@/services/progress-service";
import type { ProgressEntry } from "@/types/progress";
import { Card } from "@/components/ui/Card";
import { ButtonLink, buttonClasses } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StatusStates";
import { IconArrowRight, IconChart } from "@/components/ui/Icons";
import { formatDateTime, formatProbability } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import { TrendSparkline } from "./TrendSparkline";

export function ProgressView() {
  const { data, error, loading, reload } = useApiQuery((signal) => getProgress(signal), []);
  const [referenceFilter, setReferenceFilter] = useState<number | "all">("all");

  const sessions = useMemo(() => [...(data?.sessions ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)), [data]);

  const byReference = useMemo(() => {
    const groups = new Map<number, { name: string; entries: ProgressEntry[] }>();
    for (const s of sessions) {
      const g = groups.get(s.reference_id) ?? { name: s.reference_name, entries: [] };
      g.entries.push(s);
      groups.set(s.reference_id, g);
    }
    return [...groups.entries()].map(([id, g]) => ({ id, ...g }));
  }, [sessions]);

  if (loading) return <LoadingState label="Loading your practice history…" />;
  if (error) return <ErrorState error={error} title="Couldn't load your practice history" onRetry={reload} />;
  if (sessions.length === 0) {
    return (
      <EmptyState
        icon={<IconChart width={32} height={32} />}
        title="No practice sessions yet"
        description="Each time you record and submit a practice, it will show up here so you can see how you're progressing."
        action={<ButtonLink href="/practice">Start practising</ButtonLink>}
      />
    );
  }

  const trends = byReference
    .map((g) => ({
      ...g,
      points: g.entries
        .filter((e) => e.status === "evaluated" && e.dtw_normalized !== null)
        .sort((a, b) => a.created_at.localeCompare(b.created_at))
        .map((e) => ({ x: e.created_at, y: e.dtw_normalized as number })),
    }))
    .filter((g) => g.points.length >= 2);

  const visible = referenceFilter === "all" ? sessions : sessions.filter((s) => s.reference_id === referenceFilter);

  return (
    <div className="space-y-10">
      <section aria-labelledby="trends-heading">
        <h2 id="trends-heading" className="mb-1 font-display text-3xl font-semibold text-maroon-dark">
          Trends
        </h2>
        <p className="mb-4 text-sm text-ink-muted">Normalised DTW distance per attempt, for references with at least two evaluated sessions. Lower means closer to the reference.</p>
        {trends.length === 0 ? (
          <p className="rounded-xl border border-dashed border-line p-5 text-ink-muted">Practise the same reference at least twice to see a trend here.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {trends.map((t) => {
              const first = t.points[0].y;
              const last = t.points[t.points.length - 1].y;
              const change = last < first ? "closer to the reference" : last > first ? "further from the reference" : "about the same";
              return (
                <Card key={t.id} className="p-5">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="font-semibold text-ink">{t.name}</p>
                    <span className="text-xs text-ink-muted">{t.points.length} attempts</span>
                  </div>
                  <TrendSparkline points={t.points.map((p) => p.y)} label={`DTW trend for ${t.name}`} />
                  <p className="text-sm text-ink-muted">
                    Latest {last.toFixed(3)} vs first {first.toFixed(3)} — {change}.
                  </p>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      <section aria-labelledby="history-heading">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <h2 id="history-heading" className="font-display text-3xl font-semibold text-maroon-dark">
            All sessions
          </h2>
          {byReference.length > 1 ? (
            <div>
              <label htmlFor="ref-filter" className="mr-2 text-sm text-ink-muted">
                Show
              </label>
              <select
                id="ref-filter"
                value={referenceFilter}
                onChange={(e) => setReferenceFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
                className="h-10 rounded-full border border-line bg-paper px-4 text-sm text-ink focus:border-gold focus:outline-none"
              >
                <option value="all">All references</option>
                {byReference.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
        </div>
        <ul className="space-y-3">
          {visible.map((s) => (
            <li key={s.session_id}>
              <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-ink">{s.reference_name}</p>
                    <StatusBadge status={s.status} />
                  </div>
                  <p className="mt-1 text-sm text-ink-muted">{formatDateTime(s.created_at)}</p>
                  {s.feedback_summary ? <p className="mt-2 line-clamp-2 text-sm text-ink">{s.feedback_summary}</p> : null}
                </div>
                <dl className="flex gap-6 text-sm">
                  {s.top_label ? (
                    <div>
                      <dt className="text-ink-muted">Detected</dt>
                      <dd className="font-semibold text-ink">
                        {s.top_label}
                        {s.top_confidence !== null ? <span className="font-normal text-ink-muted"> · {formatProbability(s.top_confidence)}</span> : null}
                      </dd>
                    </div>
                  ) : null}
                  {s.dtw_normalized !== null ? (
                    <div>
                      <dt className="text-ink-muted">DTW (norm.)</dt>
                      <dd className="font-semibold text-ink">{s.dtw_normalized.toFixed(3)}</dd>
                    </div>
                  ) : null}
                </dl>
                <Link href={`/results/${s.session_id}`} className={buttonClasses("secondary", "sm")}>
                  View results <IconArrowRight width={16} height={16} />
                </Link>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
