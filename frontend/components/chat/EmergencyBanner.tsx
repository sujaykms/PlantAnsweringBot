"use client";
import { useState } from "react";
import { BellRing, Check, Loader2, Siren } from "lucide-react";
import { Button } from "@/components/ui/button";
import { notifyOperator } from "@/lib/emergency";

type State = "pending" | "sending" | "sent" | "cancelled" | "error";

const SAFETY =
  "Possible emergency — stop work, get the person to safety, call your supervisor and the site emergency number now.";

export function EmergencyBanner({
  question,
  conversationId,
  messageId,
}: {
  question: string;
  conversationId?: string;
  messageId?: string;
}) {
  const [state, setState] = useState<State>("pending");
  const [location, setLocation] = useState("");
  const [sentAt, setSentAt] = useState<Date | null>(null);

  const confirm = async () => {
    setState("sending");
    try {
      const r = await notifyOperator({
        question,
        ...(conversationId ? { conversation_id: conversationId } : {}),
        ...(messageId ? { message_id: messageId } : {}),
        ...(location.trim() ? { location: location.trim() } : {}),
      });
      setSentAt(new Date(r.created_at));
      setState("sent");
    } catch {
      setState("error");
    }
  };

  return (
    <div
      role="alert"
      className="mb-3 rounded-xl border-2 border-destructive bg-destructive/10 p-4 text-foreground"
    >
      <p className="flex gap-3 font-semibold">
        <Siren className="mt-0.5 size-6 shrink-0 text-destructive" />
        {SAFETY}
      </p>

      {state === "cancelled" ? (
        <button
          type="button"
          onClick={() => setState("pending")}
          className="mt-2 min-h-11 rounded-lg px-1 text-sm font-medium underline outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Notify operator
        </button>
      ) : (
        <div className="mt-3 space-y-3 border-t border-destructive/30 pt-3">
          {state === "sent" ? (
            <p className="flex items-center gap-2 font-semibold" aria-live="polite">
              <Check className="size-5 text-safety" />
              Plant operator notified
              {sentAt && (
                <span className="font-normal text-muted-foreground">
                  · {sentAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </span>
              )}
            </p>
          ) : (
            <>
              <p className="flex items-center gap-2 font-semibold">
                <BellRing className="size-5" /> Notify the plant operator?
              </p>
              {state === "error" && (
                <p className="text-sm font-medium text-destructive" aria-live="assertive">
                  Couldn&apos;t notify — try again. Call your supervisor directly now.
                </p>
              )}
              <label className="block text-sm">
                <span className="text-muted-foreground">Where? (optional)</span>
                <input
                  value={location}
                  onChange={(e) => setLocation(e.target.value.slice(0, 200))}
                  maxLength={200}
                  disabled={state === "sending"}
                  placeholder="e.g. Paint line, bay 2"
                  className="mt-1 min-h-12 w-full rounded-lg border bg-background px-3 text-base outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </label>
            </>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              size="lg"
              variant="destructive"
              className="min-h-14 flex-1 text-base sm:flex-none sm:px-8"
              disabled={state === "sending" || state === "sent"}
              onClick={confirm}
            >
              {state === "sending" && <Loader2 className="animate-spin" />}
              {state === "error" ? "Retry" : state === "sent" ? "Notified" : "Confirm"}
            </Button>
            {state !== "sent" && (
              <Button
                size="lg"
                variant="outline"
                className="min-h-14 flex-1 text-base sm:flex-none sm:px-8"
                disabled={state === "sending"}
                onClick={() => setState("cancelled")}
              >
                Cancel
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
