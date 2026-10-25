#!/usr/bin/env node
/**
 * Generate the home-page images with Gemini.
 *
 *   npm run images:generate                 # every slot that has no image yet
 *   npm run images:generate -- --force      # regenerate every slot
 *   npm run images:generate -- hero shloka  # only these slots (always regenerated)
 *
 * Needs GEMINI_API_KEY in frontend/.env.local. Optional GEMINI_IMAGE_MODEL.
 * Prompts live in lib/image-prompts.json.
 */
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DEFAULT_IMAGE_MODEL, generateSlot, loadEnvFile, paths, readPrompts } from "../lib/server/gemini-images.mjs";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
await loadEnvFile(root);

const args = process.argv.slice(2);
const force = args.includes("--force");
const only = args.filter((a) => !a.startsWith("--"));

const { slots } = await readPrompts(root);
const photos = JSON.parse(await readFile(paths(root).photos, "utf8")).photos;
const targets = only.length ? only : Object.keys(slots).filter((s) => force || !photos[s]?.generated);

if (!process.env.GEMINI_API_KEY) {
  console.error("✗ GEMINI_API_KEY is missing. Add this line to frontend/.env.local:\n\n  GEMINI_API_KEY=your-key-from-aistudio.google.com\n");
  process.exit(1);
}
if (targets.length === 0) {
  console.log("All slots already have generated images. Use --force to regenerate, or name slots: npm run images:generate -- hero");
  process.exit(0);
}

const model = process.env.GEMINI_IMAGE_MODEL || DEFAULT_IMAGE_MODEL;
console.log(`Generating ${targets.length} image(s) with ${model}…\n`);
let failed = 0;
for (const slot of targets) {
  process.stdout.write(`• ${slot.padEnd(14)} `);
  try {
    const r = await generateSlot(root, slot, { model });
    console.log(`✓ ${(r.bytes / 1024).toFixed(0)} KB → public${r.src.split("?")[0]}${r.usedReference ? "  (same dancer as seq1)" : ""}`);
  } catch (err) {
    failed += 1;
    console.log(`✗ ${err.message}`);
  }
}
console.log(failed ? `\n${failed} failed. Fix the issue above and run again — finished images are kept.` : "\nDone. Restart or refresh `npm run dev` to see them.");
process.exit(failed ? 1 : 0);
