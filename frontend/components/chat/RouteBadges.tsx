"use client";
import { Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { RouteDecision } from "@/lib/types";
import { styleFor } from "./source";

export function RouteBadges({ route }: { route: RouteDecision }) {
  const searched = route.searched.filter((l) => l !== "none");
  const names = searched.map((l) => styleFor(l).label).join(" · ");
  return (
    <Popover>
      <PopoverTrigger
        className="-ml-2 mb-1 flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-left text-[0.8125rem] text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-brand"
        aria-label="Why these sources?"
      >
        <span>{names ? `Searched ${names}` : "No document search"}</span>
        {route.fallback && <span>· widened search</span>}
        <Info className="size-3.5" />
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
