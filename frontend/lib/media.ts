/**
 * Pure helpers for camera and recording. Kept free of React so they can be
 * unit-tested without a browser.
 */

/**
 * Preferred recording formats, best first. Chrome/Edge/Firefox record WebM;
 * Safari records MP4. We ask the browser which it supports instead of
 * assuming.
 */
export const PREFERRED_MIME_TYPES = [
  "video/webm;codecs=vp9",
  "video/webm;codecs=vp8",
  "video/webm",
  "video/mp4;codecs=avc1",
  "video/mp4",
] as const;

/**
 * Pick the first supported MIME type. Returns "" when none are reported as
 * supported, which tells MediaRecorder to use the browser default.
 * `isSupported` is injectable for tests; in the browser pass
 * MediaRecorder.isTypeSupported.
 */
export function pickRecordingMimeType(isSupported: (type: string) => boolean): string {
  for (const type of PREFERRED_MIME_TYPES) {
    try {
      if (isSupported(type)) return type;
    } catch {
      // Some browsers throw for unknown types; treat as unsupported.
    }
  }
  return "";
}

export function extensionForMimeType(mimeType: string): string {
  if (mimeType.includes("mp4")) return "mp4";
  if (mimeType.includes("webm")) return "webm";
  return "bin";
}

export type CameraSupport = "supported" | "insecure_context" | "unsupported";

/** getUserMedia only exists on HTTPS pages or http://localhost. */
export function checkCameraSupport(): CameraSupport {
  if (typeof window === "undefined") return "unsupported";
  if (!window.isSecureContext) return "insecure_context";
  if (!navigator.mediaDevices?.getUserMedia) return "unsupported";
  if (typeof window.MediaRecorder === "undefined") return "unsupported";
  return "supported";
}

/** Translate getUserMedia errors (DOMException names) into learner-friendly text. */
export function describeCameraError(error: unknown): string {
  const name = error instanceof DOMException || error instanceof Error ? error.name : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera permission was denied. Allow camera access in your browser's address bar (the camera icon), then try again.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No camera was found. Connect a webcam and try again.";
    case "NotReadableError":
    case "AbortError":
      return "Your camera is being used by another app (for example a video call). Close it and try again.";
    default:
      return "The camera could not be started. Refresh the page and try again.";
  }
}

export function messageForSupport(support: CameraSupport): string | null {
  if (support === "insecure_context") return "Camera access needs a secure page. Open the app on http://localhost or over HTTPS.";
  if (support === "unsupported") return "This browser cannot record video. Please use a recent version of Chrome, Edge, Firefox or Safari.";
  return null;
}

/** 4200 → "0:04" */
export function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Stop every track so the camera light turns off. */
export function stopStream(stream: MediaStream | null | undefined): void {
  stream?.getTracks().forEach((track) => track.stop());
}
