"use client";

/**
 * The practice workflow for one reference:
 * enable camera → record → review → retake or submit → upload → evaluate → results.
 *
 * - useCamera owns the webcam stream.
 * - useMediaRecorder owns the recording.
 * - practiceReducer decides which actions are allowed right now.
 * This component wires the three together and talks to the services.
 */
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useReducer, useRef } from "react";
import { useCamera } from "@/hooks/useCamera";
import { useMediaRecorder } from "@/hooks/useMediaRecorder";
import { useApiQuery } from "@/hooks/useApiQuery";
import { createPracticeSession, listPracticeReferences, uploadPracticeVideo } from "@/services/practice-service";
import { evaluateAndWait } from "@/services/evaluation-service";
import { config } from "@/lib/config";
import { formatBytes, formatDuration } from "@/lib/media";
import { ApiError, describeError } from "@/types/api";
import { CameraStage } from "@/components/camera/CameraStage";
import { MudraImage } from "@/components/mudras/MudraImage";
import { Badge } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState, Notice } from "@/components/ui/StatusStates";
import { IconAlert, IconArrowLeft, IconCamera, IconCheck, IconRecord, IconRefresh, IconStop, IconUpload } from "@/components/ui/Icons";
import { Spinner } from "@/components/ui/Spinner";
import { initialPracticeState, practiceReducer, type PracticePhase } from "./practiceMachine";

const TIPS = [
  "Stand about an arm's length from the camera so your hands stay in the frame.",
  "Face a window or lamp — avoid strong light behind you.",
  "Use a plain background and keep sleeves away from your wrists.",
  "Hold the mudra steadily at chest height before and after the movement.",
];

const STEPS: { key: string; label: string; phases: PracticePhase[] }[] = [
  { key: "camera", label: "Camera", phases: ["idle", "requesting_camera", "camera_ready"] },
  { key: "record", label: "Record", phases: ["recording"] },
  { key: "review", label: "Review", phases: ["recorded"] },
  { key: "evaluate", label: "Evaluate", phases: ["uploading", "processing", "completed"] },
];

