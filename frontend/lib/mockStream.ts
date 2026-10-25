import type { StreamEvent, RetrievedChunk, Verification } from "./types";

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
  {
    id: "c4",
    source: "quality",
    title: "QS-12 Weld Inspection",
    section_path: "QS-12 > 2 Visual Criteria",
    page: 3,
    content: "Visual weld inspection: no undercut deeper than 0.5 mm; no surface porosity.",
    score: 0.41,
    rerank_score: 0.38,
  },
];

const answer = `For electrical isolation you need the following PPE [SOP-07 §3.2]:

- Arc-rated face shield and clothing (minimum 8 cal/cm²)
- Class 0 insulated gloves with leather protectors
- EH-rated safety footwear

Always **lock out the starter** and verify zero voltage before touching conductors [SOP-07 §4]. For the P-101 motor, isolate at MCC-2 [P-101 Manual §4.3].`;


const emergencyAnswer = `Apply firm direct pressure to the wound with a clean cloth and keep the person still [SOP-07 §3.2]. Do not restart or approach the equipment until it is isolated [SOP-07 §4].`;

export async function* mockStream(
  message: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const emergency = /bleeding|fire/i.test(message);
  const verifyFail = /verifyfail/i.test(message);
  const notFound = /zzz/i.test(message);
  yield { event: "status", data: { stage: "routing" } };
  await sleep(700, signal);
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
      emergency,
    },
  };
  yield { event: "status", data: { stage: "retrieving" } };
  await sleep(900, signal);
  yield { event: "sources", data: { chunks } };
  yield { event: "status", data: { stage: "generating" } };
  await sleep(1200, signal);
  yield { event: "status", data: { stage: "verifying" } };
  await sleep(1000, signal);
  const done = (not_found: boolean, verification: Verification | null): StreamEvent => ({
    event: "done",
    data: {
      conversation_id: "mock-conv",
      message_id: crypto.randomUUID(),
      not_found,
      verification,
    },
  });
  const ok = (regenerated = false, replaced = false): Verification => ({
    passed: !replaced,
    checks: [],
    regenerated,
    replaced,
  });
  if (notFound) {
    yield { event: "token", data: { text: "I could not find this in the plant documents." } };
    yield done(true, null);
    return;
  }
  const text = emergency ? emergencyAnswer : answer;
  for (const t of text.match(/\S+\s*|\n+/g) ?? []) {
    await sleep(35, signal);
    yield { event: "token", data: { text: t } };
  }
  yield done(
    false,
    verifyFail
      ? { passed: false, checks: [{ name: "numeric_grounding", passed: false, detail: "8 cal/cm² not found" }], regenerated: true, replaced: false }
      : ok(/regen/i.test(message)),
  );
}
