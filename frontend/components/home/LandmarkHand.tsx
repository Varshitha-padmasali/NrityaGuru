/**
 * Diagram of the 21 hand landmarks MediaPipe Hands returns, using its real
 * numbering and connections (0 = wrist, 4 = thumb tip, 8 = index tip,
 * 12 = middle tip, 16 = ring tip, 20 = pinky tip), drawn in a flat open hand
 * similar to Pataka. Explanatory illustration only — not live data.
 */
const POINTS: Array<[number, number]> = [
  [120, 272], // 0 wrist
  [92, 250], [74, 222], [70, 196], [76, 172], // 1–4 thumb
  [94, 162], [90, 118], [88, 90], [87, 64], // 5–8 index
  [117, 156], [117, 106], [117, 76], [117, 48], // 9–12 middle
  [140, 160], [142, 112], [143, 85], [144, 62], // 13–16 ring
  [160, 172], [165, 134], [167, 112], [168, 92], // 17–20 pinky
];

const CONNECTIONS: Array<[number, number]> = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [0, 17], [17, 18], [18, 19], [19, 20],
];

const TIPS = new Set([4, 8, 12, 16, 20]);

export function LandmarkHand({ className }: { className?: string }) {
  return (
    <svg viewBox="40 30 160 260" className={className} role="img" aria-label="Diagram of the 21 hand landmarks detected by MediaPipe Hands">
      <defs>
        <linearGradient id="ng-scan" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#c99a45" stopOpacity="0" />
          <stop offset="50%" stopColor="#c99a45" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#c99a45" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Faint palm silhouette */}
      <path
        d="M120 282 C 92 278 78 262 72 240 C 64 214 62 190 72 168 L 84 160 L 82 70 C 82 56 94 56 94 70 L 96 100 L 108 48 C 110 34 126 34 126 48 L 128 96 L 134 62 C 136 50 152 50 152 62 L 150 108 L 158 92 C 162 80 176 82 174 96 L 170 176 C 168 214 160 250 148 266 C 140 278 132 282 120 282 Z"
        fill="#ffffff"
        opacity="0.06"
      />
      <g stroke="#c99a45" strokeWidth="2" strokeLinecap="round" opacity="0.9">
        {CONNECTIONS.map(([a, b]) => (
          <line key={`${a}-${b}`} x1={POINTS[a][0]} y1={POINTS[a][1]} x2={POINTS[b][0]} y2={POINTS[b][1]} />
        ))}
      </g>
      {POINTS.map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r={TIPS.has(i) || i === 0 ? 5 : 3.6} fill={TIPS.has(i) ? "#f1e3c4" : "#fffdf8"} stroke="#6e1423" strokeWidth="1.5">
            <animate attributeName="r" values={TIPS.has(i) ? "5;6.5;5" : "3.6;4.4;3.6"} dur="2.4s" begin={`${i * 0.08}s`} repeatCount="indefinite" />
          </circle>
        </g>
      ))}
      <text x={POINTS[0][0] + 9} y={POINTS[0][1] + 4} fontSize="9" fill="#f1e3c4" opacity="0.8">0 wrist</text>
      <text x={POINTS[8][0] - 34} y={POINTS[8][1] - 6} fontSize="9" fill="#f1e3c4" opacity="0.8">8 index</text>
      <text x={POINTS[4][0] - 34} y={POINTS[4][1] + 3} fontSize="9" fill="#f1e3c4" opacity="0.8">4 thumb</text>
      {/* Scanning band */}
      <rect x="40" y="30" width="160" height="40" fill="url(#ng-scan)">
        <animate attributeName="y" values="20;260;20" dur="5s" repeatCount="indefinite" />
      </rect>
    </svg>
  );
}
