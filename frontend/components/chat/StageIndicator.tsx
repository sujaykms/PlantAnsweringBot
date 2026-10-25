import type { Stage } from "@/lib/types";

const TEXT: Record<Stage, string> = {
  routing: "Finding the right documents…",
  retrieving: "Searching documents…",
  generating: "Writing answer…",
  verifying: "Checking citations…",
};

export function StageIndicator({ stage }: { stage: Stage }) {
  return (
    <p role="status" aria-live="polite" className="flex min-h-8 items-center gap-2.5 text-[0.95rem]">
      <span className="status-dot size-2 rounded-full bg-brand" aria-hidden />
      <span className="status-text" key={stage}>
        {TEXT[stage]}
      </span>
    </p>
  );
}
