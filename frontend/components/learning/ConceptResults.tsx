import type { ConceptResult } from "@/types/knowledge";
import { MudraCard } from "@/components/mudras/MudraCard";
import { Badge } from "@/components/ui/Card";
import { Notice } from "@/components/ui/StatusStates";

/**
 * Renders exactly what POST /api/knowledge/retrieve returned:
 * one section per concept, with every matched mudra (alternatives included)
 * and an explicit message for concepts the knowledge base doesn't cover.
 */
export function ConceptResults({ concepts }: { concepts: ConceptResult[] }) {
  if (concepts.length === 0) {
    return (
      <Notice tone="warning">
        No concepts in your text matched the knowledge base yet. Try simpler words (for example an object, an animal or an action), or browse the mudra library.
      </Notice>
    );
  }

  const supported = concepts.filter((c) => c.supported && c.matches.length > 0);
  const unsupported = concepts.filter((c) => !c.supported || c.matches.length === 0);

  return (
    <div className="space-y-12">
      {supported.map((concept, index) => (
        <section key={`${concept.concept}-${index}`} aria-labelledby={`concept-${index}`}>
          <div className="mb-4 flex flex-wrap items-baseline gap-3">
            <span className="font-display text-lg font-semibold text-gold">{String(index + 1).padStart(2, "0")}</span>
            <h3 id={`concept-${index}`} className="font-display text-3xl font-semibold capitalize text-maroon-dark">
              {concept.concept}
            </h3>
            {concept.matches.length > 1 ? <Badge tone="maroon">{concept.matches.length} possible interpretations</Badge> : null}
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {concept.matches.map((match, i) => (
              <MudraCard
                key={match.id}
                mudra={match}
                rationale={match.rationale}
                source={match.source}
                alternativeLabel={concept.matches.length > 1 ? `Option ${i + 1}` : undefined}
              />
            ))}
          </div>
        </section>
      ))}

      {unsupported.length > 0 ? (
        <section aria-labelledby="unsupported-heading" className="rounded-2xl border border-dashed border-line bg-paper/60 p-6">
          <h3 id="unsupported-heading" className="font-semibold text-ink">
            Not in the knowledge base yet
          </h3>
          <p className="mt-1 text-sm text-ink-muted">
            NrityaGuru does not have a verified mudra for these concepts, so it doesn&apos;t suggest one. Ask your teacher how they would express them.
          </p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {unsupported.map((c, i) => (
              <li key={`${c.concept}-${i}`}>
                <Badge tone="neutral" className="text-sm capitalize">
                  {c.concept}
                </Badge>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
