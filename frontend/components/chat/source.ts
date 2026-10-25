import type { RouteLabel } from "@/lib/types";

export const SOURCE_STYLE: Record<
  string,
  { label: string; text: string; bg: string; border: string }
> = {
  safety: {
    label: "Safety",
    text: "text-safety",
    bg: "bg-safety/12",
    border: "border-safety/50",
  },
  maintenance: {
    label: "Maintenance",
    text: "text-maintenance",
    bg: "bg-maintenance/12",
    border: "border-maintenance/50",
  },
  quality: {
    label: "Quality",
    text: "text-quality",
    bg: "bg-quality/12",
    border: "border-quality/50",
  },
};

export const styleFor = (l: RouteLabel | string) =>
  SOURCE_STYLE[l] ?? {
    label: l,
    text: "text-muted-foreground",
    bg: "bg-muted",
    border: "border-border",
  };
