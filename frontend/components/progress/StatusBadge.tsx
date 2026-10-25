import { Badge } from "@/components/ui/Card";
import type { SessionStatus } from "@/types/practice";

const LABELS: Record<SessionStatus, { text: string; tone: "neutral" | "gold" | "success" | "danger" | "warning" }> = {
  created: { text: "Not recorded", tone: "neutral" },
  uploaded: { text: "Uploaded", tone: "gold" },
  processing: { text: "Processing", tone: "warning" },
  evaluated: { text: "Evaluated", tone: "success" },
  failed: { text: "Failed", tone: "danger" },
};

export function StatusBadge({ status }: { status: SessionStatus }) {
  const label = LABELS[status] ?? { text: status, tone: "neutral" as const };
  return <Badge tone={label.tone}>{label.text}</Badge>;
}
