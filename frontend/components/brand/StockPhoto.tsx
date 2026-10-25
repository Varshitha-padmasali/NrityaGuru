"use client";

/**
 * A decorative photo that never shows a broken image:
 *   0. AI image generated with Gemini for this slot, if one exists (labelled "AI-generated")
 *   1. Pexels / Unsplash CDN (normal, online)
 *   2. local copy in public/images/photos (after `npm run photos:download`, works offline)
 *   3. the original NrityaGuru dancer illustration
 */
import { useEffect, useRef, useState } from "react";
import { getPhoto, type PhotoKey } from "@/lib/photos";
import { cn } from "@/lib/utils";
import { DancerIllustration } from "./DancerIllustration";

type Stage = "generated" | "remote" | "local" | "illustration";

export interface StockPhotoProps {
  photo: PhotoKey;
  width: number;
  height: number;
  className?: string;
  imgClassName?: string;
  priority?: boolean;
  /** Where the small credit sits; "none" hides it (credit is then shown elsewhere). */
  credit?: "overlay" | "none";
}

export function StockPhoto({ photo, width, height, className, imgClassName, priority, credit = "overlay" }: StockPhotoProps) {
  const info = getPhoto(photo);
  const [stage, setStage] = useState<Stage>(info.generated ? "generated" : "remote");
  const [loaded, setLoaded] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  const next = () => {
    setLoaded(false);
    setStage((s) => (s === "generated" ? "remote" : s === "remote" ? "local" : "illustration"));
  };

  // The image can fail before React hydrates; check it once on mount.
  useEffect(() => {
    const img = imgRef.current;
    if (img?.complete) {
      if (img.naturalWidth > 0) setLoaded(true);
      else next();
    }
  }, []);

  const src = stage === "generated" && info.generated ? info.generated.src : stage === "remote" ? info.remoteUrl(width, height) : info.localUrl;

  return (
    <div className={cn("relative overflow-hidden bg-[#2a1012]", className)}>
      {stage !== "illustration" ? (
        // eslint-disable-next-line @next/next/no-img-element -- external CDN with a local fallback chain
        <img
          key={stage}
          ref={imgRef}
          src={src}
          alt={stage === "generated" ? `AI-generated image: ${info.alt}` : info.alt}
          width={width}
          height={height}
          loading={priority ? "eager" : "lazy"}
          fetchPriority={priority ? "high" : undefined}
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={next}
          className={cn("h-full w-full object-cover transition-[opacity,transform] duration-1000", loaded ? "scale-100 opacity-100" : "scale-[1.03] opacity-0", imgClassName)}
        />
      ) : (
        <div className="absolute inset-0 flex items-end justify-center">
          <DancerIllustration className="h-full w-full" />
        </div>
      )}
      {/* Shimmer while loading */}
      {stage !== "illustration" && !loaded ? <div className="absolute inset-0 animate-pulse bg-gradient-to-br from-gold-soft/25 to-maroon/25" aria-hidden="true" /> : null}
      {stage === "generated" && loaded && credit === "overlay" ? (
        <span className="absolute bottom-2 right-2 rounded-full bg-black/45 px-2 py-0.5 text-[10px] font-medium text-white/90 backdrop-blur-sm">
          AI-generated with Gemini
        </span>
      ) : null}
      {credit === "overlay" && (stage === "remote" || stage === "local") && loaded ? (
        <a
          href={`${info.photoPage}?utm_source=nrityaguru&utm_medium=referral`}
          target="_blank"
          rel="noopener noreferrer"
          className="absolute bottom-2 right-2 rounded-full bg-black/45 px-2 py-0.5 text-[10px] font-medium text-white/90 backdrop-blur-sm hover:bg-black/65"
        >
          Photo: {info.photographer} / {info.providerName}
        </a>
      ) : null}
    </div>
  );
}
