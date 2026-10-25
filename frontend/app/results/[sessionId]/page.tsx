import { Suspense } from "react";
import { ResultsView } from "@/components/results/ResultsView";
import { LoadingState } from "@/components/ui/StatusStates";

export default function ResultsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <Suspense fallback={<LoadingState label="Loading your results…" className="min-h-80" />}>
        <ResultsView />
      </Suspense>
    </div>
  );
}
