import { ButtonLink } from "@/components/ui/Button";
import { DancerIllustration } from "@/components/brand/DancerIllustration";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-20 text-center">
      <DancerIllustration className="h-56 w-56" title="" />
      <h1 className="mt-6 font-display text-5xl font-semibold text-maroon-dark">Page not found</h1>
      <p className="mt-3 text-ink-muted">This step isn&apos;t part of the choreography. Let&apos;s go back to the start.</p>
      <ButtonLink href="/" className="mt-8">
        Back to home
      </ButtonLink>
    </div>
  );
}
