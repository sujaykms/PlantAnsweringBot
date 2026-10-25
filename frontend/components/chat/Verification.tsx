import { CheckCircle2, TriangleAlert } from "lucide-react";
import type { Verification } from "@/lib/types";

export function VerificationNotice({ v }: { v: Verification | null | undefined }) {
  if (!v) return null;
  if (!v.passed || v.replaced) {
    return (
      <div
        role="status"
        className="mt-3 flex gap-3 rounded-xl border-2 border-hazard bg-hazard/15 p-3 text-sm"
      >
        <TriangleAlert className="mt-0.5 size-5 shrink-0" />
        <p>
          <span className="font-semibold">Couldn&apos;t verify this answer against the documents</span> —
          check the sources below.
        </p>
      </div>
    );
  }
  return (
    <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
      <CheckCircle2 className="size-3.5 text-safety" /> Citations verified
    </p>
  );
}
