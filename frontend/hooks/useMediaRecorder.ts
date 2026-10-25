"use client";

/**
 * useMediaRecorder — records a MediaStream into a single video Blob.
 *
 * Key decisions:
 * - The MIME type is chosen with MediaRecorder.isTypeSupported().
 * - Chunks, the recorder and the timer live in refs, not state, so the
 *   recorder's event callbacks never see stale values.
 * - Recording stops automatically at maxSeconds.
 * - The finished recording is kept only in memory (Blob + temporary object
 *   URL). The object URL is revoked on retake, reset and unmount. Nothing is
 *   written to localStorage/IndexedDB.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { pickRecordingMimeType } from "@/lib/media";

export type RecorderStatus = "idle" | "recording" | "recorded" | "error";

export interface Recording {
  blob: Blob;
  url: string;
  mimeType: string;
  durationMs: number;
  sizeBytes: number;
}

export interface UseMediaRecorderOptions {
  maxSeconds: number;
  maxBytes: number;
  /** Ignore clips shorter than this (accidental clicks). */
  minMs?: number;
}

export interface UseMediaRecorderResult {
  status: RecorderStatus;
  elapsedMs: number;
  recording: Recording | null;
  error: string | null;
  start: (stream: MediaStream) => boolean;
  stop: () => void;
  reset: () => void;
}

export function useMediaRecorder({ maxSeconds, maxBytes, minMs = 1000 }: UseMediaRecorderOptions): UseMediaRecorderResult {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const urlRef = useRef<string | null>(null);
  const discardRef = useRef(false); // true when stopping because of reset/unmount

  const clearTimers = useCallback(() => {
    if (tickRef.current) clearInterval(tickRef.current);
    if (autoStopRef.current) clearTimeout(autoStopRef.current);
    tickRef.current = null;
    autoStopRef.current = null;
  }, []);

  const revokeUrl = useCallback(() => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  }, []);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop(); // onstop builds the Blob
    clearTimers();
  }, [clearTimers]);

  const start = useCallback(
    (stream: MediaStream) => {
      if (recorderRef.current && recorderRef.current.state !== "inactive") return false; // no double start
      if (!stream.active) {
        setError("The camera is not active. Start the camera and try again.");
        setStatus("error");
        return false;
      }

      revokeUrl();
      setRecording(null);
      setError(null);
      chunksRef.current = [];
      discardRef.current = false;

      const mimeType = pickRecordingMimeType((t) => MediaRecorder.isTypeSupported(t));
      let recorder: MediaRecorder;
      try {
        recorder = new MediaRecorder(stream, mimeType ? { mimeType, videoBitsPerSecond: 2_500_000 } : undefined);
      } catch {
        setError("This browser could not start recording. Try Chrome or Edge.");
        setStatus("error");
        return false;
      }

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        clearTimers();
        setError("Recording failed. Please try again.");
        setStatus("error");
      };
      recorder.onstop = () => {
        clearTimers();
        recorderRef.current = null;
        if (discardRef.current) {
          chunksRef.current = [];
          return;
        }
        const durationMs = Date.now() - startedAtRef.current;
        const type = recorder.mimeType || mimeType || "video/webm";
        const blob = new Blob(chunksRef.current, { type });
        chunksRef.current = [];

        if (blob.size === 0) {
          setError("The recording was empty. Check that your camera preview is visible and record again.");
          setStatus("error");
          return;
        }
        if (durationMs < minMs) {
          setError("That recording was too short. Hold the mudra and record for at least a second.");
          setStatus("error");
          return;
        }
        if (blob.size > maxBytes) {
          setError("The recording is larger than the upload limit. Record a shorter clip.");
          setStatus("error");
          return;
        }
        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        setRecording({ blob, url, mimeType: type, durationMs, sizeBytes: blob.size });
        setStatus("recorded");
      };

      recorderRef.current = recorder;
      startedAtRef.current = Date.now();
      setElapsedMs(0);
      recorder.start(250); // emit a chunk every 250 ms so a crash loses little
      setStatus("recording");

      tickRef.current = setInterval(() => setElapsedMs(Date.now() - startedAtRef.current), 200);
      autoStopRef.current = setTimeout(() => {
        const r = recorderRef.current;
        if (r && r.state !== "inactive") r.stop();
      }, maxSeconds * 1000);
      return true;
    },
    [clearTimers, maxBytes, maxSeconds, minMs, revokeUrl],
  );

  const reset = useCallback(() => {
    discardRef.current = true;
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
    recorderRef.current = null;
    clearTimers();
    revokeUrl();
    chunksRef.current = [];
    setRecording(null);
    setError(null);
    setElapsedMs(0);
    setStatus("idle");
  }, [clearTimers, revokeUrl]);

  useEffect(() => {
    return () => {
      discardRef.current = true;
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      recorderRef.current = null;
      clearTimers();
      revokeUrl();
      chunksRef.current = [];
      setRecording(null);
      setStatus("idle");
    };
  }, [clearTimers, revokeUrl]);

  return { status, elapsedMs, recording, error, start, stop, reset };
}
