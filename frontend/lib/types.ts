export type DocSource = "safety" | "maintenance" | "quality";
export type RouteLabel = DocSource | "analytics" | "none";

export interface RouteDecision {
  routes: { label: RouteLabel; confidence: number }[];
  reason: string;
  searched: RouteLabel[];
  fallback: boolean;
  overridden: boolean;
  model: string;
  latency_ms: number;
  emergency?: boolean;
}

export interface RetrievedChunk {
  id: string;
  document_id?: string;
  source: DocSource;
  title: string;
  section_path: string;
  page: number | null;
  content: string;
  score: number;
  rerank_score: number | null;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export type Stage = "routing" | "retrieving" | "generating" | "verifying";

export interface VerificationCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface Verification {
  passed: boolean;
  checks: VerificationCheck[];
  regenerated: boolean;
  replaced: boolean;
}

export interface DoneEvent {
  conversation_id: string;
  message_id: string;
  not_found: boolean;
  verification?: Verification | null;
}

export interface NotifyRequest {
  conversation_id?: string;
  message_id?: string;
  question: string;
  location?: string;
}

export interface NotifyResponse {
  alert_id: string;
  status: "open";
  created_at: string;
}

export interface EmergencyAlert {
  id: string;
  created_at: string;
  question: string;
  location: string | null;
  status: "open" | "acknowledged";
  acknowledged_at: string | null;
}

export type StreamEvent =
  | { event: "status"; data: { stage: Stage } }
  | { event: "route"; data: RouteDecision }
  | { event: "sources"; data: { chunks: RetrievedChunk[] } }
  | { event: "token"; data: { text: string } }
  | { event: "done"; data: DoneEvent }
  | { event: "error"; data: { message: string } };

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  route?: RouteDecision;
  sources?: RetrievedChunk[];
  notFound?: boolean;
  error?: string;
  streaming?: boolean;
  stage?: Stage;
  question?: string;
  conversationId?: string;
  messageId?: string;
  verification?: Verification | null;
}
