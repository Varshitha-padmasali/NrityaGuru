/** Shared loading, error, empty and notice states so every page looks consistent. */
import type { ReactNode } from "react";
import { describeError } from "@/types/api";
import { cn } from "@/lib/utils";
import { Button } from "./Button";
import { Spinner } from "./Spinner";
import { IconAlert, IconInfo, IconRefresh } from "./Icons";

export function LoadingState({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex min-h-40 items-center justify-center text-maroon", className)}>
      <Spinner size={24} label={label} />
    </div>
  );
}

export function ErrorState({ error, title = "Something went wrong", onRetry, className }: { error: unknown; title?: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn("rounded-2xl border border-danger/25 bg-danger-soft/70 p-6", className)}>
      <div className="flex items-start gap-3">
        <IconAlert className="mt-0.5 shrink-0 text-danger" />
        <div className="flex-1">
          <h2 className="font-semibold text-danger">{title}</h2>
          <p className="mt-1 text-ink">{describeError(error)}</p>
          {onRetry ? (
            <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry} icon={<IconRefresh width={16} height={16} />}>
              Try again
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title, description, action, icon }: { title: string; description?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line bg-paper/60 px-6 py-12 text-center">
      {icon ? <div className="mb-4 text-gold">{icon}</div> : null}
      <h2 className="font-display text-2xl font-semibold text-maroon-dark">{title}</h2>
      {description ? <p className="mt-2 max-w-md text-ink-muted">{description}</p> : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

export function Notice({ tone = "info", children, className }: { tone?: "info" | "warning"; children: ReactNode; className?: string }) {
  const styles = tone === "warning" ? "border-warning/30 bg-warning-soft text-ink" : "border-gold/30 bg-gold-soft/50 text-ink";
  return (
    <div className={cn("flex items-start gap-3 rounded-xl border p-4 text-sm leading-relaxed", styles, className)}>
      {tone === "warning" ? <IconAlert className="mt-0.5 shrink-0 text-warning" /> : <IconInfo className="mt-0.5 shrink-0 text-gold" />}
      <div>{children}</div>
    </div>
  );
}
