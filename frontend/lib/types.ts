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

export interface DoneEvent {
  conversation_id: string;
  message_id: string;
  not_found: boolean;
}

export type StreamEvent =
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
}
