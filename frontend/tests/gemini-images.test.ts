/**
 * Tests the Gemini image pipeline with a mocked SDK (no network, no API key):
 * request shape, saving the file, updating lib/photos.json, fallback API, errors.
 * @vitest-environment node
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cp, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const interactionsCreate = vi.fn();
const generateContent = vi.fn();
vi.mock("@google/genai", () => ({
  GoogleGenAI: class {
    interactions = { create: interactionsCreate };
    models = { generateContent };
  },
}));

const { generateSlot, clearSlot, generateImageBytes, DEFAULT_IMAGE_MODEL } = await import("@/lib/server/gemini-images.mjs");

const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3]).toString("base64");
let root: string;

beforeEach(async () => {
  root = await mkdtemp(path.join(tmpdir(), "ng-"));
  await cp(path.join(process.cwd(), "lib"), path.join(root, "lib"), { recursive: true });
  interactionsCreate.mockReset();
  generateContent.mockReset();
});
afterEach(() => rm(root, { recursive: true, force: true }));

describe("generateSlot", () => {
  it("calls the Interactions API with the slot's prompt and format, saves the image and records it", async () => {
    interactionsCreate.mockResolvedValue({ output_image: { type: "image", data: JPEG, mime_type: "image/jpeg" } });

    const result = await generateSlot(root, "seq1", { apiKey: "test-key" });

    const req = interactionsCreate.mock.calls[0][0];
    expect(req.model).toBe(DEFAULT_IMAGE_MODEL);
    expect(req.input).toMatch(/Pushpanjali/);
    expect(req.input).toMatch(/same dancer in every frame/i); // character description
    expect(req.input).toMatch(/fictional adult/); // shared style is appended
    expect(req.response_format).toEqual({ type: "image", mime_type: "image/jpeg", aspect_ratio: "16:9", image_size: "2K" });
    expect(result.usedReference).toBe(false);

    const saved = await readFile(path.join(root, "public/images/generated/seq1.jpg"));
    expect(saved.toString("base64")).toBe(JPEG);

    const photos = JSON.parse(await readFile(path.join(root, "lib/photos.json"), "utf8")).photos;
    expect(photos.seq1.generated.src).toBe(result.src);
    expect(photos.seq1.generated.src).toMatch(/^\/images\/generated\/seq1\.jpg\?v=\d+$/);
    expect(photos.seq2.generated).toBeNull(); // other slots untouched
  });

  it("sends seq1 as a reference image so later frames show the same dancer", async () => {
    interactionsCreate.mockResolvedValue({ output_image: { type: "image", data: JPEG, mime_type: "image/jpeg" } });
    await generateSlot(root, "seq1", { apiKey: "k" });
    const result = await generateSlot(root, "seq5", { apiKey: "k" });

    const input = interactionsCreate.mock.calls[1][0].input;
    expect(Array.isArray(input)).toBe(true);
    expect(input[0]).toEqual({ type: "image", data: JPEG, mime_type: "image/jpeg" });
    expect(input[1].type).toBe("text");
    expect(input[1].text).toMatch(/Varnam/);
    expect(input[1].text).toMatch(/reference image to keep the SAME dancer/);
    expect(result.usedReference).toBe(true);
  });

  it("uses an edited prompt when given", async () => {
    interactionsCreate.mockResolvedValue({ output_image: { type: "image", data: JPEG } });
    await generateSlot(root, "blackPortrait", { apiKey: "k", promptOverride: "Custom prompt here" });
    expect(interactionsCreate.mock.calls[0][0].input).toMatch(/^Custom prompt here/);
  });

  it("falls back to generateContent if the Interactions API fails", async () => {
    interactionsCreate.mockRejectedValue(new Error("interactions unavailable"));
    generateContent.mockResolvedValue({ candidates: [{ content: { parts: [{ inlineData: { data: JPEG, mimeType: "image/png" } }] } }] });
    const result = await generateSlot(root, "shloka", { apiKey: "k" });
    expect(generateContent.mock.calls[0][0].config).toEqual({ responseModalities: ["IMAGE"], imageConfig: { aspectRatio: "4:5", imageSize: "1K" } });
    expect(result.src).toMatch(/shloka\.png/);
  });

  it("explains a rejected API key", async () => {
    interactionsCreate.mockRejectedValue(new Error("API key not valid"));
    generateContent.mockRejectedValue(new Error("API key not valid"));
    await expect(generateSlot(root, "seq1", { apiKey: "bad" })).rejects.toThrow(/API key was rejected/);
  });

  it("rejects unknown slots and a missing key", async () => {
    await expect(generateSlot(root, "nope", { apiKey: "k" })).rejects.toThrow(/Unknown image slot/);
    await expect(generateImageBytes({ apiKey: "", model: "m", prompt: "p", aspectRatio: "1:1", imageSize: "1K" })).rejects.toThrow(/GEMINI_API_KEY/);
  });

  it("clearSlot returns a slot to the stock photo", async () => {
    interactionsCreate.mockResolvedValue({ output_image: { type: "image", data: JPEG } });
    await generateSlot(root, "seq1", { apiKey: "k" });
    await clearSlot(root, "seq1");
    const photos = JSON.parse(await readFile(path.join(root, "lib/photos.json"), "utf8")).photos;
    expect(photos.seq1.generated).toBeNull();
  });
});
