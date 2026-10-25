/**
 * Original illustration of a Bharatanatyam dancer in aramandi (half-sitting)
 * with arms extended — drawn for NrityaGuru, not traced from any photograph.
 * Used as the hero visual when no photo is supplied, and as decoration.
 * It is decorative only, never a mudra reference.
 */
export function DancerIllustration({ className, title = "Illustration of a Bharatanatyam dancer in aramandi" }: { className?: string; title?: string }) {
  return (
    <svg viewBox="0 0 400 520" className={className} role={title ? "img" : undefined} aria-label={title || undefined} aria-hidden={title ? undefined : true}>
      <defs>
        <radialGradient id="ng-halo" cx="50%" cy="40%" r="55%">
          <stop offset="0%" stopColor="#f1e3c4" />
          <stop offset="70%" stopColor="#f6ecd8" />
          <stop offset="100%" stopColor="#fbf6ec" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ng-silk" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7d1a2b" />
          <stop offset="100%" stopColor="#4a0d18" />
        </linearGradient>
      </defs>

      {/* Temple arch + halo */}
      <circle cx="200" cy="215" r="200" fill="url(#ng-halo)" />
      <path d="M60 470 V230 A140 140 0 0 1 340 230 V470" fill="none" stroke="#c99a45" strokeWidth="2" opacity="0.55" />
      <path d="M78 470 V234 A122 122 0 0 1 322 234 V470" fill="none" stroke="#c99a45" strokeWidth="1" strokeDasharray="2 6" opacity="0.6" />

      {/* Arms (behind torso) — extended to the sides, palms raised */}
      <g fill="none" stroke="#5c1120" strokeLinecap="round" strokeLinejoin="round">
        <path d="M170 150 Q140 160 122 157 L90 144" strokeWidth="11" />
        <path d="M230 150 Q260 160 278 157 L310 144" strokeWidth="11" />
      </g>
      {/* Hands in pataka: fingers held together pointing up, thumb bent in */}
      <g fill="#5c1120">
        <path d="M86 147 C82 132 81 116 83 104 C84 99 89 99 90 103 C91 116 93 131 95 145 Z" />
        <path d="M314 147 C318 132 319 116 317 104 C316 99 311 99 310 103 C309 116 307 131 305 145 Z" />
      </g>
      <g fill="none" stroke="#5c1120" strokeWidth="3.5" strokeLinecap="round">
        <path d="M93 134 Q99 128 100 121" />
        <path d="M307 134 Q301 128 300 121" />
      </g>
      {/* Bangles */}
      <g stroke="#c99a45" strokeWidth="3" strokeLinecap="round">
        <path d="M95 136 L97 150" />
        <path d="M305 136 L303 150" />
      </g>

      {/* Legs in aramandi: knees out, heels together, feet turned out */}
      <g fill="none" stroke="url(#ng-silk)" strokeLinecap="round" strokeLinejoin="round">
        <path d="M184 250 L132 336 L170 424" strokeWidth="30" />
        <path d="M216 250 L268 336 L230 424" strokeWidth="30" />
      </g>
      {/* Feet */}
      <g fill="#5c1120">
        <path d="M168 418 C150 424 136 436 132 446 C146 448 166 442 180 432 Z" />
        <path d="M232 418 C250 424 264 436 268 446 C254 448 234 442 220 432 Z" />
      </g>
      {/* Ghungroo (ankle bells) */}
      <g fill="#c99a45">
        {[0, 1, 2, 3].map((i) => (
          <circle key={`l${i}`} cx={160 + i * 5} cy={418 - i * 1.5} r="2.6" />
        ))}
        {[0, 1, 2, 3].map((i) => (
          <circle key={`r${i}`} cx={240 - i * 5} cy={418 - i * 1.5} r="2.6" />
        ))}
      </g>

      {/* Pleated fan between the knees */}
      <path d="M200 244 L146 372 Q200 392 254 372 Z" fill="#8a2234" />
      <g stroke="#c99a45" strokeWidth="1.4" opacity="0.9">
        {[-44, -30, -16, -2, 12, 26, 40].map((dx) => (
          <line key={dx} x1="200" y1="248" x2={200 + dx * 1.15} y2={378 - Math.abs(dx) * 0.12} />
        ))}
      </g>
      <path d="M146 372 Q200 392 254 372" fill="none" stroke="#c99a45" strokeWidth="4" />

      {/* Torso */}
      <path d="M168 144 Q200 134 232 144 L224 202 Q220 226 222 240 L178 240 Q180 226 176 202 Z" fill="url(#ng-silk)" />
      {/* Sash across the chest */}
      <path d="M170 150 Q196 182 222 236" fill="none" stroke="#c99a45" strokeWidth="5" opacity="0.85" />
      {/* Waist belt (oddiyanam) */}
      <rect x="174" y="236" width="52" height="11" rx="5" fill="#c99a45" />
      <circle cx="200" cy="241.5" r="4" fill="#a8792c" />

      {/* Neck + necklace */}
      <rect x="193" y="118" width="14" height="22" rx="6" fill="#5c1120" />
      <path d="M182 142 Q200 160 218 142" fill="none" stroke="#c99a45" strokeWidth="3" />

      {/* Head, hair bun with jasmine, head ornament */}
      <circle cx="200" cy="96" r="25" fill="#5c1120" />
      <circle cx="224" cy="80" r="13" fill="#3d0a14" />
      <path d="M214 68 Q232 62 238 80" fill="none" stroke="#fffdf8" strokeWidth="4" strokeDasharray="1 4" strokeLinecap="round" />
      <path d="M183 79 Q200 70 217 79" fill="none" stroke="#c99a45" strokeWidth="2.5" />
      <circle cx="200" cy="82" r="3" fill="#c99a45" />

      {/* Stage line */}
      <line x1="70" y1="456" x2="330" y2="456" stroke="#c99a45" strokeWidth="1.5" opacity="0.6" />
    </svg>
  );
}

/** Tiny mark used in the header logo. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <circle cx="16" cy="16" r="15" fill="#6e1423" />
      <path d="M16 6c3 4 3 8 0 12-3-4-3-8 0-12z" fill="#c99a45" />
      <path d="M8 21c4-1 6 1 8 4 2-3 4-5 8-4" fill="none" stroke="#f1e3c4" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
