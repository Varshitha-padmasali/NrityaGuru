import { describe, expect, it } from "vitest";
import { initialPracticeState, practiceReducer, type PracticeEvent, type PracticeState } from "@/components/practice/practiceMachine";

const run = (events: PracticeEvent[], start: PracticeState = initialPracticeState) => events.reduce(practiceReducer, start);

describe("practice state machine", () => {
  it("follows the happy path from idle to completed", () => {
    const end = run([
      { type: "REQUEST_CAMERA" },
      { type: "CAMERA_READY" },
      { type: "START_RECORDING" },
      { type: "RECORDING_DONE" },
      { type: "SUBMIT" },
      { type: "UPLOAD_PROGRESS", progress: 0.5 },
      { type: "UPLOAD_DONE", sessionId: 7 },
      { type: "EVALUATION_DONE", sessionId: 7 },
    ]);
    expect(end.phase).toBe("completed");
    expect(end.sessionId).toBe(7);
  });

  it("ignores recording before the camera is ready", () => {
    expect(run([{ type: "START_RECORDING" }]).phase).toBe("idle");
    expect(run([{ type: "REQUEST_CAMERA" }, { type: "START_RECORDING" }]).phase).toBe("requesting_camera");
  });

  it("ignores submit when there is no recording", () => {
    expect(run([{ type: "REQUEST_CAMERA" }, { type: "CAMERA_READY" }, { type: "SUBMIT" }]).phase).toBe("camera_ready");
  });

  it("ignores a second submit while uploading", () => {
    const uploading = run([{ type: "REQUEST_CAMERA" }, { type: "CAMERA_READY" }, { type: "START_RECORDING" }, { type: "RECORDING_DONE" }, { type: "SUBMIT" }]);
    expect(uploading.phase).toBe("uploading");
    const again = practiceReducer(uploading, { type: "SUBMIT" });
    expect(again).toBe(uploading); // same object = event ignored
  });

  it("does not mark completed before the backend confirms (no EVALUATION_DONE while uploading)", () => {
    const uploading = run([{ type: "REQUEST_CAMERA" }, { type: "CAMERA_READY" }, { type: "START_RECORDING" }, { type: "RECORDING_DONE" }, { type: "SUBMIT" }]);
    expect(practiceReducer(uploading, { type: "EVALUATION_DONE", sessionId: 1 }).phase).toBe("uploading");
  });

  it("retake returns to the camera and clears progress", () => {
    const recorded = run([{ type: "REQUEST_CAMERA" }, { type: "CAMERA_READY" }, { type: "START_RECORDING" }, { type: "RECORDING_DONE" }]);
    expect(practiceReducer(recorded, { type: "RETAKE" }).phase).toBe("camera_ready");
  });

  it("FAIL then RETRY goes back to the recovery phase", () => {
    const uploading = run([{ type: "REQUEST_CAMERA" }, { type: "CAMERA_READY" }, { type: "START_RECORDING" }, { type: "RECORDING_DONE" }, { type: "SUBMIT" }]);
    const failed = practiceReducer(uploading, { type: "FAIL", message: "Network down", recoverTo: "recorded" });
    expect(failed.phase).toBe("error");
    expect(failed.error).toBe("Network down");
    expect(practiceReducer(failed, { type: "RETRY" }).phase).toBe("recorded");
  });

  it("clamps upload progress to 0..1", () => {
    const uploading = run([{ type: "REQUEST_CAMERA" }, { type: "CAMERA_READY" }, { type: "START_RECORDING" }, { type: "RECORDING_DONE" }, { type: "SUBMIT" }]);
    expect(practiceReducer(uploading, { type: "UPLOAD_PROGRESS", progress: 5 }).uploadProgress).toBe(1);
  });

  it("RESET always returns to the initial state", () => {
    const recording = run([{ type: "REQUEST_CAMERA" }, { type: "CAMERA_READY" }, { type: "START_RECORDING" }]);
    expect(practiceReducer(recording, { type: "RESET" })).toEqual(initialPracticeState);
  });
});
