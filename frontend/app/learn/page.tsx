import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/Card";
import { LearnWorkspace } from "@/components/learning/LearnWorkspace";

export const metadata: Metadata = { title: "Learn" };

export default function LearnPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <PageHeader
        eyebrow="Learn"
        title="From words to hastas"
        description="Suggestions come from NrityaGuru's curated knowledge base. A sentence can be expressed in more than one valid way, so treat them as options to explore."
      />
      <LearnWorkspace />
    </div>
  );
}
