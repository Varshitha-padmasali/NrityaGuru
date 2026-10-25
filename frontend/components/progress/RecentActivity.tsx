"use client";

import Link from "next/link";
import { useApiQuery } from "@/hooks/useApiQuery";
import { getProgress } from "@/services/progress-service";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StatusStates";
import { ButtonLink } from "@/components/ui/Button";
import { StatusBadge } from "./StatusBadge";
import { formatDateTime } from "@/lib/utils";
import { IconCamera } from "@/components/ui/Icons";

export function RecentActivity() {
  const { data, error, loading, reload } = useApiQuery((signal) => getProgress(signal), []);

  if (loading) return <LoadingState label="Loading recent practice…" />;
  if (error) return <ErrorState error={error} title="Couldn't load recent practice" onRetry={reload} />;

  const recent = [...(data?.sessions ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 3);
  if (recent.length === 0) {
    return (
      <EmptyState
        icon={<IconCamera width={32} height={32} />}
        title="No practice sessions yet"
        description="Your recorded practice sessions will appear here."
        action={<ButtonLink href="/practice">Start your first practice</ButtonLink>}
      />
    );
  }

  return (
    <ul className="grid gap-3 md:grid-cols-3">
      {recent.map((s) => (
        <li key={s.session_id}>
          <Link href={`/results/${s.session_id}`} className="block rounded-2xl border border-line bg-paper p-5 transition-colors hover:border-gold/60">
            <div className="flex items-start justify-between gap-3">
              <p className="font-semibold text-ink">{s.reference_name}</p>
              <StatusBadge status={s.status} />
            </div>
            <p className="mt-2 text-sm text-ink-muted">{formatDateTime(s.created_at)}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
