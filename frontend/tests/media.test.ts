import { describe, expect, it } from "vitest";
import { describeCameraError, extensionForMimeType, formatDuration, pickRecordingMimeType } from "@/lib/media";

describe("pickRecordingMimeType", () => {
  it("prefers VP9 WebM when the browser supports it (Chrome/Edge)", () => {
    expect(pickRecordingMimeType(() => true)).toBe("video/webm;codecs=vp9");
  });

  it("falls back to MP4 when only MP4 is supported (Safari)", () => {
    expect(pickRecordingMimeType((t) => t.startsWith("video/mp4"))).toBe("video/mp4;codecs=avc1");
  });

  it("returns empty string (browser default) when nothing is reported as supported", () => {
    expect(pickRecordingMimeType(() => false)).toBe("");
  });

  it("treats a throwing isTypeSupported as unsupported", () => {
    expect(
      pickRecordingMimeType((t) => {
        if (t.includes("vp9")) throw new Error("boom");
        return t === "video/webm;codecs=vp8";
      }),
    ).toBe("video/webm;codecs=vp8");
  });
});

describe("describeCameraError", () => {
  const err = (name: string) => new DOMException("x", name);

  it("explains permission denial", () => {
    expect(describeCameraError(err("NotAllowedError"))).toMatch(/permission was denied/i);
  });
  it("explains a missing camera", () => {
    expect(describeCameraError(err("NotFoundError"))).toMatch(/no camera was found/i);
  });
  it("explains a camera already in use", () => {
    expect(describeCameraError(err("NotReadableError"))).toMatch(/another app/i);
  });
  it("has a generic fallback", () => {
    expect(describeCameraError(new Error("weird"))).toMatch(/could not be started/i);
  });
});

describe("formatting helpers", () => {
  it("formats durations", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(4200)).toBe("0:04");
    expect(formatDuration(65_000)).toBe("1:05");
  });
  it("maps MIME types to file extensions", () => {
    expect(extensionForMimeType("video/webm;codecs=vp9")).toBe("webm");
    expect(extensionForMimeType("video/mp4")).toBe("mp4");
  });
});
