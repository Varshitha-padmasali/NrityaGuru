/**
 * Gemini image generation — SERVER SIDE ONLY.
 *
 * Used by:
 *   - scripts/generate-images.mjs   (npm run images:generate)
 *   - app/api/studio/generate/route.ts  (the /studio page, development only)
 *
 * The API key is read from GEMINI_API_KEY (in .env.local). It never reaches the
 * browser: do NOT rename it to NEXT_PUBLIC_GEMINI_API_KEY.
 *
 * Images are saved to public/images/generated/<slot>.jpg and recorded in
 * lib/photos.json under `generated`, so the site shows them automatically.
 */
import { GoogleGenAI } from "@google/genai";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export const DEFAULT_IMAGE_MODEL = "gemini-nano-banana-2.1";

/** @param {string} root project root (the frontend folder) */
export function paths(root) {
  return {
    prompts: path.join(root, "lib/image-prompts.json"),
    photos: path.join(root, "lib/photos.json"),
    outDir: path.join(root, "public/images/generated"),
  };
}

/** Minimal .env.local reader so the CLI script works without extra packages. */
export async function loadEnvFile(root) {
  for (const name of [".env.local", ".env"]) {
    try {
      const text = await readFile(path.join(root, name), "utf8");
      for (const line of text.split(/\r?\n/)) {
        const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
        if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
      }
    } catch {
      /* file not present */
    }
  }
}

/** @returns {Promise<{style: string, slots: Record<string, {aspectRatio: string, imageSize: string, prompt: string}>}>} */
export async function readPrompts(root) {
  return JSON.parse(await readFile(paths(root).prompts, "utf8"));
}

export function buildPrompt(style, slotPrompt, character, hasReference = false) {
  const parts = [slotPrompt];
  if (character) parts.push(character);
  if (hasReference) {
    parts.push(
      "Use the attached reference image to keep the SAME dancer: identical face, skin tone, hairstyle, costume colours, jewellery, stage and lighting. Only the pose and expression change.",
    );
  }
  parts.push(style);
  return parts.join("\n\n");
}

/**
 * Generate one image and return its bytes.
 * Tries the current Interactions API first, then falls back to the older
 * generateContent API (useful if Google renames things again).
 */
export async function generateImageBytes({ apiKey, model, prompt, aspectRatio, imageSize, reference = null }) {
  if (!apiKey) throw new Error("GEMINI_API_KEY is not set. Add it to frontend/.env.local (see .env.example).");
  const ai = new GoogleGenAI({ apiKey });

  let firstError;
  if (ai.interactions?.create) {
    try {
      const interaction = await ai.interactions.create({
        model,
        input: reference
          ? [
              { type: "image", data: reference.bytes.toString("base64"), mime_type: reference.mimeType },
              { type: "text", text: prompt },
            ]
          : prompt,
        response_format: { type: "image", mime_type: "image/jpeg", aspect_ratio: aspectRatio, image_size: imageSize },
      });
      const image = interaction.output_image;
      if (image?.data) return { bytes: Buffer.from(image.data, "base64"), mimeType: image.mime_type ?? "image/jpeg" };
      firstError = new Error("The model returned no image (it may have declined the prompt). Try rewording it.");
    } catch (err) {
      firstError = err;
    }
  }

  // Fallback: generateContent with image output.
  try {
    const response = await ai.models.generateContent({
      model,
      contents: reference
        ? [{ role: "user", parts: [{ inlineData: { data: reference.bytes.toString("base64"), mimeType: reference.mimeType } }, { text: prompt }] }]
        : prompt,
      config: { responseModalities: ["IMAGE"], imageConfig: { aspectRatio, imageSize } },
    });
    const part = response.candidates?.[0]?.content?.parts?.find((p) => p.inlineData?.data);
    if (part) return { bytes: Buffer.from(part.inlineData.data, "base64"), mimeType: part.inlineData.mimeType ?? "image/png" };
  } catch (err) {
    throw new Error(`Gemini image generation failed: ${describe(firstError ?? err)}`);
  }
  throw new Error(`Gemini image generation failed: ${describe(firstError) || "no image returned"}`);
}

