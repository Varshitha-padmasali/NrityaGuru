#!/usr/bin/env node
/**
 * Saves the home-page photos into public/images/photos/ so the site still
 * shows them without internet (e.g. during a viva in a lab with no Wi-Fi).
 *
 *   npm run photos:download
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const { photos } = JSON.parse(await readFile(path.join(root, "lib/photos.json"), "utf8"));
const outDir = path.join(root, "public/images/photos");
await mkdir(outDir, { recursive: true });

// Same URL builder as cdnUrl() in lib/photos.ts. Saved at a size large enough for every slot.
const url = ({ provider, id }, w, h) =>
  provider === "pexels"
    ? `https://images.pexels.com/photos/${id}/pexels-photo-${id}.jpeg?auto=compress&cs=tinysrgb&fit=crop&w=${w}&h=${h}`
    : `https://images.unsplash.com/${id}?auto=format&fit=crop&crop=faces,center&w=${w}&h=${h}&q=80&fm=jpg`;

let failed = 0;
for (const [key, photo] of Object.entries(photos)) {
  try {
    const res = await fetch(url(photo, 1000, 1250));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    await writeFile(path.join(outDir, `${key}.jpg`), buf);
    console.log(`✓ ${key}.jpg  (${(buf.length / 1024).toFixed(0)} KB) — ${photo.photographer} / ${photo.provider}`);
  } catch (err) {
    failed += 1;
    console.error(`✗ ${key}: ${err.message}`);
  }
}
if (failed) {
  console.error(`\n${failed} photo(s) failed. Check your internet connection and run again.`);
  process.exit(1);
}
console.log("\nDone. Photos will now load from public/images/photos/ when offline.");
