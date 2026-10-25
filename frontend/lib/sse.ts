import type { StreamEvent } from "./types";

function parseFrame(frame: string): StreamEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const i = line.indexOf(":");
    const field = i === -1 ? line : line.slice(0, i);
    let value = i === -1 ? "" : line.slice(i + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) } as StreamEvent;
  } catch {
    return null;
  }
}

/** Incrementally parse an SSE byte stream; handles frames split across chunks. */
export async function* parseSSE(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      buf += decoder.decode(value, { stream: !done });
      buf = buf.replace(/\r\n?/g, "\n");
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const ev = parseFrame(buf.slice(0, idx));
        buf = buf.slice(idx + 2);
        if (ev) yield ev;
      }
      if (done) break;
    }
    if (buf.trim()) {
      const ev = parseFrame(buf);
      if (ev) yield ev;
    }
  } finally {
    reader.releaseLock();
  }
}
