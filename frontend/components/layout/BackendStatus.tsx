"use client";

/** Small dot in the header showing whether GET /health answers. */
import { useApiQuery } from "@/hooks/useApiQuery";
import { getHealth } from "@/services/knowledge-service";
import { config } from "@/lib/config";
import { cn } from "@/lib/utils";

export function BackendStatus() {
  const { data, error, loading } = useApiQuery((signal) => getHealth(signal), []);

  const state = loading ? "checking" : error ? "offline" : data?.status === "ok" ? "online" : "degraded";
  const label = config.useMockApi
    ? "Mock data"
    : { checking: "Checking server", offline: "Server offline", online: "Server online", degraded: "Server degraded" }[state];

  return (
    <span className="hidden items-center gap-2 text-xs font-medium text-ink-muted sm:inline-flex" role="status" title={config.useMockApi ? "Development mock mode" : config.apiBaseUrl}>
      <span
        aria-hidden="true"
        className={cn(
          "h-2 w-2 rounded-full",
          config.useMockApi ? "bg-warning" : state === "online" ? "bg-success" : state === "checking" ? "bg-gold animate-pulse" : "bg-danger",
        )}
      />
      {label}
    </span>
  );
}
