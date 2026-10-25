"use client";

/**
 * The video area of the practice page. Shows one of:
 * - a placeholder before the camera starts,
 * - the live (mirrored) camera preview,
 * - the recorded clip for review.
 */
import { useEffect, useRef } from "react";
import { formatDuration } from "@/lib/media";
import { DancerIllustration } from "@/components/brand/DancerIllustration";
import { Spinner } from "@/components/ui/Spinner";

export interface CameraStageProps {
  stream: MediaStream | null;
  recordingUrl: string | null;
  isRecording: boolean;
  isRequesting: boolean;
  elapsedMs: number;
  maxSeconds: number;
}

export function CameraStage({ stream, recordingUrl, isRecording, isRequesting, elapsedMs, maxSeconds }: CameraStageProps) {
  const liveRef = useRef<HTMLVideoElement>(null);

  // Attach / detach the MediaStream. srcObject cannot be set through JSX.
  useEffect(() => {
    const video = liveRef.current;
    if (!video) return;
    video.srcObject = stream;
    if (stream) void video.play().catch(() => undefined);
    return () => {
      video.srcObject = null;
    };
  }, [stream, recordingUrl]);

  const showLive = Boolean(stream) && !recordingUrl;
  const progress = Math.min(1, elapsedMs / (maxSeconds * 1000));

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-3xl border border-line bg-maroon-dark">
      {recordingUrl ? (
        <video key={recordingUrl} src={recordingUrl} controls playsInline className="h-full w-full bg-black object-contain" aria-label="Your recorded practice clip" />
      ) : null}

      {/* Live preview is mirrored so it behaves like a mirror in a dance studio. */}
      <video
        ref={liveRef}
        muted
        playsInline
        autoPlay
        aria-label="Live camera preview"
        className={`h-full w-full -scale-x-100 object-cover ${showLive ? "block" : "hidden"}`}
      />

      {!showLive && !recordingUrl ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center text-ivory/85">
          {isRequesting ? (
            <>
              <Spinner size={28} />
              <p className="max-w-xs text-sm">Waiting for camera permission… look for the prompt near your browser&apos;s address bar.</p>
            </>
          ) : (
            <>
              <DancerIllustration className="h-40 w-40 opacity-60" title="" />
              <p className="max-w-xs text-sm">Your camera preview will appear here.</p>
            </>
          )}
        </div>
      ) : null}

      {/* Framing guide while live */}
      {showLive && !isRecording ? (
        <div className="pointer-events-none absolute inset-[12%] rounded-[2rem] border-2 border-dashed border-gold-bright/70" aria-hidden="true" />
      ) : null}

      {isRecording ? (
        <>
          <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full bg-black/60 px-3 py-1.5 text-sm font-semibold text-white" role="status" aria-live="polite">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" aria-hidden="true" />
            REC {formatDuration(elapsedMs)} / {formatDuration(maxSeconds * 1000)}
          </div>
          <div className="absolute inset-x-0 bottom-0 h-1.5 bg-white/20" aria-hidden="true">
            <div className="h-full bg-gold-bright transition-[width] duration-200" style={{ width: `${progress * 100}%` }} />
          </div>
        </>
      ) : null}
    </div>
  );
}
