import type { RetrievedChunk } from "@/lib/types";

const CITE = /\[([^\]\n]*§[^\]\n]*)\]/g;

export function parseCitations(text: string): string[] {
  return [...text.matchAll(CITE)].map((m) => m[1].trim());
}

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();

/** Does a citation like "SOP-07 §3.2" refer to this chunk? */
export function citeMatches(cite: string, c: RetrievedChunk): boolean {
  const [docRaw, ...rest] = cite.split("§");
  const doc = norm(docRaw);
  const sec = norm(rest.join("§"));
  const title = norm(c.title);
  const path = norm(c.section_path);
  const docOk = !doc || title.includes(doc) || doc.includes(title) || path.startsWith(doc);
  if (!docOk) return false;
  if (!sec) return true;
  const esc = sec.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[\\s>])${esc}([.\\s>]|$)`).test(path);
}

export function splitSources(text: string, sources: RetrievedChunk[]) {
  const cites = parseCitations(text);
  const cited = sources.filter((c) => cites.some((k) => citeMatches(k, c)));
  const ids = new Set(cited.map((c) => c.id));
  return { cited, other: sources.filter((c) => !ids.has(c.id)) };
}
