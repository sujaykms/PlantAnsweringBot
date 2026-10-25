"use client";
import { useCallback, useRef, useState } from "react";
import { parseSSE } from "./sse";
import { mockStream } from "./mockStream";
import type { ChatMessage, ChatTurn, StreamEvent } from "./types";

const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";
const uid = () => crypto.randomUUID();

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const convId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const run = useCallback(async (message: string, prior: ChatMessage[]) => {
    const history: ChatTurn[] = prior
      .filter((m) => m.content && !m.error)
      .map((m) => ({ role: m.role, content: m.content }));
    const aid = uid();
    setMessages([
      ...prior,
      { id: uid(), role: "user", content: message },
      { id: aid, role: "assistant", content: "", streaming: true, question: message, stage: "routing" },
    ]);
    const patch = (f: (m: ChatMessage) => ChatMessage) =>
      setMessages((ms) => ms.map((m) => (m.id === aid ? f(m) : m)));
    const ctl = new AbortController();
    abort.current = ctl;
    setStreaming(true);
    try {
      let events: AsyncIterable<StreamEvent>;
      if (MOCK) events = mockStream(message, ctl.signal);
      else {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({
            message,
            history,
            ...(convId.current ? { conversation_id: convId.current } : {}),
          }),
          signal: ctl.signal,
        });
        if (!res.ok || !res.body) throw new Error(`Server returned ${res.status}`);
        events = parseSSE(res.body);
      }
      for await (const ev of events) {
        if (ev.event === "status") patch((m) => ({ ...m, stage: ev.data.stage }));
        else if (ev.event === "route") patch((m) => ({ ...m, route: ev.data }));
        else if (ev.event === "sources") patch((m) => ({ ...m, sources: ev.data.chunks }));
        else if (ev.event === "token") patch((m) => ({ ...m, content: m.content + ev.data.text }));
        else if (ev.event === "done") {
          convId.current = ev.data.conversation_id;
          patch((m) => ({
            ...m,
            streaming: false,
            notFound: ev.data.not_found,
            conversationId: ev.data.conversation_id,
            messageId: ev.data.message_id,
            verification: ev.data.verification ?? null,
          }));
        } else if (ev.event === "error") {
          patch((m) => ({ ...m, streaming: false, error: ev.data.message }));
        }
      }
      patch((m) => ({ ...m, streaming: false }));
    } catch (e) {
      const aborted = (e as Error).name === "AbortError";
      patch((m) => ({
        ...m,
        streaming: false,
        error: aborted ? undefined : (e as Error).message || "Connection failed",
        content: aborted && !m.content ? "(stopped)" : m.content,
      }));
    } finally {
      setStreaming(false);
      abort.current = null;
    }
  }, []);

  const send = useCallback(
    (text: string) => {
      const t = text.trim();
      if (!t || streaming) return;
      void run(t, messages);
    },
    [messages, streaming, run],
  );

  const retry = useCallback(() => {
    if (streaming) return;
    const i = messages.length - 2;
    if (i < 0 || messages[i].role !== "user") return;
    void run(messages[i].content, messages.slice(0, i));
  }, [messages, streaming, run]);

  const stop = useCallback(() => abort.current?.abort(), []);
  const reset = useCallback(() => {
    abort.current?.abort();
    convId.current = null;
    setMessages([]);
  }, []);

  const restore = useCallback((msgs: ChatMessage[], cid: string | null) => {
    abort.current?.abort();
    convId.current = cid;
    setMessages(msgs);
  }, []);
  const getConvId = useCallback(() => convId.current, []);

  return { messages, streaming, send, retry, stop, reset, restore, getConvId };
}
