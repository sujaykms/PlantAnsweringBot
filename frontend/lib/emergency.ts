import type { EmergencyAlert, NotifyRequest, NotifyResponse } from "./types";

const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// In-memory store used only in mock mode (NEXT_PUBLIC_MOCK=1).
const mockAlerts: EmergencyAlert[] = [];

export async function notifyOperator(req: NotifyRequest): Promise<NotifyResponse> {
  if (MOCK) {
    await delay(900);
    if (/notifyfail/i.test(req.question)) throw new Error("mock failure");
    const a: EmergencyAlert = {
      id: crypto.randomUUID(),
      created_at: new Date().toISOString(),
      question: req.question,
      location: req.location || null,
      status: "open",
      acknowledged_at: null,
    };
    mockAlerts.unshift(a);
    return { alert_id: a.id, status: "open", created_at: a.created_at };
  }
  const res = await fetch("/api/emergency/notify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function listOpenAlerts(): Promise<EmergencyAlert[]> {
  if (MOCK) {
    await delay(200);
    return mockAlerts.filter((a) => a.status === "open");
  }
  const res = await fetch("/api/emergency/alerts?status=open", { cache: "no-store" });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function ackAlert(id: string): Promise<void> {
  if (MOCK) {
    await delay(300);
    const a = mockAlerts.find((x) => x.id === id);
    if (a) Object.assign(a, { status: "acknowledged", acknowledged_at: new Date().toISOString() });
    return;
  }
  const res = await fetch(`/api/emergency/alerts/${encodeURIComponent(id)}/ack`, { method: "POST" });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
}
