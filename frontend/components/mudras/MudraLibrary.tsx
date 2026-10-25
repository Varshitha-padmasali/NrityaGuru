"use client";

import { useMemo, useState } from "react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { listMudras } from "@/services/knowledge-service";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/StatusStates";
import { IconHand, IconSearch } from "@/components/ui/Icons";
import { MudraCard } from "./MudraCard";

export function MudraLibrary() {
  const { data, error, loading, reload } = useApiQuery((signal) => listMudras(signal), []);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!data) return [];
    if (!q) return data;
    return data.filter((m) => m.name.toLowerCase().includes(q) || (m.meaning ?? "").toLowerCase().includes(q));
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
          placeholder="Filter by name or meaning"
          className="h-12 w-full rounded-full border border-line bg-paper pl-11 pr-4 text-ink placeholder:text-ink-muted/60 focus:border-gold focus:outline-none"
        />
      </div>
      {filtered.length === 0 ? (
        <p className="text-ink-muted">No mudras match &ldquo;{filter}&rdquo;.</p>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((m) => (
            <li key={m.id}>
              <MudraCard mudra={m} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
