/** Practice references, sessions and video upload. */
import { apiRequest, uploadWithProgress } from "@/lib/api-client";
import { endpoints } from "@/lib/api-endpoints";
import { isPracticeReferenceList, isPracticeSession } from "@/lib/validators";
import { extensionForMimeType } from "@/lib/media";
import type { PracticeReference, PracticeSession } from "@/types/practice";

export function listPracticeReferences(signal?: AbortSignal): Promise<PracticeReference[]> {
  return apiRequest(endpoints.movements(), { validate: isPracticeReferenceList, signal });
}

export function createPracticeSession(referenceId: number, signal?: AbortSignal): Promise<PracticeSession> {
  return apiRequest(endpoints.sessions(), { method: "POST", json: { reference_id: referenceId }, validate: isPracticeSession, signal });
}

/**
 * Upload the recording as multipart/form-data. The backend reads the file
 * from the "video" field and the reference from "reference_id".
 */
export function uploadPracticeVideo(
  sessionId: number,
  referenceId: number,
  blob: Blob,
  onProgress?: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<PracticeSession> {
  const form = new FormData();
  const ext = extensionForMimeType(blob.type);
  form.append("video", blob, `practice-${sessionId}.${ext}`);
  form.append("reference_id", String(referenceId));
  return uploadWithProgress(endpoints.sessionVideo(sessionId), form, { validate: isPracticeSession, onProgress, signal });
}
