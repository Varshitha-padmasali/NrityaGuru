"use client";

import Link from "next/link";
import { useApiQuery } from "@/hooks/useApiQuery";
import { listPracticeReferences } from "@/services/practice-service";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StatusStates";
import { Badge } from "@/components/ui/Card";
import { buttonClasses } from "@/components/ui/Button";
import { IconCamera } from "@/components/ui/Icons";
import { MudraImage } from "@/components/mudras/MudraImage";

/** Lists only the references the backend says can actually be evaluated. */
export function ReferenceList() {
  const { data, error, loading, reload } = useApiQuery((signal) => listPracticeReferences(signal), []);

  if (loading) return <LoadingState label="Loading practice references…" />;
  if (error) return <ErrorState error={error} title="Couldn't load practice references" onRetry={reload} />;
  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={<IconCamera width={32} height={32} />}
        title="No practice references yet"
        description="A mudra can be practised here once it has a recorded reference and the evaluation model supports it."
      />
    );
  }

  return (
    <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {data.map((ref) => (
        <li key={ref.id} className="flex flex-col overflow-hidden rounded-2xl border border-line bg-paper shadow-[var(--shadow-card)]">
          <MudraImage src={ref.image_url} name={ref.name} className="aspect-[4/3] w-full" />
          <div className="flex flex-1 flex-col p-5">
            <Badge tone={ref.reference_type === "sequence" ? "maroon" : "gold"} className="self-start">
              {ref.reference_type === "sequence" ? `Sequence · ${ref.mudra_ids.length} steps` : "Single mudra"}
            </Badge>
            <h2 className="mt-2 font-display text-2xl font-semibold text-maroon-dark">{ref.name}</h2>
            {ref.description ? <p className="mt-1 text-ink-muted">{ref.description}</p> : null}
            <Link href={`/practice/${ref.id}`} className={buttonClasses("primary", "sm", "mt-auto self-start")}>
              <IconCamera width={16} height={16} /> Practise this
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}
