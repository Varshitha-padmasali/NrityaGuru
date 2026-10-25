/**
 * Image Studio API — DEVELOPMENT ONLY.
 *
 * Runs on the Next.js server (never in the browser), so GEMINI_API_KEY from
 * .env.local stays secret. Disabled in production builds so nobody can spend
 * your Gemini quota through a deployed site.
 *
 * POST { action: "list" }                         → slots, prompts, current images
 * POST { action: "generate", slot, prompt? }      → generate + save one image
 * POST { action: "clear", slot }                  → go back to the stock photo
 *
 * (POST only: with Next.js cache components a GET handler can be prerendered.)
 */
import { NextResponse } from "next/server";
import { clearSlot, DEFAULT_IMAGE_MODEL, generateSlot, readPrompts } from "@/lib/server/gemini-images.mjs";
import { readFile } from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();

type Body = { action?: string; slot?: string; prompt?: string };

export async function POST(request: Request) {
  if (process.env.NODE_ENV === "production") {
    return NextResponse.json({ detail: "The Image Studio is only available in development." }, { status: 404 });
  }

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body." }, { status: 400 });
  }

  try {
    if (body.action === "list") {
      const prompts = await readPrompts(ROOT);
      const photos = JSON.parse(await readFile(path.join(ROOT, "lib/photos.json"), "utf8")).photos;
      return NextResponse.json({
        keyConfigured: Boolean(process.env.GEMINI_API_KEY),
        model: process.env.GEMINI_IMAGE_MODEL || DEFAULT_IMAGE_MODEL,
        style: prompts.style,
        slots: Object.entries(prompts.slots).map(([slot, cfg]) => ({
          slot,
          ...(cfg as object),
          generated: photos[slot]?.generated ?? null,
        })),
      });
    }

    if (body.action === "generate") {
      if (!body.slot) return NextResponse.json({ detail: "slot is required." }, { status: 422 });
      if (!process.env.GEMINI_API_KEY) {
        return NextResponse.json({ detail: "GEMINI_API_KEY is not set in frontend/.env.local. Add it and restart npm run dev." }, { status: 503 });
      }
      const prompt = typeof body.prompt === "string" && body.prompt.trim() ? body.prompt.trim().slice(0, 2000) : undefined;
      const result = await generateSlot(ROOT, body.slot, { promptOverride: prompt });
      return NextResponse.json(result);
    }

    if (body.action === "clear") {
      if (!body.slot) return NextResponse.json({ detail: "slot is required." }, { status: 422 });
      await clearSlot(ROOT, body.slot);
      return NextResponse.json({ slot: body.slot, cleared: true });
    }

    return NextResponse.json({ detail: "Unknown action." }, { status: 422 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Image generation failed.";
    return NextResponse.json({ detail: message }, { status: 502 });
  }
}
