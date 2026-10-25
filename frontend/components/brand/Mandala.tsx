/**
 * Decorative lotus mandala drawn from simple repeated petals (pure SVG, no image).
 * Purely ornamental — aria-hidden.
 */
export function Mandala({ className, spin = false }: { className?: string; spin?: boolean }) {
  const outer = Array.from({ length: 24 }, (_, i) => i * 15);
  const middle = Array.from({ length: 16 }, (_, i) => i * 22.5);
  const inner = Array.from({ length: 8 }, (_, i) => i * 45);
  const dots = Array.from({ length: 48 }, (_, i) => i * 7.5);

  return (
    <svg viewBox="-200 -200 400 400" className={className} aria-hidden="true" focusable="false">
      <g className={spin ? "origin-center animate-[ng-spin_120s_linear_infinite]" : undefined} fill="none" stroke="currentColor">
        <circle r="196" strokeWidth="0.8" opacity="0.5" />
        <circle r="186" strokeWidth="0.5" strokeDasharray="1 5" opacity="0.7" />
        {dots.map((a) => (
          <circle key={`d${a}`} r="1.6" cx="0" cy="-176" transform={`rotate(${a})`} fill="currentColor" stroke="none" opacity="0.6" />
        ))}
        {outer.map((a) => (
          <path key={`o${a}`} d="M0 -168 C 18 -140, 18 -112, 0 -92 C -18 -112, -18 -140, 0 -168 Z" transform={`rotate(${a})`} strokeWidth="0.9" opacity="0.55" />
        ))}
        <circle r="92" strokeWidth="0.8" opacity="0.6" />
        {middle.map((a) => (
          <path key={`m${a}`} d="M0 -90 C 22 -70, 20 -48, 0 -36 C -20 -48, -22 -70, 0 -90 Z" transform={`rotate(${a})`} strokeWidth="1" opacity="0.7" />
        ))}
        {inner.map((a) => (
          <path key={`i${a}`} d="M0 -34 C 12 -24, 12 -12, 0 -6 C -12 -12, -12 -24, 0 -34 Z" transform={`rotate(${a})`} strokeWidth="1" opacity="0.85" />
        ))}
        <circle r="5" fill="currentColor" stroke="none" opacity="0.8" />
      </g>
    </svg>
  );
}