function describe(err) {
  if (!err) return "";
  const msg = err.message ?? String(err);
  if (/API key not valid|API_KEY_INVALID|401|403/i.test(msg)) return "the API key was rejected — check GEMINI_API_KEY.";
  if (/not found|404/i.test(msg)) return `model not found — check GEMINI_IMAGE_MODEL (${msg}).`;
  if (/quota|429|RESOURCE_EXHAUSTED/i.test(msg)) return "quota or rate limit reached — wait a minute, or check billing for image models.";
  return msg;
}

/**
 * Generate a slot's image, save it, and record it in lib/photos.json.
 * @returns {Promise<{slot: string, src: string, model: string, bytes: number, usedReference: boolean}>}
 */
export async function generateSlot(root, slot, { model, apiKey, promptOverride } = {}) {
  const prompts = await readPrompts(root);
  const { style, character, slots } = prompts;
  const config = slots[slot];
  if (!config) throw new Error(`Unknown image slot "${slot}". Known: ${Object.keys(slots).join(", ")}`);

  // A slot can name its own character text (e.g. "mudraCharacter"); otherwise `character: true` uses the shared one.
  const characterText = config.characterKey ? prompts[config.characterKey] : config.character ? character : null;

  // Consistency: if this slot names a reference slot that has been generated, send that image too.
  const reference = config.reference ? await readGeneratedImage(root, config.reference) : null;

  const usedModel = model || process.env.GEMINI_IMAGE_MODEL || DEFAULT_IMAGE_MODEL;
  const { bytes, mimeType } = await generateImageBytes({
    apiKey: apiKey ?? process.env.GEMINI_API_KEY,
    model: usedModel,
    prompt: buildPrompt(style, promptOverride || config.prompt, characterText, Boolean(reference)),
    aspectRatio: config.aspectRatio,
    imageSize: config.imageSize,
    reference,
  });

  const ext = mimeType.includes("png") ? "png" : mimeType.includes("webp") ? "webp" : "jpg";
  const { outDir, photos } = paths(root);
  await mkdir(outDir, { recursive: true });
  const fileName = `${slot}.${ext}`;
  await writeFile(path.join(outDir, fileName), bytes);

  // Version query string so the browser doesn't show a cached older image.
  const createdAt = new Date().toISOString();
  const src = `/images/generated/${fileName}?v=${Date.parse(createdAt)}`;
  const data = JSON.parse(await readFile(photos, "utf8"));
  if (data.photos[slot]) {
    data.photos[slot].generated = { src, model: usedModel, createdAt };
    await writeFile(photos, `${JSON.stringify(data, null, 2)}\n`);
  }
  return { slot, src, model: usedModel, bytes: bytes.length, usedReference: Boolean(reference) };
}

/** Bytes of a slot's generated image, or null if it hasn't been generated. */
export async function readGeneratedImage(root, slot) {
  const data = JSON.parse(await readFile(paths(root).photos, "utf8"));
  const src = data.photos[slot]?.generated?.src;
  if (!src) return null;
  const file = path.join(root, "public", src.split("?")[0]);
  try {
    const bytes = await readFile(file);
    const mimeType = file.endsWith(".png") ? "image/png" : file.endsWith(".webp") ? "image/webp" : "image/jpeg";
    return { bytes, mimeType };
  } catch {
    return null;
  }
}

/** Remove a slot's generated image from use (the stock photo is shown again). */
export async function clearSlot(root, slot) {
  const { photos } = paths(root);
  const data = JSON.parse(await readFile(photos, "utf8"));
  if (data.photos[slot]) {
    data.photos[slot].generated = null;
    await writeFile(photos, `${JSON.stringify(data, null, 2)}\n`);
  }
}
