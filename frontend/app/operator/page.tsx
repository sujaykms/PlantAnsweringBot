"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Check, Loader2, Siren } from "lucide-react";
import { Button } from "@/components/ui/button";
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
    <>
      <header className="border-b-4 border-hazard bg-card">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-4 px-4 py-3">
          <h1 className="flex-1 text-xl font-bold tracking-tight">Operator alerts</h1>
          <Link
            href="/"
            className="flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm font-medium underline outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ArrowLeft className="size-4" /> Back to chat
          </Link>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6">
          {error && (
            <p role="alert" className="mb-4 rounded-xl border-2 border-destructive bg-destructive/10 p-3 text-sm">
              Couldn&apos;t refresh alerts. Retrying every 5 seconds.
            </p>
          )}
          {alerts === null ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : alerts.length === 0 ? (
            <p className="rounded-xl border-2 border-dashed p-6 text-center text-muted-foreground">
              No open alerts.
            </p>
          ) : (
            <ul className="space-y-3">
              {alerts.map((a) => (
                <li
                  key={a.id}
                  className="flex flex-col gap-3 rounded-xl border-2 border-destructive bg-destructive/10 p-4 sm:flex-row sm:items-center"
                >
                  <Siren className="size-6 shrink-0 text-destructive" />
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-xs text-muted-foreground">
                      {new Date(a.created_at).toLocaleString()}
                    </p>
                    <p className="font-semibold break-words">{a.question}</p>
                    {a.location && <p className="text-sm">Where: {a.location}</p>}
                  </div>
                  <Button
                    size="lg"
                    className="min-h-14 sm:px-6"
                    disabled={busy === a.id}
                    onClick={() => ack(a.id)}
                  >
                    {busy === a.id ? <Loader2 className="animate-spin" /> : <Check />} Acknowledge
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </>
  );
}
