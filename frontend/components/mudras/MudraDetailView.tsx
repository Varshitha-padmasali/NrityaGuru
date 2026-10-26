"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { explainConcepts, getMudra } from "@/services/knowledge-service";
import type { ExplainResponse } from "@/types/knowledge";
import { ApiError } from "@/types/api";
import { Badge } from "@/components/ui/Card";
import { Button, ButtonLink } from "@/components/ui/Button";
import { ErrorState, LoadingState, Notice } from "@/components/ui/StatusStates";
import { IconArrowLeft, IconCamera, IconSparkle } from "@/components/ui/Icons";
import { TutorExplanation } from "@/components/learning/TutorExplanation";
import { capitalize } from "@/lib/utils";
import { MudraImage } from "./MudraImage";

const VERIFICATION: Record<string, { text: string; tone: "success" | "warning" | "neutral" }> = {
  verified: { text: "Verified entry", tone: "success" },
  needs_review: { text: "Needs review", tone: "warning" },
  unverified: { text: "Unverified entry", tone: "neutral" },
};

export function MudraDetailView() {
  const { id } = useParams<{ id: string }>();
  const { data: mudra, error, loading, reload } = useApiQuery((signal) => getMudra(id, signal), [id]);

  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<unknown>(null);
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);

  const askTutor = async () => {
    if (!mudra || explaining) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setExplaining(true);
    setExplainError(null);
    try {
      setExplanation(await explainConcepts(`Explain the ${mudra.name} mudra for a beginner.`, [mudra.id], controller.signal));
    } catch (err) {
      if (!(err instanceof ApiError && err.kind === "aborted")) setExplainError(err);
    } finally {
      if (!controller.signal.aborted) setExplaining(false);
    }
  };

  if (loading) return <LoadingState label="Loading mudra…" className="min-h-80" />;
  if (error) return <ErrorState error={error} title="Couldn't load this mudra" onRetry={reload} />;
  if (!mudra) return null;

  const verification = VERIFICATION[mudra.verification_status] ?? VERIFICATION.unverified;

  return (
    <article>
      <Link href="/mudras" className="mb-6 inline-flex items-center gap-1.5 rounded text-sm font-medium text-maroon hover:underline">
        <IconArrowLeft width={16} height={16} /> All mudras
      </Link>

      <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <div className="overflow-hidden rounded-3xl border border-line bg-paper shadow-[var(--shadow-card)]">
            <MudraImage src={mudra.image_url} name={mudra.name} className="aspect-square w-full" />
          </div>
          {mudra.source ? <p className="mt-3 text-sm text-ink-muted">Source: {mudra.source}</p> : null}
        </div>

        <div>
          <div className="mb-3 flex flex-wrap gap-2">
            {mudra.hasta_type ? <Badge tone="gold">{capitalize(mudra.hasta_type)} hasta</Badge> : null}
            <Badge tone={verification.tone}>{verification.text}</Badge>
          </div>
          <h1 className="font-display text-5xl font-semibold text-maroon-dark sm:text-6xl">{mudra.name}</h1>
          {mudra.alt_names.length > 0 ? <p className="mt-2 text-ink-muted">Also known as {mudra.alt_names.join(", ")}</p> : null}

          <dl className="mt-8 space-y-6">
            <DetailBlock term="Meaning" value={mudra.meaning} />
            <DetailBlock term="Usage and context" value={mudra.usage} />
            <DetailBlock term="How to form it" value={mudra.instructions} />
          </dl>

          <div className="mt-8 flex flex-wrap gap-3">
            {mudra.practice_reference_id ? (
              <ButtonLink href={`/practice/${mudra.practice_reference_id}`} size="lg" icon={<IconCamera width={18} height={18} />}>
                Start practice
              </ButtonLink>
            ) : null}
            {!explanation ? (
              <Button variant="secondary" size="lg" onClick={askTutor} loading={explaining} icon={<IconSparkle width={18} height={18} />}>
                Ask the AI tutor
              </Button>
            ) : null}
          </div>
          {!mudra.practice_reference_id ? (
            <Notice className="mt-6">Camera evaluation isn&apos;t available for this mudra yet — it needs a recorded reference and a trained model first.</Notice>
          ) : null}
        </div>
      </div>

      {explanation || explaining || explainError ? (
        <div className="mt-12">
          <TutorExplanation data={explanation} loading={explaining} error={explainError} onRetry={askTutor} />
        </div>
      ) : null}
    </article>
  );
}

function DetailBlock({ term, value }: { term: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-gold">{term}</dt>
      <dd className="mt-1.5 whitespace-pre-line text-lg leading-relaxed text-ink">{value ?? <span className="text-base italic text-ink-muted">Not recorded yet.</span>}</dd>
    </div>
  );
}
