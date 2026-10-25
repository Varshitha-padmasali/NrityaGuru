import { Suspense } from "react";
import { PracticeFlow } from "@/components/practice/PracticeFlow";
import { LoadingState } from "@/components/ui/StatusStates";

export default function PracticeMovementPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <Suspense fallback={<LoadingState label="Loading practice…" className="min-h-80" />}>
        <PracticeFlow />
      </Suspense>
    </div>
  );
}
