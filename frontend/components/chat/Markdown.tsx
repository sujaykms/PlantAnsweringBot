"use client";
import ReactMarkdown from "react-markdown";

const CITE = /\[([^\]\n]*§[^\]\n]*)\]/g;

export function Markdown({ text, onCite }: { text: string; onCite?: (cite: string) => void }) {
  const src = text.replace(CITE, (_, c: string) => `[${c}](cite:${encodeURIComponent(c)})`);
  return (
    <div className="space-y-3 text-base leading-relaxed [&_ol]:list-decimal [&_ol]:pl-6 [&_ul]:list-disc [&_ul]:pl-6 [&_li]:my-1 [&_h1]:text-lg [&_h1]:font-bold [&_h2]:text-lg [&_h2]:font-bold [&_h3]:font-bold [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-sm [&_table]:text-sm">
      <ReactMarkdown
        urlTransform={(u) => (u.startsWith("cite:") ? u : u.startsWith("http") ? u : "")}
        components={{
          a: ({ href, children }) =>
            href?.startsWith("cite:") ? (
              <button
                type="button"
                onClick={() => onCite?.(decodeURIComponent(href.slice(5)))}
                title="Show source"
                className="mx-0.5 inline-block min-h-6 cursor-pointer rounded-md border border-maintenance/40 bg-maintenance/10 px-1.5 py-0.5 align-baseline font-mono text-xs font-semibold text-maintenance outline-none hover:bg-maintenance/20 focus-visible:ring-2 focus-visible:ring-ring"
              >
                {children}
              </button>
            ) : (
              <a href={href} className="underline" target="_blank" rel="noreferrer">
                {children}
              </a>
            ),
        }}
      >
        {src}
      </ReactMarkdown>
    </div>
  );
}
