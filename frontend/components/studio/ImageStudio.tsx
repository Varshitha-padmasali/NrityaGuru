"use client";

/**
 * Image Studio UI (development only). Talks to /api/studio on the Next.js
 * server, which calls Gemini with the secret key. One card per image slot:
 * see the prompt, edit it, generate, regenerate, or go back to the stock photo.
 */
import { useCallback, useEffect, useState } from "react";
import { Badge, Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorState, LoadingState, Notice } from "@/components/ui/StatusStates";
import { IconRefresh, IconSparkle } from "@/components/ui/Icons";
import { formatDateTime } from "@/lib/utils";

interface Slot {
  slot: string;
  aspectRatio: string;
  imageSize: string;
  prompt: string;
  generated: { src: string; model: string; createdAt: string } | null;
}

interface StudioState {
  keyConfigured: boolean;
  model: string;
  style: string;
  slots: Slot[];
}

const SLOT_LABELS: Record<string, string> = {
  seq1: "Slideshow 1 · Pushpanjali (reference dancer)",
  seq2: "Slideshow 2 · Alarippu",
  seq3: "Slideshow 3 · Jatiswaram",
  seq4: "Slideshow 4 · Shabdam",
  seq5: "Slideshow 5 · Varnam",
  seq6: "Slideshow 6 · Padam",
  seq7: "Slideshow 7 · Tillana",
  seq8: "Slideshow 8 · Mangalam",
  shloka: "Shloka section",
  blackPortrait: "Gallery — large tile",
  redStage: "Gallery — tall tile",
  smileStage: "Gallery — small tile 1",
  greenCostume: "Gallery — small tile 2",
};

async function studio<T>(body: object): Promise<T> {
  const res = await fetch("/api/studio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`);
  return data as T;
}

export function ImageStudio() {
  const [state, setState] = useState<StudioState | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    studio<StudioState>({ action: "list" })
      .then((s) => {
        setState(s);
        setLoadError(null);
      })
      .catch(setLoadError);
  }, []);

  useEffect(load, [load]);

  const generate = async (slot: string) => {
    if (busy[slot]) return;
    setBusy((b) => ({ ...b, [slot]: true }));
    setErrors((e) => ({ ...e, [slot]: null }));
    try {
      await studio({ action: "generate", slot, prompt: drafts[slot] });
      load();
    } catch (err) {
      setErrors((e) => ({ ...e, [slot]: err instanceof Error ? err.message : "Failed" }));
    } finally {
      setBusy((b) => ({ ...b, [slot]: false }));
    }
  };

  const clear = async (slot: string) => {
    await studio({ action: "clear", slot }).catch(() => undefined);
    load();
  };

  if (loadError) return <ErrorState error={loadError} title="The Image Studio isn't available" onRetry={load} />;
  if (!state) return <LoadingState label="Loading image slots…" />;

  const pending = state.slots.filter((s) => !s.generated).map((s) => s.slot);

  return (
    <div className="space-y-8">
      {!state.keyConfigured ? (
        <Notice tone="warning">
          <strong>GEMINI_API_KEY is not set.</strong> Create a key at aistudio.google.com, add <code>GEMINI_API_KEY=your-key</code> to{" "}
          <code>frontend/.env.local</code>, then restart <code>npm run dev</code>.
        </Notice>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-line bg-paper p-5">
          <p className="text-ink">
            Model: <strong>{state.model}</strong> · {state.slots.length - pending.length}/{state.slots.length} slots generated
          </p>
          {pending.length > 0 ? (
            <Button
              icon={<IconSparkle width={18} height={18} />}
              disabled={Object.values(busy).some(Boolean)}
              onClick={async () => {
                for (const slot of pending) await generate(slot);
              }}
            >
              Generate all missing ({pending.length}) — slideshow first
            </Button>
          ) : null}
        </div>
      )}

      <Notice>
        <strong>Tip:</strong> generate <em>Slideshow 1</em> first and regenerate it until you love the dancer — frames 2–8 use it as a reference so the same dancer
        appears in every step. If you regenerate frame 1 later, regenerate the others too.
      </Notice>

      <Notice>
        Generated images are decoration only and are labelled &ldquo;AI-generated&rdquo; on the site. AI images can draw hands incorrectly, so never use them as mudra
        reference images — those must come from the verified knowledge base.
      </Notice>

      <div className="grid gap-6 md:grid-cols-2">
        {state.slots.map((s) => (
          <Card key={s.slot} className="overflow-hidden">
            <div className="relative flex aspect-[4/3] items-center justify-center bg-[#14060a]">
              {s.generated ? (
                // eslint-disable-next-line @next/next/no-img-element -- local generated file
                <img src={s.generated.src} alt={`Generated image for ${s.slot}`} className="h-full w-full object-contain" />
              ) : (
                <p className="px-6 text-center text-sm text-ivory/60">Not generated yet — the stock photo is shown on the site.</p>
              )}
              {busy[s.slot] ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/60 text-gold-soft">
                  <LoadingState label="Gemini is painting…" className="min-h-0 text-gold-soft" />
                </div>
              ) : null}
            </div>
            <div className="space-y-3 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-display text-2xl font-semibold text-maroon-dark">{SLOT_LABELS[s.slot] ?? s.slot}</h2>
                <Badge>{s.aspectRatio}</Badge>
                <Badge>{s.imageSize}</Badge>
              </div>
              <label htmlFor={`prompt-${s.slot}`} className="block text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Prompt
              </label>
              <textarea
                id={`prompt-${s.slot}`}
                rows={5}
                value={drafts[s.slot] ?? s.prompt}
                onChange={(e) => setDrafts((d) => ({ ...d, [s.slot]: e.target.value }))}
                className="w-full rounded-xl border border-line bg-ivory/60 px-3 py-2 text-sm text-ink focus:border-gold focus:outline-none"
              />
              {errors[s.slot] ? (
                <p role="alert" className="text-sm font-medium text-danger">
                  {errors[s.slot]}
                </p>
              ) : null}
              {s.generated ? <p className="text-xs text-ink-muted">Generated {formatDateTime(s.generated.createdAt)} with {s.generated.model}</p> : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  onClick={() => generate(s.slot)}
                  loading={busy[s.slot]}
                  disabled={!state.keyConfigured}
                  icon={s.generated ? <IconRefresh width={16} height={16} /> : <IconSparkle width={16} height={16} />}
                >
                  {s.generated ? "Regenerate" : "Generate"}
                </Button>
                {s.generated ? (
                  <Button size="sm" variant="ghost" onClick={() => clear(s.slot)}>
                    Use stock photo instead
                  </Button>
                ) : null}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
