/**
 * The traditional order of a Bharatanatyam recital (the margam), used as the
 * story of the home-page slideshow. Each step is paired with an image slot
 * (seq1–seq8) in lib/photos.json / lib/image-prompts.json.
 */
import type { PhotoKey } from "./photos";

export interface MargamStep {
  slot: PhotoKey;
  name: string;
  /** Short meaning for the caption. */
  meaning: string;
}

export const MARGAM: MargamStep[] = [
  { slot: "seq1", name: "Pushpanjali", meaning: "An offering of flowers — a salutation to the divine, the guru and the audience." },
  { slot: "seq2", name: "Alarippu", meaning: "“To blossom”: the body awakens, limb by limb, in pure rhythm." },
  { slot: "seq3", name: "Jatiswaram", meaning: "Pure dance (nritta) woven to musical notes — line, rhythm and footwork." },
  { slot: "seq4", name: "Shabdam", meaning: "The first story: expression (abhinaya) enters with song." },
  { slot: "seq5", name: "Varnam", meaning: "The centrepiece, where intricate rhythm and deep expression meet." },
  { slot: "seq6", name: "Padam", meaning: "A slow, intimate song of love and devotion, told through the eyes." },
  { slot: "seq7", name: "Tillana", meaning: "A joyful, brisk finale bursting with rhythm." },
  { slot: "seq8", name: "Mangalam", meaning: "A closing prayer of gratitude." },
];
