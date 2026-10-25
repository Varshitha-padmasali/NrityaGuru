import { StockPhoto } from "@/components/brand/StockPhoto";
import { Mandala } from "@/components/brand/Mandala";

/**
 * The well-known Abhinaya Darpana verse on the hand leading the eyes, mind,
 * bhava and rasa — the reason NrityaGuru starts from hastas.
 */
export function ShlokaSection() {
  return (
    <section aria-labelledby="shloka-heading" className="relative overflow-hidden bg-maroon-dark text-ivory">
      <Mandala className="pointer-events-none absolute -left-40 -top-40 h-[560px] w-[560px] text-gold/20" />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-20 sm:px-6 md:grid-cols-[1fr_0.8fr]">
        <div>
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.25em] text-gold-bright">Abhinaya Darpana</p>
          <h2 id="shloka-heading" className="sr-only">
            Why we begin with the hand
          </h2>
          <blockquote>
            <p lang="sa" className="font-devanagari text-2xl leading-[1.9] text-gold-soft sm:text-3xl">
              यतो हस्तस्ततो दृष्टिः यतो दृष्टिस्ततो मनः ।<br />
              यतो मनस्ततो भावो यतो भावस्ततो रसः ॥
            </p>
            <p className="mt-6 font-display text-xl italic leading-relaxed text-ivory/80 sm:text-2xl">
              Yato hastas tato dṛṣṭiḥ, yato dṛṣṭis tato manaḥ,
              <br />
              yato manas tato bhāvo, yato bhāvas tato rasaḥ.
            </p>
            <footer className="mt-6 max-w-lg text-lg leading-relaxed text-ivory/90">
              Where the hand goes, the eyes follow. Where the eyes go, the mind follows. Where the mind goes, feeling arises — and from feeling comes{" "}
              <em className="font-display text-xl text-gold-bright">rasa</em>.
            </footer>
          </blockquote>
          <p className="mt-8 max-w-lg text-sm leading-relaxed text-ivory/60">
            That is why NrityaGuru starts with hastas: the gestures are where expression begins, and where a camera can give you the clearest feedback.
          </p>
        </div>
        <div className="relative mx-auto w-full max-w-sm">
          <div className="absolute -inset-4 rounded-t-[999px] border border-gold/40" aria-hidden="true" />
          <StockPhoto photo="shloka" width={800} height={1000} className="aspect-[4/5] rounded-t-[999px] rounded-b-2xl" />
        </div>
      </div>
    </section>
  );
}
