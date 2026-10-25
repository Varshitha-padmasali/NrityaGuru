"use client";

/**
 * Reference image with a clearly labelled placeholder.
 * If the backend has no image, or the image fails to load, we show a
 * placeholder that SAYS it is a placeholder — never a stand-in that could be
 * mistaken for an authentic reference.
 */
import { useState } from "react";
import { resolveMediaUrl } from "@/lib/config";
import { cn } from "@/lib/utils";
import { IconHand } from "@/components/ui/Icons";

export function MudraImage({ src, name, className }: { src: string | null; name: string; className?: string }) {
  const url = resolveMediaUrl(src);
  const [failed, setFailed] = useState(false);

  if (!url || failed) {
    return (
      <div
        className={cn("flex flex-col items-center justify-center gap-2 bg-ivory-deep text-center text-ink-muted", className)}
        role="img"
        aria-label={`No reference image available for ${name}`}
      >
        <IconHand width={36} height={36} className="text-gold/70" />
        <span className="px-4 text-xs font-medium">Reference image not available</span>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- images come from the backend host, which is configured at runtime
    <img src={url} alt={`Reference image of the ${name} mudra`} loading="lazy" decoding="async" onError={() => setFailed(true)} className={cn("bg-ivory-deep object-contain", className)} />
  );
}
