import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/Card";
import { ReferenceList } from "@/components/practice/ReferenceList";

export const metadata: Metadata = { title: "Practice" };

export default function PracticeIndexPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <PageHeader
        eyebrow="Practice"
        title="Choose what to practise"
        description="These are the mudras and sequences NrityaGuru can currently compare against a recorded reference."
      />
      <ReferenceList />
    </div>
  );
}
