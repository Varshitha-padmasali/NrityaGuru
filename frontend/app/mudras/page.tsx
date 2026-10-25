import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/Card";
import { MudraLibrary } from "@/components/mudras/MudraLibrary";

export const metadata: Metadata = { title: "Mudras" };

export default function MudrasPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="Library" title="Mudra library" description="Every hasta currently in the NrityaGuru knowledge base, with its meaning and reference image." />
      <MudraLibrary />
    </div>
  );
}
