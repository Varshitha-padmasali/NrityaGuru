/**
 * Camera + recorder hook tests with fake browser APIs.
 * jsdom has no camera or MediaRecorder, so we provide small fakes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useCamera } from "@/hooks/useCamera";
import { useMediaRecorder } from "@/hooks/useMediaRecorder";

function fakeStream() {
  const track = { stop: vi.fn(), addEventListener: vi.fn() };
  return {
    active: true,
    getTracks: () => [track],
    getVideoTracks: () => [track],
    track,
  } as unknown as MediaStream & { track: typeof track };
}

class FakeMediaRecorder {
  static isTypeSupported = vi.fn((t: string) => t === "video/webm");
  static instances: FakeMediaRecorder[] = [];
  static nextChunkSize = 1000;
  state: "inactive" | "recording" = "inactive";
  mimeType: string;
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(_stream: MediaStream, options?: { mimeType?: string }) {
    this.mimeType = options?.mimeType ?? "";
    FakeMediaRecorder.instances.push(this);
  }
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    const size = FakeMediaRecorder.nextChunkSize;
    if (size > 0) this.ondataavailable?.({ data: new Blob([new Uint8Array(size)], { type: this.mimeType }) });
    this.onstop?.();
  }
}

beforeEach(() => {
  FakeMediaRecorder.instances = [];
  FakeMediaRecorder.nextChunkSize = 1000;
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:fake"), revokeObjectURL: vi.fn() }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  // @ts-expect-error -- remove the fake between tests
  delete navigator.mediaDevices;
});

function setGetUserMedia(impl: () => Promise<MediaStream>) {
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia: vi.fn(impl) }, configurable: true });
}

describe("useCamera", () => {
  it("starts the camera and stops all tracks on unmount", async () => {
    const stream = fakeStream();
    setGetUserMedia(() => Promise.resolve(stream));
    const { result, unmount } = renderHook(() => useCamera());
    expect(result.current.status).toBe("idle"); // nothing requested until start()
    await act(() => result.current.start());
    expect(result.current.status).toBe("ready");
    expect(result.current.stream).toBe(stream);
    unmount();
    expect(stream.track.stop).toHaveBeenCalled();
  });

  it("reports permission denial", async () => {
    setGetUserMedia(() => Promise.reject(new DOMException("denied", "NotAllowedError")));
    const { result } = renderHook(() => useCamera());
    await act(() => result.current.start());
    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/permission was denied/i);
  });

  it("reports a missing camera", async () => {
    setGetUserMedia(() => Promise.reject(new DOMException("none", "NotFoundError")));
    const { result } = renderHook(() => useCamera());
    await act(() => result.current.start());
    expect(result.current.error).toMatch(/no camera was found/i);
  });

  it("reports an unsupported browser", async () => {
    const { result } = renderHook(() => useCamera()); // no navigator.mediaDevices
    await act(() => result.current.start());
    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/cannot record video/i);
  });

  it("stops a stream that arrives after unmount", async () => {
    const stream = fakeStream();
    let resolve!: (s: MediaStream) => void;
    setGetUserMedia(() => new Promise((r) => (resolve = r)));
    const { result, unmount } = renderHook(() => useCamera());
    let pending!: Promise<unknown>;
    act(() => {
      pending = result.current.start();
    });
    unmount();
    resolve(stream);
    await pending;
    expect(stream.track.stop).toHaveBeenCalled();
  });
});

describe("useMediaRecorder", () => {
  const options = { maxSeconds: 8, maxBytes: 10_000, minMs: 0 };

  it("records, selects a supported MIME type and produces an object URL", () => {
    const { result } = renderHook(() => useMediaRecorder(options));
    act(() => {
      result.current.start(fakeStream());
    });
    expect(result.current.status).toBe("recording");
    expect(FakeMediaRecorder.instances[0].mimeType).toBe("video/webm");
    act(() => result.current.stop());
    expect(result.current.status).toBe("recorded");
    expect(result.current.recording?.url).toBe("blob:fake");
    expect(result.current.recording?.sizeBytes).toBe(1000);
  });

  it("refuses to start twice", () => {
    const { result } = renderHook(() => useMediaRecorder(options));
    let second = true;
    act(() => {
      result.current.start(fakeStream());
      second = result.current.start(fakeStream());
    });
    expect(second).toBe(false);
    expect(FakeMediaRecorder.instances).toHaveLength(1);
  });

  it("reports an empty recording", () => {
    FakeMediaRecorder.nextChunkSize = 0;
    const { result } = renderHook(() => useMediaRecorder(options));
    act(() => {
      result.current.start(fakeStream());
    });
    act(() => result.current.stop());
    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/recording was empty/i);
  });

  it("rejects recordings over the size limit", () => {
    FakeMediaRecorder.nextChunkSize = 20_000;
    const { result } = renderHook(() => useMediaRecorder(options));
    act(() => {
      result.current.start(fakeStream());
    });
    act(() => result.current.stop());
    expect(result.current.error).toMatch(/larger than the upload limit/i);
  });

  it("stops automatically at the time limit", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useMediaRecorder({ ...options, maxSeconds: 3 }));
    act(() => {
      result.current.start(fakeStream());
    });
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(result.current.status).toBe("recorded");
  });

  it("revokes the object URL on retake (reset) and on unmount", () => {
    const { result, unmount } = renderHook(() => useMediaRecorder(options));
    act(() => {
      result.current.start(fakeStream());
    });
    act(() => result.current.stop());
    act(() => result.current.reset());
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:fake");
    expect(result.current.recording).toBeNull();

    act(() => {
      result.current.start(fakeStream());
    });
    act(() => result.current.stop());
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
  });
});
