/**
 * The eight single-hand mudras (asamyuta hastas) shown in the home-page hero.
 *
 * Both image sets come from Wikimedia Commons and are credited on the page as
 * their licences require:
 *   - public/images/hands/    hand-shape close-ups, frames from the "Learn Asamyuta
 *                             Hasta" video lesson by Kalavenue (Arts venue), CC BY 3.0
 *   - public/images/dancers/  stage photographs by Suyash Dwivedi, CC BY-SA 4.0
 *
 * The short descriptions summarise the traditional Abhinaya Darpana
 * descriptions for a decorative hero. They are NOT the curated knowledge base:
 * the Mudras and Learn pages (backed by the API) remain the source of truth,
 * and a teacher should confirm fine hand details.
 */
import type { PhotoKey } from "./photos";

export interface HeroMudra {
  id: string;
  /**
   * Image slot (lib/photos.json) for an AI-generated dancer performing this
   * mudra (npm run images:generate). Used when it exists, else `dancer` below.
   */
  slot: PhotoKey;
  /** CSS object-position for the AI image in the arch (keeps the hands in frame). */
  aiPosition?: string;
  /** "r g b" tint for the stage glow, matched to the costume colour in the prompt. */
  accent: string;
  name: string;
  /** Meaning of the Sanskrit name. */
  english: string;
  /** How the hand is held. */
  description: string;
  usedFor: string;
  /** Close-up of the hand shape; the video names each hasta, so it is a labelled reference. */
  src: string;
  /** Commons description page (source + licence) of the hand photo. */
  page: string;
  artist: string;
  license: string;
  /**
   * Stage photo of a Bharatanatyam dancer in costume, shown large in the arch.
   * It is atmosphere: the photographer did not label which mudra it shows, so
   * the caption never claims it does.
   */
  dancer: { src: string; page: string; artist: string; license: string; position: string };
}

const ARTIST = "Kalavenue";
const LICENSE = "CC BY-SA 4.0";
const HAND_LICENSE = "CC BY 3.0";
const HAND_PAGE = "https://commons.wikimedia.org/wiki/File:Bharatanatyam_-_Learn_Asamyuta_Hasta_(HD)_(Video_Lesson_for_Beginners).webm";
const commons = (file: string) => `https://commons.wikimedia.org/wiki/File:${file}`;
const stage = (n: string, position = "50% 30%") => ({
  src: `/images/dancers/m${n}.jpg`,
  page: commons(`Bharatanatyam_Mudra_${n}.jpg`),
  artist: "Suyash Dwivedi",
  license: LICENSE,
  position,
});

export const HERO_MUDRAS: HeroMudra[] = [
  {
    id: "pataka",
    accent: "70 120 255",
    slot: "mudra1",
    name: "Pataka",
    english: "The flag",
    description: "All four fingers held straight and together, the thumb bent in.",
    usedFor: "clouds, a forest, a river, a blessing, “no”.",
    src: "/images/hands/pataka.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("02", "50% 30%"),
  },
  {
    id: "tripataka",
    aiPosition: "30% 30%",
    accent: "255 90 170",
    slot: "mudra2",
    name: "Tripataka",
    english: "The three-part flag",
    description: "Like Pataka, but the ring finger is bent down.",
    usedFor: "a crown, a tree, a flame, a lamp.",
    src: "/images/hands/tripataka.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("04", "50% 30%"),
  },
  {
    id: "mushti",
    accent: "220 50 50",
    slot: "mudra3",
    name: "Mushti",
    english: "The fist",
    description: "Fingers curled into the palm, the thumb resting over them.",
    usedFor: "steadiness, holding something firmly, wrestling.",
    src: "/images/hands/mushti.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("07", "50% 30%"),
  },
  {
    id: "kapittha",
    aiPosition: "25% 30%",
    accent: "40 190 160",
    slot: "mudra4",
    name: "Kapittha",
    english: "The wood-apple",
    description: "Fingers curled, the index finger pressed down over the thumb.",
    usedFor: "holding cymbals or a flower, milking, Lakshmi and Saraswati.",
    src: "/images/hands/kapittha.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("09", "50% 30%"),
  },
  {
    id: "alapadma",
    accent: "255 170 200",
    aiPosition: "22% 35%",
    slot: "mudra5",
    name: "Alapadma",
    english: "The fully bloomed lotus",
    description: "All fingers spread wide and gently curved outward.",
    usedFor: "a lotus, the full moon, beauty, a round pot.",
    src: "/images/hands/alapadma.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("10", "50% 30%"),
  },
  {
    id: "hamsasya",
    accent: "235 235 255",
    slot: "mudra6",
    name: "Hamsasya",
    english: "The swan’s beak",
    description: "Thumb and index finger tips touch; the other three fingers stay extended.",
    usedFor: "pearls, painting, tying a thread, auspiciousness.",
    src: "/images/hands/hamsasya.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("05", "42% 50%"),
  },
  {
    id: "mayura",
    aiPosition: "50% 20%",
    accent: "110 90 255",
    slot: "mudra7",
    name: "Mayura",
    english: "The peacock",
    description: "The thumb touches the ring finger; the other fingers stay extended.",
    usedFor: "a peacock, a creeper, applying a tilak.",
    src: "/images/hands/mayura.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("13", "50% 50%"),
  },
  {
    id: "shikhara",
    accent: "255 150 40",
    aiPosition: "40% 30%",
    slot: "mudra8",
    name: "Shikhara",
    english: "The peak",
    description: "A closed fist with the thumb pointing straight up.",
    usedFor: "a bow, a pillar, a husband, asking a question.",
    src: "/images/hands/shikhara.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("11", "82% 50%"),
  },
];
