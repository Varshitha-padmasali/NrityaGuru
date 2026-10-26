/**
 * Eight attributed hand-shape photographs used as home-page visuals.
 *
 * Both image sets come from Wikimedia Commons and are credited on the page as
 * their licences require:
 *   - public/images/hands/    hand-shape close-ups, frames from the "Learn Asamyuta
 *                             Hasta" video lesson by Kalavenue (Arts venue), CC BY 3.0
 *   - public/images/dancers/  stage photographs by Suyash Dwivedi, CC BY-SA 4.0
 *
 * The catalogue name and its cited knowledge are loaded from the backend at runtime.
 * This file contains visual asset metadata only; it is not a second mudra catalogue.
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
    id: "mudra_pataka",
    accent: "70 120 255",
    slot: "mudra1",
    src: "/images/hands/pataka.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("02", "50% 30%"),
  },
  {
    id: "mudra_tripataka",
    aiPosition: "30% 30%",
    accent: "255 90 170",
    slot: "mudra2",
    src: "/images/hands/tripataka.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("04", "50% 30%"),
  },
  {
    id: "mudra_mushti",
    accent: "220 50 50",
    slot: "mudra3",
    src: "/images/hands/mushti.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("07", "50% 30%"),
  },
  {
    id: "mudra_kapitha",
    aiPosition: "25% 30%",
    accent: "40 190 160",
    slot: "mudra4",
    src: "/images/hands/kapittha.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("09", "50% 30%"),
  },
  {
    id: "mudra_allapadma",
    accent: "255 170 200",
    aiPosition: "22% 35%",
    slot: "mudra5",
    src: "/images/hands/alapadma.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("10", "50% 30%"),
  },
  {
    id: "mudra_hamsasya",
    accent: "235 235 255",
    slot: "mudra6",
    src: "/images/hands/hamsasya.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("05", "42% 50%"),
  },
  {
    id: "mudra_mayura",
    aiPosition: "50% 20%",
    accent: "110 90 255",
    slot: "mudra7",
    src: "/images/hands/mayura.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("13", "50% 50%"),
  },
  {
    id: "mudra_shikhara",
    accent: "255 150 40",
    aiPosition: "40% 30%",
    slot: "mudra8",
    src: "/images/hands/shikhara.jpg",
    page: HAND_PAGE,
    artist: ARTIST,
    license: HAND_LICENSE,
    dancer: stage("11", "82% 50%"),
  },
];
