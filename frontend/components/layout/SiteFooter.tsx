import { config } from "@/lib/config";

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-line">
      <div className="temple-rule" aria-hidden="true" />
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-ink-muted sm:flex-row sm:justify-between sm:px-6">
        <p>
          <span className="font-display text-base font-semibold text-maroon">NrityaGuru</span> — AI-assisted Bharatanatyam learning and practice.
        </p>
        <p>A practice aid, not a replacement for your guru.</p>
      </div>
    </footer>
  );
}

/** Visible on every page while mock mode is on, so mock data is never mistaken for real results. */
export function MockModeBanner() {
  if (!config.useMockApi) return null;
  return (
    <div role="status" className="bg-warning px-4 py-2 text-center text-sm font-semibold text-white">
      Development mock mode — all data on screen is placeholder data, not real knowledge-base content or evaluation results.
    </div>
  );
}
