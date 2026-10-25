"use client";
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowUp, FileQuestion, RotateCcw, SquarePen, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useChatStream } from "@/lib/useChatStream";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Markdown } from "./Markdown";
import { RouteBadges } from "./RouteBadges";
import { SourceCards } from "./SourceCards";
import { EmergencyBanner } from "./EmergencyBanner";
import { StageIndicator } from "./StageIndicator";
import { VerificationNotice } from "./Verification";
import { citeMatches } from "./cite";
import { SOURCE_STYLE } from "./source";

const STARTERS = [
  "What PPE is needed for electrical isolation?",
  "P-101 shows fault E35",
  "Torque for P-101 motor mount bolts?",
  "We found 3 bad welds in a lot of 500 — hold it?",
  "How do I replace the P-101 mechanical seal?",
];

function Assistant({ m, onRetry }: { m: ChatMessage; onRetry: () => void }) {
  const [focus, setFocus] = useState<{ ids: string[]; n: number } | null>(null);
  const onCite = (cite: string) => {
    const ids = (m.sources ?? []).filter((c) => citeMatches(cite, c)).map((c) => c.id);
    if (ids.length) setFocus((f) => ({ ids, n: (f?.n ?? 0) + 1 }));
  };
  return (
    <div className="max-w-3xl">
      {m.route?.emergency && (
        <EmergencyBanner
          question={m.question ?? ""}
          conversationId={m.conversationId}
          messageId={m.messageId}
        />
      )}
      {m.route && <RouteBadges route={m.route} />}
      {m.notFound ? (
        <div className="mt-1 flex gap-3 rounded-xl border-2 border-dashed border-hazard bg-hazard/10 p-4">
          <FileQuestion className="mt-0.5 size-6 shrink-0" />
          <div>
            <p className="font-semibold">Not found in the plant documents</p>
            <p className="text-sm text-muted-foreground">
              Check the sources below, rephrase with an equipment tag or SOP number, or ask your
              supervisor.
            </p>
          </div>
        </div>
      ) : m.content ? (
        <Markdown text={m.content} onCite={onCite} />
      ) : (
        m.streaming && <StageIndicator stage={m.stage ?? "routing"} />
      )}
      {!m.streaming && !m.error && !m.notFound && <VerificationNotice v={m.verification} />}
      {m.streaming && m.content && (
        <span className="ml-1 inline-block h-4 w-2 animate-pulse bg-foreground align-middle" />
      )}
      {m.error && (
        <div
          role="alert"
          className="mt-2 flex flex-wrap items-center gap-3 rounded-xl border-2 border-destructive bg-destructive/10 p-3"
        >
          <AlertTriangle className="size-5 text-destructive" />
          <span className="flex-1 text-sm">{m.error}</span>
          <Button size="lg" variant="outline" className="min-h-11" onClick={onRetry}>
            <RotateCcw /> Retry
          </Button>
        </div>
      )}
      {m.sources && (
        <SourceCards sources={m.sources} answer={m.content} scope={m.id} focus={focus} />
      )}
    </div>
  );
}

export function Chat() {
  const { messages, streaming, send, retry, stop, reset } = useChatStream();
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const submit = (t: string) => {
    if (!t.trim() || streaming) return;
    send(t);
    setInput("");
  };

  return (
    <>
      <header className="border-b-4 border-hazard bg-card">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <h1 className="text-xl font-bold tracking-tight">Plant Docs Assistant</h1>
          <ul className="flex flex-1 flex-wrap items-center gap-2 text-sm font-semibold" aria-label="Source legend">
            {Object.entries(SOURCE_STYLE).map(([k, s]) => (
              <li key={k} className={cn("rounded-full border px-3 py-1", s.text, s.bg, s.border)}>
                {s.label}
              </li>
            ))}
          </ul>
          {messages.length > 0 && (
            <Button variant="outline" size="lg" className="min-h-11" onClick={reset}>
              <SquarePen /> New chat
            </Button>
          )}
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6">
          {messages.length === 0 ? (
            <section>
              <h2 className="mb-1 text-2xl font-bold">What do you need to know?</h2>
              <p className="mb-5 text-muted-foreground">
                Ask about safety procedures, equipment maintenance or quality limits.
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {STARTERS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => submit(q)}
                    className="min-h-20 rounded-xl border-2 bg-card p-4 text-left text-lg font-medium transition-colors hover:border-hazard active:bg-hazard/20 focus-visible:ring-2 focus-visible:ring-ring outline-none"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <ul className="space-y-6">
              {messages.map((m) => (
                <li key={m.id} className={m.role === "user" ? "flex justify-end" : ""}>
                  {m.role === "user" ? (
                    <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-3 text-lg text-primary-foreground">
                      {m.content}
                    </p>
                  ) : (
                    <Assistant m={m} onRetry={retry} />
                  )}
                </li>
              ))}
            </ul>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <form
        className="border-t bg-card pb-[env(safe-area-inset-bottom)]"
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <div className="mx-auto flex max-w-4xl items-end gap-2 p-3">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit(input);
              }
            }}
            disabled={streaming}
            rows={1}
            placeholder="Ask a question…"
            aria-label="Question"
            className="max-h-40 min-h-14 resize-none text-lg md:text-lg"
          />
          {streaming ? (
            <Button type="button" size="lg" variant="destructive" className="size-14" onClick={stop} aria-label="Stop">
              <Square />
            </Button>
          ) : (
            <Button type="submit" size="lg" className="size-14" disabled={!input.trim()} aria-label="Send">
              <ArrowUp />
            </Button>
          )}
        </div>
      </form>
    </>
  );
}
