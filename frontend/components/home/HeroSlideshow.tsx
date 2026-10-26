"use client";

/**
 * Full-screen hero: eight single-hand mudras (asamyuta hastas), one at a time.
 *
 * - A costumed Bharatanatyam dancer (stage photo) fills a gold-edged temple
 *   arch with a glowing, slowly turning mandala behind it; a blurred copy of
 *   the same photo fills the stage so the colours always match.
 * - A round gold medallion shows the reference photo of the hand shape for the
 *   current mudra. The stage photo is atmosphere only; it is not claimed to
 *   show that mudra.
 * - Photos crossfade with a slow "Ken Burns" zoom; marigold petals drift down.
 * - A thumbnail strip shows every mudra; the active one fills like a timer.
 * - Pauses while the strip is hovered or focused, and has a Pause button
 *   (WCAG 2.2.2). With prefers-reduced-motion nothing auto-advances or moves.
 * - Photos are free-licence images from Wikimedia Commons (see lib/hero-mudras.ts
 *   for authors and licences); both credits are shown on the active photo.
 */
import Link from "next/link";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { HERO_MUDRAS } from "@/lib/hero-mudras";
import { listMudras } from "@/services/knowledge-service";
import { useApiQuery } from "@/hooks/useApiQuery";
import { getPhoto } from "@/lib/photos";
import { cn } from "@/lib/utils";
import { Mandala } from "@/components/brand/Mandala";
import { IconBook, IconCamera, IconSparkle } from "@/components/ui/Icons";

const SLIDE_MS = 6000;

/** AI-generated dancer image for a mudra if one has been generated, else the stage photo. */
function stageImage(m: (typeof HERO_MUDRAS)[number]) {
  const ai = getPhoto(m.slot).generated;
  return ai ? { src: ai.src, ai: true, position: m.aiPosition ?? "50% 30%" } : { src: m.dancer.src, ai: false, position: m.dancer.position };
}

// Fixed values (not random) so server and client render the same markup.
const PETALS = [
  { left: 6, size: 14, delay: 0, dur: 14, drift: 60 },
  { left: 16, size: 10, delay: 5, dur: 17, drift: -40 },
  { left: 27, size: 16, delay: 2, dur: 15, drift: 90 },
  { left: 41, size: 9, delay: 8, dur: 18, drift: -70 },
  { left: 55, size: 13, delay: 3, dur: 16, drift: 50 },
  { left: 68, size: 11, delay: 10, dur: 14, drift: -60 },
  { left: 79, size: 15, delay: 1, dur: 19, drift: 80 },
  { left: 90, size: 10, delay: 6, dur: 15, drift: -50 },
];

