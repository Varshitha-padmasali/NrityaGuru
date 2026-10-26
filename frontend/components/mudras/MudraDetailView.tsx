"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { explainConcepts, getMudra } from "@/services/knowledge-service";
import type { ExplainResponse } from "@/types/knowledge";
import { ApiError } from "@/types/api";
import { Badge } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingState, Notice } from "@/components/ui/StatusStates";
import { IconArrowLeft, IconSparkle } from "@/components/ui/Icons";
import { TutorExplanation } from "@/components/learning/TutorExplanation";
import { MudraImage } from "./MudraImage";

const VERIFICATION: Record<string, { text: string; tone: "success" | "warning" | "neutral" }> = {
  verified: { text: "Verified entry", tone: "success" },
  source_cited: { text: "Source cited; teacher review pending", tone: "warning" },
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
      setExplanation(await explainConcepts(`Explain the ${mudra.name} mudra for a beginner.`, controller.signal));
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
            <MudraImage src={mudra.reference_image_path} name={mudra.name} className="aspect-square w-full" />
          </div>
          {mudra.source ? <p className="mt-3 text-sm text-ink-muted">Source: {mudra.source.source_name}</p> : null}
        </div>

        <div>
          <div className="mb-3 flex flex-wrap gap-2">
            <Badge tone="gold">{mudra.category}</Badge>
            <Badge tone={verification.tone}>{verification.text}</Badge>
          </div>
          <h1 className="font-display text-5xl font-semibold text-maroon-dark sm:text-6xl">{mudra.name}</h1>
          {mudra.alternate_names.length > 0 ? <p className="mt-2 text-ink-muted">Also known as {mudra.alternate_names.join(", ")}</p> : null}

          <dl className="mt-8 space-y-6">
            <DetailBlock term="Meaning" value={mudra.meaning} />
            <DetailBlock term="Usage and context" value={mudra.usage.length ? mudra.usage.join(", ") : null} />
            <DetailBlock term="Description" value={mudra.description} />
            <DetailBlock term="How to form it" value={mudra.practice_instructions} />
          </dl>

          <div className="mt-8 flex flex-wrap gap-3">
            {!explanation ? (
              <Button variant="secondary" size="lg" onClick={askTutor} loading={explaining} icon={<IconSparkle width={18} height={18} />}>
                Ask the AI tutor
              </Button>
            ) : null}
          </div>
          <Notice className="mt-6">
            {mudra.recognition_supported
              ? "This mudra is supported by the currently loaded recognition model."
              : mudra.dataset_image_count > 0
                ? `The dataset contains ${mudra.dataset_image_count.toLocaleString()} images, but no compatible recognition model is loaded for this class yet.`
                : "This mudra is in the knowledge base, but has no dataset images or loaded recognition model."}
          </Notice>
          {mudra.dataset_classes.length > 0 ? (
            <div className="mt-5 rounded-xl border border-line bg-paper/70 p-4">
              <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-gold">Dataset labels</h2>
              <ul className="mt-2 space-y-1 text-sm text-ink-muted">
                {mudra.dataset_classes.map((entry) => (
                  <li key={entry.dataset_folder}>
                    <span className="font-medium text-ink">{entry.dataset_folder}</span>
                    {entry.variant_id ? ` · ${entry.variant_id}` : ""} · {entry.image_count.toLocaleString()} images
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-ink-muted">Folder labels are mapped to this catalogue entry; mappings are pending dance-teacher review.</p>
            </div>
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
