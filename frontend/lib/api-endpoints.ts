/** Every backend path in one place, so a renamed endpoint is a one-line change. */
export const endpoints = {
  health: () => "/health",
  mudras: () => "/api/mudras",
  mudra: (id: number | string) => `/api/mudras/${encodeURIComponent(String(id))}`,
  retrieve: () => "/api/knowledge/retrieve",
  explain: () => "/api/tutor/explain",
  movements: () => "/api/movements",
  sessions: () => "/api/practice/sessions",
  sessionVideo: (sessionId: number | string) => `/api/practice/sessions/${encodeURIComponent(String(sessionId))}/video`,
  sessionEvaluate: (sessionId: number | string) => `/api/practice/sessions/${encodeURIComponent(String(sessionId))}/evaluate`,
  sessionResults: (sessionId: number | string) => `/api/practice/sessions/${encodeURIComponent(String(sessionId))}/results`,
  sessionFeedback: (sessionId: number | string) => `/api/practice/sessions/${encodeURIComponent(String(sessionId))}/feedback`,
  progress: () => "/api/progress",
} as const;
