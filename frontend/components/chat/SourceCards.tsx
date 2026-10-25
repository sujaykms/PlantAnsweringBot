"use client";
import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RetrievedChunk } from "@/lib/types";
import { splitSources } from "./cite";
import { styleFor } from "./source";

export const cardDomId = (scope: string, id: string) => `src-${scope}-${id}`;

function SourceCard({
  c,
  scope,
  cited,
  forceOpen,
}: {
  c: RetrievedChunk;
  scope: string;
  cited?: boolean;
  forceOpen?: number;
}) {
  const [open, setOpen] = useState(false);
  const [flash, setFlash] = useState(false);
  const s = styleFor(c.source);
  const score = c.rerank_score ?? c.score;

  useEffect(() => {
    if (!forceOpen) return;
    const t0 = setTimeout(() => {
      setOpen(true);
      setFlash(true);
      document.getElementById(cardDomId(scope, c.id))?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 0);
    const t1 = setTimeout(() => setFlash(false), 1600);
    return () => {
      clearTimeout(t0);
      clearTimeout(t1);
    };
  }, [forceOpen, scope, c.id]);

  return (
    <li
      id={cardDomId(scope, c.id)}
      className={cn("rounded-xl border bg-card/60 transition-shadow", flash && "ring-2 ring-brand")}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex min-h-14 w-full items-start gap-3 rounded-xl p-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={cn("flex items-center gap-1.5 text-xs font-medium", s.text)}>
              <span className="size-1.5 rounded-full bg-current" />
              {s.label}
            </span>
            {cited && (
              <span className="rounded-full border border-brand/40 px-1.5 text-[11px] font-medium text-brand">
                Cited
              </span>
            )}
            <span className="truncate text-sm font-semibold">{c.title}</span>
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {c.section_path}
            {c.page != null && ` · p.${c.page}`}
          </p>
        </div>
        <span className="hidden font-mono text-xs text-muted-foreground sm:inline">{score.toFixed(2)}</span>
        <ChevronDown className={cn("size-5 shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <p className="border-t px-3 py-3 text-sm leading-relaxed whitespace-pre-wrap">{c.content}</p>
      )}
    </li>
  );
}

/** focus: which chunk ids to open + scroll to (n changes on every click). */
export function SourceCards({
  sources,
  answer,
  scope,
  focus,
}: {
  sources: RetrievedChunk[];
  answer: string;
  scope: string;
  focus?: { ids: string[]; n: number } | null;
}) {
  const [open, setOpen] = useState(false);
  const [alsoOpen, setAlsoOpen] = useState(false);
  const { cited, other } = splitSources(answer, sources);

  // Expand the right containers when a citation pill is clicked.
  useEffect(() => {
    if (!focus) return;
    const t = setTimeout(() => {
      setOpen(true);
      if (focus.ids.some((id) => other.some((c) => c.id === id))) setAlsoOpen(true);
    }, 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.n]);

  if (!sources.length) return null;
  const fo = (id: string) => (focus?.ids.includes(id) ? focus.n : undefined);
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex min-h-11 items-center gap-2 rounded-lg px-1 text-sm font-medium text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        <ChevronDown className={cn("size-4 transition-transform", !open && "-rotate-90")} />
        Sources ({sources.length})
        {cited.length > 0 && <span className="font-normal">· {cited.length} cited</span>}
      </button>
      {open && (
        <div className="mt-1 space-y-2">
          {cited.length > 0 && (
            <ul className="space-y-2">
              {cited.map((c) => (
                <SourceCard key={c.id} c={c} scope={scope} cited forceOpen={fo(c.id)} />
              ))}
            </ul>
          )}
          {other.length > 0 &&
            (cited.length > 0 ? (
              <div>
                <button
                  type="button"
                  onClick={() => setAlsoOpen(!alsoOpen)}
                  aria-expanded={alsoOpen}
                  className="flex min-h-11 items-center gap-2 rounded-lg px-1 text-sm font-medium text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  <ChevronDown className={cn("size-4 transition-transform", !alsoOpen && "-rotate-90")} />
                  Also retrieved ({other.length})
                </button>
                {alsoOpen && (
                  <ul className="mt-1 space-y-2">
                    {other.map((c) => (
                      <SourceCard key={c.id} c={c} scope={scope} forceOpen={fo(c.id)} />
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <ul className="space-y-2">
                {other.map((c) => (
                  <SourceCard key={c.id} c={c} scope={scope} forceOpen={fo(c.id)} />
                ))}
              </ul>
            ))}
        </div>
      )}
    </div>
  );
}
