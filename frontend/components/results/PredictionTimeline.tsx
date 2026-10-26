import type { Prediction } from "@/types/evaluation";
import { formatFrameRange, formatProbability } from "@/lib/utils";

const PALETTE = ["#6e1423", "#a8792c", "#2f6b4f", "#5b3a7a", "#8a5a00", "#1f4e79"];

/**
 * Horizontal bar showing which label the model predicted over time.
 * Widths come straight from the frame ranges returned by the backend.
 */
export function PredictionTimeline({ predictions, framesTotal, fps }: { predictions: Prediction[]; framesTotal: number; fps: number | null }) {
  if (predictions.length === 0 || framesTotal <= 0) {
    return <p className="text-sm text-ink-muted">No gesture predictions were returned for this recording.</p>;
  }

  const labels = [...new Set(predictions.map((p) => p.label))];
  const colorFor = (label: string) => PALETTE[labels.indexOf(label) % PALETTE.length];

  return (
    <div>
      <div className="relative h-10 w-full overflow-hidden rounded-lg bg-ivory-deep" role="img" aria-label="Timeline of predicted gestures">
        {predictions.map((p, i) => {
          const left = (p.frame_start / framesTotal) * 100;
          const width = (Math.max(1, p.frame_end - p.frame_start + 1) / framesTotal) * 100;
          return (
            <div
              key={i}
              className="absolute inset-y-0 border-r-2 border-paper"
              style={{ left: `${left}%`, width: `${width}%`, backgroundColor: colorFor(p.label) }}
              title={`${p.label} · ${formatProbability(p.confidence)}`}
            />
          );
        })}
      </div>
      <ul className="mt-3 space-y-1.5 text-sm">
        {predictions.map((p, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2">
            <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: colorFor(p.label) }} aria-hidden="true" />
            <span className="font-semibold text-ink">{p.label}</span>
            <span className="text-ink-muted">
              {formatFrameRange(p.frame_start, p.frame_end, fps)} · model confidence {formatProbability(p.confidence)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
