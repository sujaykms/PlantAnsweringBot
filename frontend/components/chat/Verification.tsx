import { CheckCircle2, TriangleAlert } from "lucide-react";
import type { Verification } from "@/lib/types";

export function VerificationNotice({ v }: { v: Verification | null | undefined }) {
  if (!v) return null;
  if (!v.passed || v.replaced) {
    return (
      <div
        role="status"
        className="mt-3 flex gap-2.5 rounded-xl border border-hazard/70 bg-hazard/10 px-3 py-2.5 text-sm"
      >
        <TriangleAlert className="mt-0.5 size-4 shrink-0" />
        <p>
          <span className="font-semibold">Couldn&apos;t verify this answer against the documents</span> —
          check the sources below.
        </p>
      </div>
    );
  }
  return (
    <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
      <CheckCircle2 className="size-3.5 text-quality" /> Citations verified
    </p>
  );
}
