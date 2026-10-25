"use client";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowUp,
  FileQuestion,
  PanelLeft,
  RotateCcw,
  SquarePen,
  Sprout,
  Square,
  X,
} from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useChatStream } from "@/lib/useChatStream";
import { loadChats, saveChats, type SavedChat } from "@/lib/history";
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

const ring = "outline-none focus-visible:ring-2 focus-visible:ring-brand";

function Mark() {
  return (
    <span
      aria-hidden
      className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-brand/12 text-brand ring-1 ring-brand/25"
    >
      <Sprout className="size-4" />
    </span>
  );
}

function Assistant({ m, onRetry }: { m: ChatMessage; onRetry: () => void }) {
  const [focus, setFocus] = useState<{ ids: string[]; n: number } | null>(null);
  const onCite = (cite: string) => {
    const ids = (m.sources ?? []).filter((c) => citeMatches(cite, c)).map((c) => c.id);
    if (ids.length) setFocus((f) => ({ ids, n: (f?.n ?? 0) + 1 }));
  };
  return (
    <div className="flex gap-3 sm:gap-4">
      <Mark />
      <div className="min-w-0 flex-1">
        {m.route?.emergency && (
          <EmergencyBanner
            question={m.question ?? ""}
            conversationId={m.conversationId}
            messageId={m.messageId}
          />
        )}
        {m.route && <RouteBadges route={m.route} />}
        {m.notFound ? (
          <div className="flex gap-3 rounded-2xl border border-dashed border-hazard bg-hazard/10 p-4">
            <FileQuestion className="mt-0.5 size-5 shrink-0" />
            <div>
              <p className="font-semibold">Not found in the plant documents</p>
              <p className="text-[0.95rem] text-muted-foreground">
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
        {m.error && (
          <div
            role="alert"
            className="mt-2 flex flex-wrap items-center gap-3 rounded-2xl border-2 border-destructive bg-destructive/10 p-3"
          >
            <AlertTriangle className="size-5 text-destructive" />
            <span className="flex-1 text-sm">{m.error}</span>
            <button
              type="button"
              onClick={onRetry}
              className={cn(
                "flex min-h-11 items-center gap-2 rounded-full border bg-background px-4 text-sm font-medium hover:bg-muted",
                ring,
              )}
            >
              <RotateCcw className="size-4" /> Retry
            </button>
          </div>
        )}
        {m.sources && (
          <SourceCards sources={m.sources} answer={m.content} scope={m.id} focus={focus} />
        )}
      </div>
    </div>
  );
}

export function Chat() {
  const { messages, streaming, send, retry, stop, reset, restore, getConvId } = useChatStream();
  const [input, setInput] = useState("");
  const [chats, setChats] = useState<SavedChat[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [chatId, setChatId] = useState("initial-chat");
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      setChats(loadChats());
      setLoaded(true);
    }, 0);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  // Persist finished conversations (never while a reply is streaming).
  useEffect(() => {
    if (!loaded || streaming || messages.length === 0) return;
    const t = setTimeout(() => {
      setChats((cs) => {
        const first = messages.find((m) => m.role === "user")?.content ?? "New chat";
        const entry: SavedChat = {
          id: chatId,
          title: first.slice(0, 80),
          updated: Date.now(),
          convId: getConvId(),
          messages: messages.map((m) => ({ ...m, streaming: false })),
        };
        const next = [entry, ...cs.filter((c) => c.id !== chatId)].slice(0, 40);
        saveChats(next);
        return next;
      });
    }, 0);
    return () => clearTimeout(t);
  }, [messages, streaming, loaded, chatId, getConvId]);

  // Auto-grow composer up to ~6 lines.
  useLayoutEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [input]);

  const submit = (t: string) => {
    if (!t.trim() || streaming) return;
    send(t);
    setInput("");
  };

  const newChat = () => {
    reset();
    setChatId(crypto.randomUUID());
    setInput("");
    setDrawer(false);
    taRef.current?.focus();
  };
  const openChat = (c: SavedChat) => {
    if (streaming) return;
    restore(c.messages, c.convId);
    setChatId(c.id);
    setDrawer(false);
  };
  const removeChat = (id: string) => {
    setChats((cs) => {
      const next = cs.filter((c) => c.id !== id);
      saveChats(next);
      return next;
    });
    if (id === chatId) newChat();
  };

  return (
    <div className="flex h-dvh">
      {drawer && (
        <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setDrawer(false)} aria-hidden />
      )}
      <aside
        aria-label="Conversations"
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r bg-sidebar pt-[env(safe-area-inset-top)] transition-transform duration-200 md:static md:z-auto md:translate-x-0 md:transition-none",
          drawer ? "translate-x-0" : "-translate-x-full",
          collapsed && "md:hidden",
        )}
      >
        <div className="flex items-center gap-1 p-3">
          <button
            type="button"
            onClick={newChat}
            className={cn(
              "flex min-h-11 flex-1 items-center gap-2 rounded-xl px-3 text-[0.95rem] font-medium transition-colors hover:bg-muted",
              ring,
            )}
          >
            <SquarePen className="size-4" /> New chat
          </button>
          <button
            type="button"
            onClick={() => {
              setDrawer(false);
              setCollapsed(true);
            }}
            aria-label="Close sidebar"
            className={cn("flex size-11 items-center justify-center rounded-xl text-muted-foreground hover:bg-muted", ring)}
          >
            <PanelLeft className="size-5" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 pb-3" aria-label="Past chats">
          {chats.length > 0 && <p className="px-3 py-2 text-xs text-muted-foreground">Recent</p>}
          <ul>
            {chats.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  type="button"
                  onClick={() => openChat(c)}
                  aria-current={c.id === chatId ? "true" : undefined}
                  className={cn(
                    "flex min-h-11 w-full items-center rounded-xl py-2 pr-11 pl-3 text-left text-[0.9rem] transition-colors hover:bg-muted",
                    c.id === chatId && "bg-muted font-medium",
                    ring,
                  )}
                >
                  <span className="line-clamp-1">{c.title}</span>
                </button>
                <button
                  type="button"
                  onClick={() => removeChat(c.id)}
                  aria-label={`Delete chat: ${c.title}`}
                  className={cn(
                    "absolute top-0 right-0 flex size-11 items-center justify-center rounded-xl text-muted-foreground opacity-100 hover:text-foreground md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100",
                    ring,
                  )}
                >
                  <X className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center justify-between border-t p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
          <a href="/operator" className={cn("flex min-h-11 items-center rounded-xl px-3 text-sm text-muted-foreground hover:text-foreground", ring)}>
            Operator alerts
          </a>
          <ThemeToggle />
        </div>
      </aside>

      <div className="relative flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-1 px-2 py-2 pt-[max(0.5rem,env(safe-area-inset-top))]">
          <button
            type="button"
            onClick={() => {
              setDrawer(true);
              setCollapsed(false);
            }}
            aria-label="Open sidebar"
            className={cn(
              "flex size-11 items-center justify-center rounded-xl text-muted-foreground hover:bg-muted",
              !collapsed && "md:hidden",
              ring,
            )}
          >
            <PanelLeft className="size-5" />
          </button>
          <p className="flex-1 truncate px-2 text-[0.95rem] font-medium text-muted-foreground">
            Plant Docs Assistant
          </p>
          <ThemeToggle className={cn(!collapsed && "md:hidden")} />
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[46rem] px-4 pt-4 pb-8">
            {messages.length === 0 ? (
              <section className="flex min-h-[55vh] flex-col items-center justify-center text-center">
                <span className="mb-5 flex size-12 items-center justify-center rounded-full bg-brand/12 text-brand ring-1 ring-brand/25">
                  <Sprout className="size-6" />
                </span>
                <h1 className="text-[1.75rem] leading-tight font-semibold tracking-tight sm:text-3xl">
                  What do you need to know?
                </h1>
                <p className="mt-2 text-muted-foreground">
                  Ask about safety procedures, equipment maintenance or quality limits.
                </p>
                <div className="mt-8 grid w-full gap-2 text-left sm:grid-cols-2">
                  {STARTERS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => submit(q)}
                      className={cn(
                        "min-h-14 rounded-2xl border px-4 text-left py-3 text-[0.95rem] leading-snug transition-colors hover:bg-muted active:bg-muted",
                        ring,
                      )}
                    >
                      {q}
                    </button>
                  ))}
                </div>
                <ul
                  aria-label="Source legend"
                  className="mt-8 flex flex-wrap justify-center gap-x-5 gap-y-1 text-xs text-muted-foreground"
                >
                  {Object.entries(SOURCE_STYLE).map(([k, s]) => (
                    <li key={k} className="flex items-center gap-1.5">
                      <span className={cn("size-2 rounded-full bg-current", s.text)} />
                      {s.label}
                    </li>
                  ))}
                </ul>
              </section>
            ) : (
              <ul className="space-y-8">
                {messages.map((m) => (
                  <li key={m.id} className={m.role === "user" ? "flex justify-end" : ""}>
                    {m.role === "user" ? (
                      <p className="max-w-[85%] rounded-3xl bg-user-bubble px-4 py-2.5 text-[1.0625rem] leading-relaxed break-words whitespace-pre-wrap">
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
          className="px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
          onSubmit={(e) => {
            e.preventDefault();
            submit(input);
          }}
        >
          <div className="mx-auto w-full max-w-[46rem]">
            <div className="flex items-end gap-2 rounded-[1.75rem] border bg-card py-2 pr-2 pl-5 shadow-[0_2px_16px_-4px_rgb(0_0_0/0.12)] transition-shadow focus-within:border-brand/60 focus-within:shadow-[0_2px_20px_-4px_rgb(0_0_0/0.18)]">
              <textarea
                ref={taRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    submit(input);
                  }
                }}
                rows={1}
                placeholder="Ask about a procedure, fault code or limit…"
                aria-label="Question"
                className="max-h-[10.5rem] min-h-11 flex-1 resize-none bg-transparent py-2.5 text-[1.0625rem] leading-6 outline-none placeholder:text-muted-foreground"
              />
              {streaming ? (
                <button
                  type="button"
                  onClick={stop}
                  aria-label="Stop generating"
                  className={cn(
                    "flex size-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground",
                    ring,
                  )}
                >
                  <Square className="size-4 fill-current" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  aria-label="Send"
                  className={cn(
                    "flex size-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-opacity disabled:opacity-30",
                    ring,
                  )}
                >
                  <ArrowUp className="size-5" />
                </button>
              )}
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Answers come from plant documents. Check the cited source before safety-critical work.
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
