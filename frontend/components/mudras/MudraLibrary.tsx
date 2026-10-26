"use client";

import { useMemo, useState } from "react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { listMudras } from "@/services/knowledge-service";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StatusStates";
import { IconHand, IconSearch } from "@/components/ui/Icons";
import { Badge } from "@/components/ui/Card";
import Link from "next/link";
import { MudraImage } from "./MudraImage";

export function MudraLibrary() {
  const { data, error, loading, reload } = useApiQuery((signal) => listMudras(signal), []);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!data) return [];
    if (!q) return data;
    return data.filter((m) => [m.name, ...m.alternate_names, ...m.dataset_classes.map((entry) => entry.dataset_folder), m.meaning ?? "", ...m.usage]
      .some((value) => value.toLowerCase().includes(q)));
  }, [data, filter]);

  if (loading) return <LoadingState label="Loading mudras…" />;
  if (error) return <ErrorState error={error} title="Couldn't load the mudra library" onRetry={reload} />;
  if (!data || data.length === 0) {
    return <EmptyState icon={<IconHand width={32} height={32} />} title="The library is empty" description="No mudras have been added to the knowledge base yet." />;
  }

  return (
    <div>
      <div className="relative mb-8 max-w-md">
        <label htmlFor="mudra-filter" className="sr-only">
          Filter mudras
        </label>
        <IconSearch className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-muted" width={18} height={18} />
        <input
          id="mudra-filter"
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by mudra name or meaning"
          className="h-12 w-full rounded-full border border-line bg-paper pl-11 pr-4 text-ink placeholder:text-ink-muted/60 focus:border-gold focus:outline-none"
        />
      </div>
      {filtered.length === 0 ? (
        <p className="text-ink-muted">No mudras match &ldquo;{filter}&rdquo;.</p>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((m) => (
            <li key={m.id}>
              <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-paper shadow-[var(--shadow-card)]">
                <MudraImage src={m.reference_image_path} name={m.name} className="aspect-[4/3] w-full" />
                <div className="flex flex-1 flex-col p-5">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge tone="gold">{m.category}</Badge>
                    <Badge tone={m.verification_status === "verified" ? "gold" : "neutral"}>{m.verification_status.replace("_", " ")}</Badge>
                  </div>
                  <h2 className="font-display text-2xl font-semibold text-maroon-dark">
                    <Link href={`/mudras/${m.id}`} className="rounded hover:text-maroon">{m.name}</Link>
                  </h2>
                  {m.meaning ? <p className="mt-1 text-ink-muted">{m.meaning}</p> : <p className="mt-1 text-sm italic text-ink-muted">Meaning not verified or recorded.</p>}
                  <p className="mt-auto pt-4 text-sm text-ink-muted">
                    {m.dataset_image_count > 0 ? `${m.dataset_image_count.toLocaleString()} dataset images` : "No dataset images"}
                    {m.recognition_supported ? " · supported by the loaded recognition model" : " · not supported by a loaded recognition model"}
                  </p>
                </div>
              </article>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
