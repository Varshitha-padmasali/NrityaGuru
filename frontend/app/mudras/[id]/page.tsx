import { Suspense } from "react";
import { MudraDetailView } from "@/components/mudras/MudraDetailView";
import { LoadingState } from "@/components/ui/StatusStates";

/**
 * The page itself is a server component; the dynamic part (reading the id and
 * fetching) is a client component inside Suspense, as Next.js 16 cache
 * components require for routes with dynamic params.
 */
export default function MudraDetailPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <Suspense fallback={<LoadingState label="Loading mudra…" className="min-h-80" />}>
        <MudraDetailView />
      </Suspense>
    </div>
  );
}
