"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Check, Loader2, Siren } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ackAlert, listOpenAlerts } from "@/lib/emergency";
import type { EmergencyAlert } from "@/lib/types";

export default function OperatorPage() {
  const [alerts, setAlerts] = useState<EmergencyAlert[] | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setAlerts(await listOpenAlerts());
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    const t = setInterval(load, 5000);
    return () => {
      clearTimeout(first);
      clearInterval(t);
    };
  }, [load]);

  const ack = async (id: string) => {
    setBusy(id);
    try {
      await ackAlert(id);
      await load();
    } catch {
      setError(true);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-1 px-2 py-2">
        <Link
          href="/"
          className="flex min-h-11 items-center gap-2 rounded-xl px-3 text-[0.95rem] text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-brand"
        >
          <ArrowLeft className="size-4" /> Back to chat
        </Link>
        <span className="flex-1" />
        <ThemeToggle />
      </header>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[46rem] px-4 pt-4 pb-10">
          <h1 className="mb-6 text-[1.75rem] font-semibold tracking-tight">Operator alerts</h1>
          {error && (
            <p role="alert" className="mb-4 rounded-2xl border-2 border-destructive bg-destructive/10 p-3 text-sm">
              Couldn&apos;t refresh alerts. Retrying every 5 seconds.
            </p>
          )}
          {alerts === null ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : alerts.length === 0 ? (
            <p className="rounded-2xl border border-dashed p-8 text-center text-muted-foreground">
              No open alerts.
            </p>
          ) : (
            <ul className="space-y-3">
              {alerts.map((a) => (
                <li
                  key={a.id}
                  className="flex flex-col gap-3 overflow-hidden rounded-2xl border-2 border-destructive bg-destructive/10 p-4 sm:flex-row sm:items-center"
                >
                  <Siren className="size-6 shrink-0 text-destructive" />
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-xs text-muted-foreground">
                      {new Date(a.created_at).toLocaleString()}
                    </p>
                    <p className="text-lg font-semibold break-words">{a.question}</p>
                    {a.location && <p className="text-sm">Where: {a.location}</p>}
                  </div>
                  <button
                    type="button"
                    disabled={busy === a.id}
                    onClick={() => ack(a.id)}
                    className="flex min-h-14 items-center justify-center gap-2 rounded-full bg-primary px-6 font-medium text-primary-foreground outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-50"
                  >
                    {busy === a.id ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}{" "}
                    Acknowledge
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
