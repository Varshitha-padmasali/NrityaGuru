"use client";

/**
 * useCamera — owns the webcam MediaStream.
 *
 * - Nothing happens until start() is called (camera is only requested after
 *   the learner clicks a button).
 * - stop() and component cleanup stop every track, so the camera light turns
 *   off when the learner leaves the practice page.
 * - If the component goes away while the permission prompt is still open, the
 *   stream that arrives later is stopped immediately instead of leaking.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { checkCameraSupport, describeCameraError, messageForSupport, stopStream } from "@/lib/media";

export type CameraStatus = "idle" | "requesting" | "ready" | "error";

export interface UseCameraResult {
  status: CameraStatus;
  stream: MediaStream | null;
  error: string | null;
  start: () => Promise<MediaStream | null>;
  stop: () => void;
}

const VIDEO_CONSTRAINTS: MediaStreamConstraints = {
  audio: false, // evaluation only uses video; never record the learner's audio
  video: {
    facingMode: "user",
    width: { ideal: 1280 },
    height: { ideal: 720 },
    frameRate: { ideal: 30 },
  },
};

export function useCamera(): UseCameraResult {
  const [status, setStatus] = useState<CameraStatus>("idle");
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  // Increments on every start/stop; a getUserMedia result from an older request is discarded.
  const requestIdRef = useRef(0);

  const stop = useCallback(() => {
    requestIdRef.current += 1;
    stopStream(streamRef.current);
    streamRef.current = null;
    setStream(null);
    setStatus("idle");
  }, []);

  const start = useCallback(async () => {
    if (streamRef.current) return streamRef.current; // already running

    const supportMessage = messageForSupport(checkCameraSupport());
    if (supportMessage) {
      setError(supportMessage);
      setStatus("error");
      return null;
    }

    const requestId = ++requestIdRef.current;
    setStatus("requesting");
    setError(null);
    try {
      const media = await navigator.mediaDevices.getUserMedia(VIDEO_CONSTRAINTS);
      if (requestId !== requestIdRef.current) {
        stopStream(media); // stopped or unmounted while we were waiting
        return null;
      }
      // If the camera is unplugged or revoked mid-session, reflect that.
      media.getVideoTracks().forEach((track) => {
        track.addEventListener("ended", () => {
          if (streamRef.current === media) {
            streamRef.current = null;
            setStream(null);
            setError("The camera stopped unexpectedly. Check the connection and start the camera again.");
            setStatus("error");
          }
        });
      });
      streamRef.current = media;
      setStream(media);
      setStatus("ready");
      return media;
    } catch (err) {
      if (requestId !== requestIdRef.current) return null;
      setError(describeCameraError(err));
      setStatus("error");
      return null;
    }
  }, []);

  // Cleanup when the component unmounts or its route is hidden.
  useEffect(() => {
    return () => {
      requestIdRef.current += 1;
      stopStream(streamRef.current);
      streamRef.current = null;
      setStream(null);
      setStatus("idle");
    };
  }, []);

  return { status, stream, error, start, stop };
}