function subscribeReducedMotion(cb: () => void) {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}
const getReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function HeroSlideshow() {
  const [index, setIndex] = useState(0);
  const [cycle, setCycle] = useState(0); // restarts the zoom/progress animations
  const [userPaused, setUserPaused] = useState(false);
  const [hovering, setHovering] = useState(false);
  const reducedMotion = useSyncExternalStore(subscribeReducedMotion, getReducedMotion, () => false);
  const { data: catalogue } = useApiQuery((signal) => listMudras(signal), []);

  const paused = userPaused || hovering || reducedMotion;
  const visual = HERO_MUDRAS[index];
  const mudra = catalogue?.find((record) => record.id === visual.id);
  const current = stageImage(visual);

  const goTo = useCallback((i: number) => {
    setIndex((i + HERO_MUDRAS.length) % HERO_MUDRAS.length);
    setCycle((c) => c + 1);
  }, []);

  useEffect(() => {
    if (paused) return;
    const t = setTimeout(() => goTo(index + 1), SLIDE_MS);
    return () => clearTimeout(t);
  }, [paused, index, cycle, goTo]);

  // Keyboard: left/right arrows move between mudras when the hero has focus.
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") goTo(index + 1);
    if (e.key === "ArrowLeft") goTo(index - 1);
  };

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Bharatanatyam mudras, one at a time"
      onKeyDown={onKeyDown}
      className="relative isolate flex min-h-[calc(100svh-4rem)] flex-col overflow-hidden bg-[#0f0406] text-ivory"
    >
      {/* ── Stage backdrop: blurred copy of the current photo + lighting ── */}
      <div className="absolute inset-0 -z-10" aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative blurred backdrop */}
        <img
          key={`bg-${index}`}
          src={current.src}
          alt=""
          className="absolute inset-0 h-full w-full scale-125 animate-[ng-rise_1.4s_ease-out_both] object-cover blur-3xl saturate-150"
        />
        <div className="absolute inset-0 bg-[#0f0406]/75" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0f0406] via-[#0f0406]/60 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0f0406] via-transparent to-[#0f0406]/50" />
        <div
          className="absolute inset-0 mix-blend-soft-light"
          style={{ background: `radial-gradient(ellipse 40% 55% at 72% 40%, rgb(${visual.accent} / 0.5), transparent 70%)`, transition: "background 1.2s" }}
        />
        {/* drifting marigold petals */}
        {!reducedMotion
          ? PETALS.map((p, i) => (
              <span
                key={i}
                className="absolute top-0 block rounded-[50%_0_50%_0] bg-gradient-to-br from-[#ffb347] to-[#e0662b] opacity-0"
                style={
                  {
                    left: `${p.left}%`,
                    width: p.size,
                    height: p.size * 1.4,
                    "--drift": `${p.drift}px`,
                    animation: `ng-petal ${p.dur}s linear ${p.delay}s infinite`,
                  } as React.CSSProperties
                }
              />
            ))
          : null}
      </div>

      <div className="mx-auto grid w-full max-w-6xl flex-1 items-center gap-10 px-4 pb-6 pt-14 sm:px-6 lg:grid-cols-[1.05fr_0.95fr]">
        {/* ── Text ── */}
        <div className="max-w-xl">
          <p className="rise mb-6 inline-flex items-center gap-2 rounded-full border border-gold-bright/40 bg-black/25 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-gold-bright backdrop-blur">
            <IconSparkle width={14} height={14} /> AI-assisted Bharatanatyam
          </p>
          <h1 className="rise font-display text-[3.2rem] font-semibold leading-[0.98] drop-shadow-[0_4px_24px_rgb(0_0_0/0.6)] sm:text-7xl lg:text-[5.2rem]">
            Every <em className="bg-gradient-to-r from-gold-bright via-gold-soft to-gold-bright bg-clip-text font-medium text-transparent">mudra</em>
            <br />
            tells a story.
          </h1>

          {/* Caption for the current mudra */}
          <div key={`cap-${index}-${cycle}`} className="rise mt-8 border-l-2 border-gold-bright/70 pl-5" aria-live={paused ? "polite" : "off"}>
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-gold-bright/90">
              Featured image {String(index + 1).padStart(2, "0")} of {String(HERO_MUDRAS.length).padStart(2, "0")} · {mudra?.category ?? "Bharatanatyam hasta"}
            </p>
            <p className="mt-1 font-display text-4xl italic text-gold-soft sm:text-5xl">{mudra?.name ?? "Explore the mudra library"}</p>
            <p className="mt-2 max-w-md text-base leading-relaxed text-ivory/80">
              {mudra?.meaning ?? "The knowledge base lists this gesture name; verified meanings and usage are shown when a cited record supplies them."}
            </p>
          </div>

          <div className="rise mt-9 flex flex-wrap gap-3 [animation-delay:200ms]">
            <Link
              href="/learn"
              className="inline-flex h-13 items-center gap-2.5 rounded-full bg-gold-bright px-7 text-base font-semibold text-maroon-dark shadow-[0_10px_30px_-10px_rgb(201_154_69/0.7)] transition-colors hover:bg-gold-soft"
            >
              <IconBook width={18} height={18} /> Start learning
            </Link>
            <Link
              href="/practice"
              className="inline-flex h-13 items-center gap-2.5 rounded-full border border-ivory/35 bg-black/20 px-7 text-base font-semibold text-ivory backdrop-blur transition-colors hover:border-gold-bright hover:text-gold-soft"
            >
              <IconCamera width={18} height={18} /> Practise a mudra
            </Link>
          </div>
        </div>

        {/* ── Temple-arch frame ── */}
        <div className="relative mx-auto w-full max-w-[26rem] lg:max-w-none lg:w-[22rem] lg:justify-self-end xl:w-[25rem]">
          <Mandala spin className="pointer-events-none absolute left-1/2 top-1/2 -z-10 h-[135%] w-[135%] -translate-x-1/2 -translate-y-1/2 text-gold-bright/35" />
          <div
            className="pointer-events-none absolute -inset-6 -z-10 animate-[ng-glow_5s_ease-in-out_infinite] rounded-[999px]"
            style={{ background: `radial-gradient(circle, rgb(${visual.accent} / 0.4), transparent 65%)` }}
            aria-hidden="true"
          />
          {/* gold outer ring */}
          <div className="rounded-t-[999px] rounded-b-[2.25rem] bg-gradient-to-b from-gold-soft via-gold-bright to-gold p-[3px] shadow-[0_30px_80px_-20px_rgb(0_0_0/0.8)]">
            <div className="rounded-t-[999px] rounded-b-[2.1rem] bg-[#0f0406] p-2">
              <div className="relative aspect-[3/4] overflow-hidden rounded-t-[999px] rounded-b-[1.75rem] bg-[#2a1012]">
                {HERO_MUDRAS.map((m, i) => {
                  const active = i === index;
                  const img = stageImage(m);
                  return (
                    <div
                      key={m.id}
                      role="group"
                      aria-roledescription="slide"
                      aria-label={`${i + 1} of ${HERO_MUDRAS.length}: ${catalogue?.find((record) => record.id === m.id)?.name ?? "Bharatanatyam hand gesture"}`}
                      aria-hidden={!active}
                      className={cn("absolute inset-0 transition-opacity duration-[1600ms] ease-out", active ? "opacity-100" : "opacity-0")}
                    >
                      <div
                        key={active ? `zoom-${cycle}` : "still"}
                        className={cn("h-full w-full", active && !reducedMotion && "animate-[ng-kenburns_7.5s_ease-out_forwards]")}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element -- local static photo */}
                        <img
                          src={img.src}
                          alt={img.ai ? `AI-generated image of a Bharatanatyam dancer; the catalogue label is ${catalogue?.find((record) => record.id === m.id)?.name ?? "not available"}` : "A Bharatanatyam dancer in traditional costume performing on stage"}
                          width={1000}
                          height={1500}
                          loading={i < 2 ? "eager" : "lazy"}
                          decoding="async"
                          style={{ objectPosition: img.position }}
                          className="h-full w-full object-cover"
                        />
                      </div>
                    </div>
                  );
                })}
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" aria-hidden="true" />
                <p className="pointer-events-none absolute inset-x-0 bottom-10 text-center font-display text-3xl italic text-gold-soft drop-shadow-lg">{mudra?.name ?? "NrityaGuru"}</p>
                <p className="absolute inset-x-0 bottom-2 mx-auto w-fit max-w-[92%] truncate rounded-full bg-black/50 px-2 py-0.5 text-[10px] font-medium text-white/90 backdrop-blur-sm">
                  {current.ai ? (
                    "AI-generated with Gemini · "
                  ) : (
                    <>
                      Photo:{" "}
                      <a href={visual.dancer.page} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
                        {visual.dancer.artist}
                      </a>
                      {" · "}
                    </>
                  )}
                  Hand shape:{" "}
                  <a href={visual.page} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
                    {visual.artist}
                  </a>{" "}
                  / Wikimedia Commons · {visual.license}
                </p>
              </div>
            </div>
          </div>
          {/* Reference hand photo for the current mudra */}
          <figure className="absolute -left-4 bottom-16 z-10 sm:-left-10 lg:-left-16">
            <div className="h-32 w-32 overflow-hidden rounded-full border-[3px] border-gold-bright bg-[#2a1012] shadow-[0_12px_40px_-8px_rgb(0_0_0/0.8)] ring-4 ring-[#0f0406]/70 sm:h-40 sm:w-40">
              {/* eslint-disable-next-line @next/next/no-img-element -- local static photo */}
              <img
                key={visual.id}
                src={visual.src}
                alt={`Reference photo accompanying ${mudra?.name ?? "a Bharatanatyam hasta"}`}
                width={128}
                height={128}
                className="h-full w-full animate-[ng-rise_0.8s_ease-out_both] object-cover"
              />
            </div>
            <figcaption className="mt-2 text-center text-[10px] font-semibold uppercase tracking-[0.2em] text-gold-bright drop-shadow">Hand shape</figcaption>
          </figure>
        </div>
      </div>

      {/* ── Mudra navigator (thumbnails) ── */}
      <div
        className="mx-auto w-full max-w-6xl px-4 pb-8 sm:px-6"
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
        onFocus={() => setHovering(true)}
        onBlur={() => setHovering(false)}
      >
        <div className="flex items-end gap-3">
          <ol className="grid flex-1 grid-cols-8 gap-1.5 sm:gap-3" aria-label="Mudras">
            {HERO_MUDRAS.map((m, i) => {
              const active = i === index;
              const done = i < index;
              const record = catalogue?.find((item) => item.id === m.id);
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => goTo(i)}
                    aria-current={active ? "step" : undefined}
                    aria-label={`Show hand gesture ${i + 1}: ${record?.name ?? "name unavailable"}`}
                    className="group block w-full text-left"
                  >
                    <span
                      className={cn(
                        "mb-2 block aspect-[4/3] overflow-hidden rounded-t-full rounded-b-lg border transition-all duration-500",
                        active ? "border-gold-bright opacity-100 shadow-[0_0_20px_rgb(201_154_69/0.55)]" : "border-ivory/20 opacity-50 group-hover:opacity-90",
                      )}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element -- local static photo */}
                      <img src={stageImage(m).src} alt="" width={160} height={120} loading="lazy" decoding="async" style={{ objectPosition: stageImage(m).position }} className="h-full w-full object-cover" />
                    </span>
                    <span
                      className={cn(
                        "mb-2 hidden truncate text-[11px] font-semibold uppercase tracking-wider transition-colors md:block",
                        active ? "text-gold-bright" : "text-ivory/45 group-hover:text-ivory/80",
                      )}
                    >
                      {record?.name ?? `Gesture ${i + 1}`}
                    </span>
                    <span className="block h-[3px] overflow-hidden rounded-full bg-ivory/20">
                      <span
                        key={active ? `p-${cycle}` : "idle"}
                        className={cn(
                          "block h-full rounded-full bg-gold-bright",
                          done && "w-full",
                          !active && !done && "w-0",
                          active && (paused ? "w-full" : "w-0 animate-[ng-progress_linear_forwards]"),
                        )}
                        style={active && !paused ? { animationDuration: `${SLIDE_MS}ms` } : undefined}
                      />
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
          <button
            type="button"
            onClick={() => setUserPaused((p) => !p)}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-ivory/30 bg-black/30 text-ivory backdrop-blur transition-colors hover:border-gold-bright hover:text-gold-bright"
            aria-label={userPaused ? "Play slideshow" : "Pause slideshow"}
          >
            {userPaused ? (
              <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M7 5l12 7-12 7z" fill="currentColor" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
                <rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" />
                <rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