export function PracticeFlow() {
  const { movementId } = useParams<{ movementId: string }>();
  const referenceId = Number(movementId);
  const router = useRouter();

  const refs = useApiQuery((signal) => listPracticeReferences(signal), [], Number.isInteger(referenceId));
  const reference = refs.data?.find((r) => r.id === referenceId) ?? null;
  const maxSeconds = reference?.max_duration_seconds ?? config.maxRecordingSeconds;

  const camera = useCamera();
  const recorder = useMediaRecorder({ maxSeconds, maxBytes: config.maxUploadMb * 1024 * 1024 });
  const [state, dispatch] = useReducer(practiceReducer, initialPracticeState);

  const sessionIdRef = useRef<number | null>(null); // reuse one session across upload retries
  const submittingRef = useRef(false); // hard lock against double submit
  const controllerRef = useRef<AbortController | null>(null);

  // --- Keep the state machine in sync with the hooks -------------------------
  useEffect(() => {
    if (camera.status === "ready") dispatch({ type: "CAMERA_READY" });
    if (camera.status === "error" && camera.error) {
      dispatch({ type: "FAIL", message: camera.error, recoverTo: "idle" });
    }
  }, [camera.status, camera.error]);

  useEffect(() => {
    if (recorder.status === "recorded") dispatch({ type: "RECORDING_DONE" });
    if (recorder.status === "error" && recorder.error) {
      dispatch({ type: "FAIL", message: recorder.error, recoverTo: camera.stream ? "camera_ready" : "idle" });
    }
  }, [recorder.status, recorder.error, camera.stream]);

  // Leaving the page (or Next.js hiding it) cancels uploads and resets the flow.
  // The hooks stop the camera and free the recording themselves.
  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
      submittingRef.current = false;
      sessionIdRef.current = null;
      dispatch({ type: "RESET" });
    };
  }, []);

  // --- Actions ----------------------------------------------------------------
  const enableCamera = useCallback(() => {
    dispatch({ type: "REQUEST_CAMERA" });
    void camera.start();
  }, [camera]);

  const startRecording = () => {
    if (state.phase !== "camera_ready" || !camera.stream) return;
    dispatch({ type: "START_RECORDING" });
    if (!recorder.start(camera.stream)) {
      // the recorder hook sets its own error, which the effect above turns into FAIL
    }
  };

  const retake = () => {
    recorder.reset();
    if (camera.stream) dispatch({ type: "RETAKE" });
    else {
      dispatch({ type: "RESET" });
    }
  };

  const submit = async () => {
    const recording = recorder.recording;
    if (submittingRef.current || state.phase !== "recorded" || !recording || !reference) return;
    submittingRef.current = true;
    dispatch({ type: "SUBMIT" });

    const controller = new AbortController();
    controllerRef.current = controller;

    let sessionId = sessionIdRef.current;
    try {
      if (sessionId === null) {
        const session = await createPracticeSession(reference.id, controller.signal);
        sessionId = session.session_id;
        sessionIdRef.current = sessionId;
      }
      await uploadPracticeVideo(sessionId, reference.id, recording.blob, (p) => dispatch({ type: "UPLOAD_PROGRESS", progress: p }), controller.signal);
      dispatch({ type: "UPLOAD_DONE", sessionId });
      camera.stop(); // video is uploaded — turn the camera light off
    } catch (err) {
      submittingRef.current = false;
      if (err instanceof ApiError && err.kind === "aborted") return;
      dispatch({ type: "FAIL", message: `Upload failed. ${describeError(err)}`, recoverTo: "recorded" });
      return;
    }

    try {
      await evaluateAndWait(sessionId, controller.signal);
      dispatch({ type: "EVALUATION_DONE", sessionId });
      recorder.reset(); // release the recording from memory
      router.push(`/results/${sessionId}`);
    } catch (err) {
      if (err instanceof ApiError && err.kind === "aborted") return;
      if (err instanceof ApiError && err.kind === "timeout") {
        // Still processing on the server — the results page keeps checking.
        dispatch({ type: "EVALUATION_DONE", sessionId });
        recorder.reset();
        router.push(`/results/${sessionId}`);
        return;
      }
      dispatch({ type: "FAIL", message: `Evaluation failed. ${describeError(err)}`, recoverTo: "recorded" });
    } finally {
      submittingRef.current = false;
    }
  };

  const retry = () => {
    if (state.recoverTo === "recorded" && !recorder.recording) {
      dispatch({ type: "RESET" });
      return;
    }
    if (state.recoverTo === "camera_ready" && !camera.stream) {
      dispatch({ type: "RESET" });
      return;
    }
    dispatch({ type: "RETRY" });
  };

  // --- Render -----------------------------------------------------------------
  if (!Number.isInteger(referenceId)) {
    return <EmptyState title="Unknown practice reference" description="This link doesn't point to a valid reference." action={<BackLink />} />;
  }
  if (refs.loading) return <LoadingState label="Loading reference…" className="min-h-80" />;
  if (refs.error) return <ErrorState error={refs.error} title="Couldn't load the practice reference" onRetry={refs.reload} />;
  if (!reference) {
    return <EmptyState title="Reference not available" description="This reference doesn't exist or can't be evaluated yet." action={<BackLink />} />;
  }

  const phase = state.phase;
  const busy = phase === "uploading" || phase === "processing";
  const activeStep = STEPS.findIndex((s) => s.phases.includes(phase === "error" ? state.recoverTo : phase));

  return (
    <div>
      <BackLink />
      <div className="mt-4 grid gap-8 lg:grid-cols-[1.6fr_1fr]">
        {/* Camera column */}
        <section aria-labelledby="practice-heading">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h1 id="practice-heading" className="font-display text-4xl font-semibold text-maroon-dark">
              {reference.name}
            </h1>
            <ol className="flex items-center gap-1.5 text-xs font-semibold" aria-label="Progress">
              {STEPS.map((step, i) => (
                <li
                  key={step.key}
                  aria-current={i === activeStep ? "step" : undefined}
                  className={`rounded-full px-2.5 py-1 ${i === activeStep ? "bg-maroon text-ivory" : i < activeStep ? "bg-gold-soft text-maroon" : "bg-ivory-deep text-ink-muted"}`}
                >
                  {step.label}
                </li>
              ))}
            </ol>
          </div>

          <CameraStage
            stream={camera.stream}
            recordingUrl={recorder.recording?.url ?? null}
            isRecording={phase === "recording"}
            isRequesting={phase === "requesting_camera"}
            elapsedMs={recorder.elapsedMs}
            maxSeconds={maxSeconds}
          />

          {/* Controls */}
          <div className="mt-5 flex flex-wrap items-center gap-3" aria-live="polite">
            {phase === "idle" ? (
              <Button size="lg" onClick={enableCamera} icon={<IconCamera width={18} height={18} />}>
                Enable camera
              </Button>
            ) : null}
            {phase === "requesting_camera" ? (
              <Button size="lg" loading disabled>
                Starting camera…
              </Button>
            ) : null}
            {phase === "camera_ready" ? (
              <>
                <Button size="lg" onClick={startRecording} icon={<IconRecord width={18} height={18} className="text-red-300" />}>
                  Start recording
                </Button>
                <span className="text-sm text-ink-muted">Recording stops automatically after {maxSeconds} seconds.</span>
              </>
            ) : null}
            {phase === "recording" ? (
              <Button size="lg" variant="danger" onClick={recorder.stop} icon={<IconStop width={18} height={18} />}>
                Stop recording
              </Button>
            ) : null}
            {phase === "recorded" && recorder.recording ? (
              <>
                <Button size="lg" onClick={submit} icon={<IconUpload width={18} height={18} />}>
                  Submit for evaluation
                </Button>
                <Button size="lg" variant="secondary" onClick={retake} icon={<IconRefresh width={18} height={18} />}>
                  Retake
                </Button>
                <span className="text-sm text-ink-muted">
                  {formatDuration(recorder.recording.durationMs)} · {formatBytes(recorder.recording.sizeBytes)}
                </span>
              </>
            ) : null}
            {phase === "uploading" ? <UploadProgress progress={state.uploadProgress} /> : null}
            {phase === "processing" ? (
              <div className="flex items-center gap-3 rounded-xl bg-gold-soft/60 px-4 py-3 text-maroon" role="status">
                <Spinner />
                <span className="font-medium">Analysing your recording against the reference… this can take a little while.</span>
              </div>
            ) : null}
            {phase === "completed" ? (
              <div className="flex items-center gap-2 text-success" role="status">
                <IconCheck /> Evaluation complete — opening your results…
                {state.sessionId ? (
                  <Link href={`/results/${state.sessionId}`} className="font-semibold underline">
                    View results
                  </Link>
                ) : null}
              </div>
            ) : null}
            {phase === "error" ? (
              <div role="alert" className="flex w-full flex-col gap-3 rounded-xl border border-danger/25 bg-danger-soft/70 p-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="flex items-start gap-2 text-ink">
                  <IconAlert className="mt-0.5 shrink-0 text-danger" /> {state.error}
                </p>
                <Button variant="secondary" size="sm" onClick={retry} icon={<IconRefresh width={16} height={16} />}>
                  {state.recoverTo === "recorded" ? "Back to my recording" : state.recoverTo === "idle" ? "Try again" : "Back to camera"}
                </Button>
              </div>
            ) : null}
          </div>

          <p className="mt-6 text-xs leading-relaxed text-ink-muted">
            Your video stays on this device until you press <strong>Submit</strong>. It is then sent to the NrityaGuru server only to extract hand
            landmarks for this evaluation. No audio is recorded.
          </p>
        </section>

        {/* Reference column */}
        <aside className="space-y-5" aria-label="Reference and tips">
          <div className="overflow-hidden rounded-2xl border border-line bg-paper shadow-[var(--shadow-card)]">
            <MudraImage src={reference.image_url} name={reference.name} className="aspect-[4/3] w-full" />
            <div className="p-5">
              <Badge tone={reference.reference_type === "sequence" ? "maroon" : "gold"}>
                {reference.reference_type === "sequence" ? `Sequence · ${reference.mudra_ids.length} steps` : "Single mudra"}
              </Badge>
              {reference.description ? <p className="mt-2 text-ink-muted">{reference.description}</p> : null}
              {reference.mudra_ids.length === 1 ? (
                <Link href={`/mudras/${reference.mudra_ids[0]}`} className="mt-3 inline-block text-sm font-semibold text-maroon hover:underline">
                  Read about this mudra →
                </Link>
              ) : null}
            </div>
          </div>
          <div className="rounded-2xl border border-line bg-paper p-5">
            <h2 className="font-display text-xl font-semibold text-maroon-dark">Before you record</h2>
            <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-ink">
              {TIPS.map((tip) => (
                <li key={tip} className="flex gap-2">
                  <IconCheck width={16} height={16} className="mt-0.5 shrink-0 text-gold" />
                  {tip}
                </li>
              ))}
            </ul>
          </div>
          {busy ? <Notice>Please keep this page open until evaluation finishes.</Notice> : null}
        </aside>
      </div>
    </div>
  );
}

function UploadProgress({ progress }: { progress: number }) {
  const pct = Math.round(progress * 100);
  return (
    <div className="w-full max-w-md">
      <div className="mb-1.5 flex justify-between text-sm font-medium text-maroon">
        <span>Uploading recording…</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-ivory-deep" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Upload progress">
        <div className="h-full rounded-full bg-maroon transition-[width] duration-200" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function BackLink() {
  return (
    <Link href="/practice" className="inline-flex items-center gap-1.5 rounded text-sm font-medium text-maroon hover:underline">
      <IconArrowLeft width={16} height={16} /> All practice references
    </Link>
  );
}
