import type { StreamEvent, RetrievedChunk } from "./types";

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((res, rej) => {
    const t = setTimeout(res, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      rej(new DOMException("Aborted", "AbortError"));
    });
  });

const chunks: RetrievedChunk[] = [
  {
    id: "c1",
    source: "safety",
    title: "SOP-07 Lockout/Tagout",
    section_path: "SOP-07 > 3 Electrical Isolation > 3.2 PPE",
    page: 6,
    content:
      "Before electrical isolation, wear arc-rated face shield, Class 0 insulated gloves with leather protectors, arc-rated clothing (min 8 cal/cm²) and EH-rated safety footwear.",
    score: 0.82,
    rerank_score: 0.94,
  },
  {
    id: "c2",
    source: "maintenance",
    title: "Pump P-101 Manual",
    section_path: "Pump P-101 Manual > 4 Motor > 4.3 Mounting",
    page: 31,
    content:
      "Isolate and lock out the motor starter at MCC-2 before removing the motor mount bolts. Verify zero energy with a rated voltage tester.",
    score: 0.71,
    rerank_score: 0.78,
  },
  {
    id: "c3",
    source: "safety",
    title: "SOP-07 Lockout/Tagout",
    section_path: "SOP-07 > 4 Verification",
    page: 8,
    content:
      "Test-before-touch: verify absence of voltage using a tester proven on a known source before and after the test.",
    score: 0.64,
    rerank_score: 0.61,
  },
];

const answer = `For electrical isolation you need the following PPE [SOP-07 §3.2]:

- Arc-rated face shield and clothing (minimum 8 cal/cm²)
- Class 0 insulated gloves with leather protectors
- EH-rated safety footwear

Always **lock out the starter** and verify zero voltage before touching conductors [SOP-07 §4]. For the P-101 motor, isolate at MCC-2 [P-101 Manual §4.3].`;

export async function* mockStream(
  message: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  await sleep(300, signal);
  yield {
    event: "route",
    data: {
      routes: [
        { label: "safety", confidence: 0.86 },
        { label: "maintenance", confidence: 0.58 },
      ],
      reason: "Mentions isolation and PPE (safety) plus equipment P-101 (maintenance).",
      searched: ["safety", "maintenance"],
      fallback: false,
      overridden: false,
      model: "mock-router",
      latency_ms: 240,
    },
  };
  await sleep(400, signal);
  yield { event: "sources", data: { chunks } };
  if (/zzz/i.test(message)) {
    yield { event: "token", data: { text: "I could not find this in the plant documents." } };
    yield {
      event: "done",
      data: { conversation_id: "mock-conv", message_id: crypto.randomUUID(), not_found: true },
    };
    return;
  }
  for (const t of answer.match(/\S+\s*|\n+/g) ?? []) {
    await sleep(35, signal);
    yield { event: "token", data: { text: t } };
  }
  yield {
    event: "done",
    data: { conversation_id: "mock-conv", message_id: crypto.randomUUID(), not_found: false },
  };
}
