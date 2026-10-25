/**
 * Scrolling band of the 28 asamyuta (single-hand) hasta names from the
 * Abhinaya Darpana. Decorative only — it does not claim the app supports them all.
 * Pauses on hover and stops entirely for prefers-reduced-motion users.
 */
const HASTAS = [
  "Pataka", "Tripataka", "Ardhapataka", "Kartarimukha", "Mayura", "Ardhachandra", "Arala",
  "Shukatunda", "Mushti", "Shikhara", "Kapittha", "Katakamukha", "Suchi", "Chandrakala",
  "Padmakosha", "Sarpashirsha", "Mrigashirsha", "Simhamukha", "Kangula", "Alapadma",
  "Chatura", "Bhramara", "Hamsasya", "Hamsapaksha", "Samdamsha", "Mukula", "Tamrachuda", "Trishula",
];

export function HastaMarquee() {
  const row = (hidden: boolean) => (
    <ul className="flex shrink-0 items-center gap-8 pr-8" aria-hidden={hidden || undefined}>
      {HASTAS.map((name) => (
        <li key={name} className="flex items-center gap-8 whitespace-nowrap font-display text-2xl italic text-gold-soft sm:text-3xl">
          {name}
          <span className="text-base not-italic text-gold-bright" aria-hidden="true">
            ✦
          </span>
        </li>
      ))}
    </ul>
  );

  return (
    <section aria-label="The 28 asamyuta hastas" className="group relative overflow-hidden border-y border-gold/30 bg-maroon-dark py-5">
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24 bg-gradient-to-r from-maroon-dark to-transparent" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24 bg-gradient-to-l from-maroon-dark to-transparent" aria-hidden="true" />
      <div className="flex w-max animate-[ng-marquee_70s_linear_infinite] group-hover:[animation-play-state:paused] motion-reduce:animate-none">
        {row(false)}
        {row(true)}
      </div>
    </section>
  );
}
