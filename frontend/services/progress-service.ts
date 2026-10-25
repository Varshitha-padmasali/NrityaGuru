/** Learning history. */
import { apiRequest } from "@/lib/api-client";
import { endpoints } from "@/lib/api-endpoints";
import { isProgressResponse } from "@/lib/validators";
import type { ProgressResponse } from "@/types/progress";

export function getProgress(signal?: AbortSignal): Promise<ProgressResponse> {
  return apiRequest(endpoints.progress(), { validate: isProgressResponse, signal });
}
