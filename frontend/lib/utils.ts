/** Join class names, skipping falsy values. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

/** "2026-10-24T14:30:00Z" → "24 Oct 2026, 8:00 pm" in the learner's locale/time zone. */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}

/** 0.8734 → "87%". Only for values the backend defines as probabilities. */
export function formatProbability(value: number): string {
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

/** Display an uncalibrated classifier score without presenting it as a probability. */
export function formatModelScore(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : "—";
}

/** Frame range → "0.7 s – 1.2 s" when fps is known, else "frames 20–36". */
export function formatFrameRange(start: number | null, end: number | null, fps: number | null): string | null {
  if (start === null || end === null) return null;
  if (fps && fps > 0) return `${(start / fps).toFixed(1)} s – ${(end / fps).toFixed(1)} s`;
  return `frames ${start}–${end}`;
}

export function capitalize(text: string): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}
