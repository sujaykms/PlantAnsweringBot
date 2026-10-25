import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Stage } from "@/lib/types";

const STAGES: { id: Stage; label: string }[] = [
  { id: "routing", label: "Routing" },
  { id: "retrieving", label: "Retrieving" },
  { id: "generating", label: "Generating" },
  { id: "verifying", label: "Verifying" },
];

export function StageIndicator({ stage }: { stage: Stage }) {
  const cur = STAGES.findIndex((s) => s.id === stage);
  return (
    <ol
      aria-label="Progress"
      aria-live="polite"
      className="mt-1 flex flex-wrap items-center gap-x-1 gap-y-1 text-sm"
    >
      {STAGES.map((s, i) => {
        const done = i < cur;
        const active = i === cur;
        return (
          <li key={s.id} className="flex items-center gap-1" aria-current={active ? "step" : undefined}>
            <span
              className={cn(
                "flex min-h-8 items-center gap-1.5 rounded-full border px-3 py-1 font-medium transition-colors",
                active && "border-hazard bg-hazard/20 text-foreground",
                done && "border-transparent text-muted-foreground",
                !active && !done && "border-transparent text-muted-foreground/60",
              )}
            >
              {done ? (
                <Check className="size-3.5" />
              ) : (
                <span
                  className={cn(
                    "size-2 rounded-full",
                    active ? "animate-pulse bg-hazard" : "bg-muted-foreground/40",
                  )}
                />
              )}
              {s.label}
              {active && <span className="animate-pulse">…</span>}
            </span>
            {i < STAGES.length - 1 && <span className="text-muted-foreground/40">›</span>}
          </li>
        );
      })}
    </ol>
  );
}
