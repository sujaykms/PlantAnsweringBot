"use client";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RetrievedChunk } from "@/lib/types";
import { styleFor } from "./source";

function SourceCard({ c }: { c: RetrievedChunk }) {
  const [open, setOpen] = useState(false);
  const s = styleFor(c.source);
  const score = c.rerank_score ?? c.score;
  return (
    <li className={cn("rounded-xl border-l-4 border bg-card", s.border)}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex min-h-14 w-full items-start gap-3 rounded-xl p-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={cn("text-xs font-semibold", s.text)}>{s.label}</span>
            <span className="truncate text-sm font-semibold">{c.title}</span>
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {c.section_path}
            {c.page != null && ` · p.${c.page}`}
          </p>
        </div>
        <span className="font-mono text-xs text-muted-foreground">{score.toFixed(2)}</span>
        <ChevronDown className={cn("size-5 shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <p className="border-t px-3 py-3 text-sm leading-relaxed whitespace-pre-wrap">
          {c.content}
        </p>
      )}
    </li>
  );
}

export function SourceCards({ sources }: { sources: RetrievedChunk[] }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) return null;
  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex min-h-11 items-center gap-2 rounded-lg px-1 text-sm font-medium text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronDown className={cn("size-4 transition-transform", !open && "-rotate-90")} />
        {sources.length} source{sources.length > 1 && "s"}
      </button>
      {open && (
        <ul className="mt-1 space-y-2">
          {sources.map((c) => (
            <SourceCard key={c.id} c={c} />
          ))}
        </ul>
      )}
    </div>
  );
}
