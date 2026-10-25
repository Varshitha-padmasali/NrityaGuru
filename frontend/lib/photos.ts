/**
 * Decorative photography (home page only). See lib/photos.json for sources and licences.
 * These are atmosphere, NOT mudra reference images — reference images always come
 * from the curated knowledge base via the backend.
 */
import data from "./photos.json";

export type PhotoKey = keyof typeof data.photos;
type Provider = "pexels" | "unsplash";

export interface PhotoInfo {
  key: PhotoKey;
  alt: string;
  photographer: string;
  photoPage: string;
  providerName: "Pexels" | "Unsplash";
  /** CDN URL, cropped server-side to the requested size. */
  remoteUrl: (width: number, height: number) => string;
  /** Copy saved by `npm run photos:download` (used when offline). */
  localUrl: string;
  /** Set when an AI image was generated for this slot (npm run images:generate or /studio). */
  generated: { src: string; model: string; createdAt: string } | null;
}

/** Shared with scripts/download-photos.mjs (keep the two in sync). */
export function cdnUrl(provider: Provider, id: string, w: number, h: number): string {
  if (provider === "pexels") {
    return `https://images.pexels.com/photos/${id}/pexels-photo-${id}.jpeg?auto=compress&cs=tinysrgb&fit=crop&w=${w}&h=${h}`;
  }
  // crop=faces keeps the dancer's face in frame when Unsplash crops to our shape.
  return `https://images.unsplash.com/${id}?auto=format&fit=crop&crop=faces,center&w=${w}&h=${h}&q=80`;
}

export function getPhoto(key: PhotoKey): PhotoInfo {
  const p = data.photos[key];
  const provider = p.provider as Provider;
  return {
    key,
    alt: p.alt,
    photographer: p.photographer,
    photoPage: p.photoPage,
    providerName: provider === "pexels" ? "Pexels" : "Unsplash",
    remoteUrl: (w, h) => cdnUrl(provider, p.id, w, h),
    localUrl: `/images/photos/${key}.jpg`,
    generated: (p.generated as PhotoInfo["generated"]) ?? null,
  };
}
