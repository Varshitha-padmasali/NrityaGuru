import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/Card";
import { ProgressView } from "@/components/progress/ProgressView";

export const metadata: Metadata = { title: "Progress" };

export default function ProgressPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <PageHeader eyebrow="Progress" title="Your practice journey" description="Every session you've submitted, with the measurements the evaluation actually recorded." />
      <ProgressView />
    </div>
  );
}
