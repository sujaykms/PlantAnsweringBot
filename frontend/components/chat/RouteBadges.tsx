"use client";
import { Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { RouteDecision } from "@/lib/types";
import { styleFor } from "./source";

export function RouteBadges({ route }: { route: RouteDecision }) {
  const searched = route.searched.filter((l) => l !== "none");
  const names = searched.map((l) => styleFor(l).label).join(" + ");
  return (
    <Popover>
      <PopoverTrigger
        className="flex min-h-11 flex-wrap items-center gap-2 rounded-lg px-1 text-left text-sm text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label="Why these sources?"
      >
        <span>{names ? `Searching ${names}` : "No document search"}</span>
        {searched.map((l) => (
          <span
            key={l}
            className={cn(
              "rounded-full border px-2.5 py-0.5 text-xs font-semibold",
              styleFor(l).text,
              styleFor(l).bg,
              styleFor(l).border,
            )}
          >
            {styleFor(l).label}
          </span>
        ))}
        {route.fallback && (
          <span className="rounded-full border border-hazard bg-hazard/20 px-2.5 py-0.5 text-xs font-semibold text-foreground">
            Widened search
          </span>
        )}
        <Info className="size-4" />
      </PopoverTrigger>
      <PopoverContent className="w-80 space-y-2 text-sm">
        <p>{route.reason || "No reason given."}</p>
        <ul className="space-y-1">
          {route.routes.map((r) => (
            <li key={r.label} className="flex justify-between">
              <span className={styleFor(r.label).text}>{styleFor(r.label).label}</span>
              <span className="font-mono">{Math.round(r.confidence * 100)}%</span>
            </li>
          ))}
        </ul>
        {route.fallback && (
          <p className="text-muted-foreground">
            Nothing strong matched, so all document sets were searched.
          </p>
        )}
        {route.overridden && <p className="text-muted-foreground">Sources chosen manually.</p>}
        <p className="font-mono text-xs text-muted-foreground">
          {route.model} · {route.latency_ms} ms
        </p>
      </PopoverContent>
    </Popover>
  );
}
