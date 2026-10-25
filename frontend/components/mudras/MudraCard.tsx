import Link from "next/link";
import type { MudraSummary } from "@/types/knowledge";
import { Badge } from "@/components/ui/Card";
import { ButtonLink, buttonClasses } from "@/components/ui/Button";
import { IconArrowRight, IconCamera } from "@/components/ui/Icons";
import { capitalize } from "@/lib/utils";
import { MudraImage } from "./MudraImage";

export interface MudraCardProps {
  mudra: MudraSummary;
  /** Why the knowledge base linked this mudra to the learner's concept. */
  rationale?: string | null;
  source?: string | null;
  /** Show "Start practice" only when a practice reference exists. */
  practiceReferenceId?: number | null;
  /** Label shown when this card is one of several alternatives. */
  alternativeLabel?: string;
}

export function MudraCard({ mudra, rationale, source, practiceReferenceId, alternativeLabel }: MudraCardProps) {
  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-paper shadow-[var(--shadow-card)]">
      <MudraImage src={mudra.image_url} name={mudra.name} className="aspect-[4/3] w-full" />
      <div className="flex flex-1 flex-col p-5">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {mudra.hasta_type ? <Badge tone="gold">{capitalize(mudra.hasta_type)} hasta</Badge> : null}
          {alternativeLabel ? <Badge tone="neutral">{alternativeLabel}</Badge> : null}
        </div>
        <h3 className="font-display text-2xl font-semibold text-maroon-dark">
          <Link href={`/mudras/${mudra.id}`} className="rounded hover:text-maroon">
            {mudra.name}
          </Link>
        </h3>
        {mudra.meaning ? <p className="mt-1 text-ink-muted">{mudra.meaning}</p> : <p className="mt-1 text-sm italic text-ink-muted">No meaning recorded yet.</p>}
        {rationale ? (
          <p className="mt-3 border-l-2 border-gold/60 pl-3 text-sm leading-relaxed text-ink">
            <span className="font-semibold">Why this match: </span>
            {rationale}
          </p>
        ) : null}
        {source ? <p className="mt-3 text-xs text-ink-muted">Source: {source}</p> : null}

        <div className="mt-auto flex flex-wrap gap-2 pt-5">
          <Link href={`/mudras/${mudra.id}`} className={buttonClasses("secondary", "sm")}>
            View details <IconArrowRight width={16} height={16} />
          </Link>
          {practiceReferenceId ? (
            <ButtonLink href={`/practice/${practiceReferenceId}`} size="sm" icon={<IconCamera width={16} height={16} />}>
              Start practice
            </ButtonLink>
          ) : null}
        </div>
      </div>
    </article>
  );
}
