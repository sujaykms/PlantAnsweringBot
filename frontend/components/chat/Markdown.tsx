"use client";
import ReactMarkdown from "react-markdown";

const CITE = /\[([^\]\n]*§[^\]\n]*)\]/g;

export function Markdown({ text, onCite }: { text: string; onCite?: (cite: string) => void }) {
  const src = text.replace(CITE, (_, c: string) => `[${c}](cite:${encodeURIComponent(c)})`);
  return (
    <div className="space-y-4 text-[1.0625rem] leading-[1.7] [&_strong]:font-semibold [&_li]:pl-1 [&_ol]:list-decimal [&_ol]:pl-6 [&_ul]:list-disc [&_ul]:pl-6 [&_li]:my-1 [&_h1]:text-lg [&_h1]:font-bold [&_h2]:text-lg [&_h2]:font-bold [&_h3]:font-bold [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-sm [&_table]:text-sm">
      <ReactMarkdown
        urlTransform={(u) => (u.startsWith("cite:") ? u : u.startsWith("http") ? u : "")}
        components={{
          a: ({ href, children }) =>
            href?.startsWith("cite:") ? (
              <button
                type="button"
                onClick={() => onCite?.(decodeURIComponent(href.slice(5)))}
                title="Show source"
                className="mx-0.5 inline-block cursor-pointer rounded-full border border-border bg-muted px-2 py-px align-baseline text-[0.75rem] font-medium leading-5 text-foreground/80 outline-none transition-colors hover:border-brand hover:bg-brand/10 hover:text-brand focus-visible:ring-2 focus-visible:ring-brand"
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
