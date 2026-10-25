/** Minimal SVG line chart for a short series of backend-provided values. */
export function TrendSparkline({ points, label }: { points: number[]; label: string }) {
  const width = 320;
  const height = 72;
  const pad = 8;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const x = (i: number) => pad + (i * (width - pad * 2)) / Math.max(1, points.length - 1);
  // SVG y grows downward, so the smallest distance (closest to the reference) is drawn at the TOP.
  const yFlipped = (v: number) => pad + ((v - min) / span) * (height - pad * 2);
  const path = points.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${yFlipped(v).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="my-3 h-20 w-full" role="img" aria-label={`${label}: ${points.map((p) => p.toFixed(3)).join(", ")}`}>
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#e5d6bd" />
      <path d={path} fill="none" stroke="#6e1423" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      {points.map((v, i) => (
        <circle key={i} cx={x(i)} cy={yFlipped(v)} r="3.5" fill={i === points.length - 1 ? "#a8792c" : "#6e1423"} />
      ))}
    </svg>
  );
}
