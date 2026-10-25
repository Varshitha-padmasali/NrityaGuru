import Link from "next/link";
import { StockPhoto } from "@/components/brand/StockPhoto";
import { Mandala } from "@/components/brand/Mandala";
import { ButtonLink } from "@/components/ui/Button";
import { IconArrowRight, IconBook, IconCamera, IconChart, IconHand, IconSearch, IconSparkle } from "@/components/ui/Icons";
import { RecentActivity } from "@/components/progress/RecentActivity";
import { HastaMarquee } from "@/components/home/HastaMarquee";
import { HeroSlideshow } from "@/components/home/HeroSlideshow";
import { ShlokaSection } from "@/components/home/ShlokaSection";
import { LandmarkHand } from "@/components/home/LandmarkHand";

const JOURNEY = [
  { icon: IconSearch, title: "Express", text: "Type a sentence, a line of lyrics or a concept." },
  { icon: IconBook, title: "Discover", text: "Matching hastas come from a curated, sourced knowledge base." },
  { icon: IconSparkle, title: "Understand", text: "The AI tutor explains meaning and usage in plain words." },
  { icon: IconCamera, title: "Perform", text: "Record yourself holding the mudra in front of your camera." },
  { icon: IconHand, title: "Compare", text: "Your movement is aligned with a reference, frame by frame." },
  { icon: IconChart, title: "Grow", text: "Evidence-based feedback, and a history of every attempt." },
];

const PIPELINE = [
  { step: "OpenCV", text: "reads your recording frame by frame" },
  { step: "MediaPipe Hands", text: "finds 21 landmarks on each hand" },
  { step: "Features", text: "turns them into distances and finger angles" },
  { step: "MLP", text: "recognises which hasta each moment looks like" },
  { step: "DTW", text: "aligns your timing with the reference and measures the gap" },
  { step: "Gemini", text: "explains only what was measured, in simple words" },
];

export default function HomePage() {
  return (
    <>
      <HeroSlideshow />

      <HastaMarquee />

      {/* ───────── Journey ───────── */}
      <section className="relative mx-auto max-w-6xl px-4 py-20 sm:px-6" aria-labelledby="journey-heading">
        <div className="mb-14 text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-gold">The learning loop</p>
          <h2 id="journey-heading" className="font-display text-4xl font-semibold text-maroon-dark sm:text-5xl">
            From a sentence to the stage
          </h2>
        </div>
        <ol className="relative grid gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
          {/* dotted path behind the steps (desktop) */}
          <div className="pointer-events-none absolute left-[8%] right-[8%] top-8 hidden border-t-2 border-dotted border-gold/40 lg:block" aria-hidden="true" />
          <div className="pointer-events-none absolute bottom-[calc(50%-1rem)] left-[8%] right-[8%] hidden border-t-2 border-dotted border-gold/40 lg:block" aria-hidden="true" />
          {JOURNEY.map(({ icon: Icon, title, text }, i) => (
            <li key={title} className="relative flex flex-col items-center px-6 text-center">
              <span className="relative z-10 flex h-16 w-16 items-center justify-center rounded-full border-2 border-gold/60 bg-paper text-maroon shadow-[0_0_0_6px_var(--color-ivory)]">
                <Icon width={26} height={26} />
                <span className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full bg-maroon font-display text-sm font-semibold text-gold-soft">
                  {i + 1}
                </span>
              </span>
              <h3 className="mt-5 font-display text-3xl font-semibold text-maroon-dark">{title}</h3>
              <p className="mt-2 max-w-xs leading-relaxed text-ink-muted">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <ShlokaSection />

      {/* ───────── How the camera sees you ───────── */}
      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6" aria-labelledby="pipeline-heading">
        <div className="grid items-center gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-maroon-dark via-maroon to-[#3a0a13] p-8 shadow-[var(--shadow-card)]">
            <Mandala className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 text-gold/15" />
            <p className="relative text-xs font-semibold uppercase tracking-[0.25em] text-gold-bright">What the camera sees</p>
            <LandmarkHand className="relative mx-auto mt-4 h-80 w-full max-w-xs" />
            <p className="relative mt-2 text-center text-xs text-ivory/60">Illustration of MediaPipe&apos;s 21-point hand model</p>
          </div>
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-gold">How evaluation works</p>
            <h2 id="pipeline-heading" className="font-display text-4xl font-semibold text-maroon-dark sm:text-5xl">
              Not a guess — a measurement.
            </h2>
            <p className="mt-4 max-w-xl text-lg leading-relaxed text-ink-muted">
              Your feedback is built from what the pipeline actually measured in your video. The AI tutor puts it into words; it never invents a mistake.
            </p>
            <ol className="mt-8 space-y-0">
              {PIPELINE.map((p, i) => (
                <li key={p.step} className="group relative flex gap-4 pb-5 last:pb-0">
                  {i < PIPELINE.length - 1 ? <span className="absolute left-[15px] top-8 h-full w-px bg-gold/40" aria-hidden="true" /> : null}
                  <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-gold/60 bg-paper text-sm font-semibold text-maroon">
                    {i + 1}
                  </span>
                  <p className="pt-1 text-ink">
                    <span className="font-semibold text-maroon">{p.step}</span> <span className="text-ink-muted">{p.text}</span>
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* ───────── Gallery: on stage ───────── */}
      <section className="relative overflow-hidden bg-[#14060a] py-20 text-ivory" aria-labelledby="gallery-heading">
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(ellipse 55% 45% at 50% 0%, rgb(214 150 60 / 0.22), transparent 70%)" }}
          aria-hidden="true"
        />
        <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
          <div className="mb-10 flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-gold-bright">On stage</p>
              <h2 id="gallery-heading" className="font-display text-4xl font-semibold sm:text-5xl">
                Practise today. <span className="italic text-gold-bright">Perform tomorrow.</span>
              </h2>
              <p className="mt-3 max-w-lg text-ivory/65">Your guru guides you in class. NrityaGuru helps you practise in between.</p>
            </div>
            <Link
              href="/practice"
              className="inline-flex h-11 items-center gap-2 self-start rounded-full border border-gold-bright/60 px-5 text-[15px] font-semibold text-gold-soft transition-colors hover:bg-white/10 sm:self-auto"
            >
              <IconCamera width={18} height={18} /> Begin practice
            </Link>
          </div>
          <div className="grid auto-rows-[190px] grid-cols-2 gap-3 sm:auto-rows-[230px] md:grid-cols-4 md:gap-4">
            <StockPhoto photo="blackPortrait" width={900} height={940} className="col-span-2 row-span-2 rounded-[1.75rem]" />
            <StockPhoto photo="redStage" width={500} height={940} className="row-span-2 rounded-t-[999px] rounded-b-[1.75rem]" />
            <StockPhoto photo="smileStage" width={500} height={460} className="rounded-[1.75rem]" />
            <StockPhoto photo="greenCostume" width={500} height={460} className="rounded-[1.75rem]" />
          </div>
        </div>
      </section>

      {/* ───────── Recent practice ───────── */}
      <section className="mx-auto max-w-6xl px-4 pt-20 sm:px-6" aria-labelledby="recent-heading">
        <div className="mb-6 flex items-end justify-between gap-4">
          <h2 id="recent-heading" className="font-display text-4xl font-semibold text-maroon-dark">
            Recent practice
          </h2>
          <ButtonLink href="/progress" variant="ghost" size="sm">
            All sessions <IconArrowRight width={16} height={16} />
          </ButtonLink>
        </div>
        <RecentActivity />
      </section>
    </>
  );
}
