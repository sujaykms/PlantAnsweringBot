"""Shared contracts. Frozen after Phase 0 — ingestion, backend and frontend all depend on these."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

DocSource = Literal["safety", "maintenance", "quality"]
RouteLabel = Literal["safety", "maintenance", "quality", "analytics", "none"]
DOC_SOURCES: tuple[DocSource, ...] = ("safety", "maintenance", "quality")


# ---- Routing ----
class RouteScore(BaseModel):
    label: RouteLabel
    confidence: float = Field(ge=0, le=1)


class RouteDecision(BaseModel):
    """Router output after decision rules are applied."""

    routes: list[RouteScore]          # raw ranked model output
    reason: str = ""
    searched: list[RouteLabel]        # labels actually queried
    fallback: bool = False            # True if we widened to all doc indexes
    overridden: bool = False          # True if the user picked the source
    emergency: bool = False           # injury / fire / spill / gas detected in the question
    unsafe: str = "none"              # none | bypass_safety | falsify_records | sabotage | other_harm
    injection: bool = False           # prompt-injection / authority-claim attempt
    physical_work: bool | None = None  # asks to physically work on equipment; None = classifier unavailable
    model: str = ""
    latency_ms: int = 0


# ---- Ingestion ----
class ChunkIn(BaseModel):
    """A chunk ready to be embedded and stored."""

    source: DocSource
    section_path: str                 # "Pump P-101 Manual > 4 Motor > 4.3 Mounting"
    page: int | None = None
    doc_type: str | None = None       # sop | manual | standard | table
    equipment_ids: list[str] = []
    content: str                      # what the LLM sees / user reads
    embed_text: str                   # "[MAINTENANCE] {section_path}\n{content}"


# ---- Retrieval ----
class RetrievedChunk(BaseModel):
    id: UUID
    document_id: UUID
    source: DocSource
    title: str
    section_path: str
    page: int | None = None
    content: str
    score: float                      # hybrid RRF score
    rerank_score: float | None = None


# ---- Analytics (Phase 3) ----
class AnalyticsResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list]
    truncated: bool = False


# ---- API ----
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None
    history: list[ChatTurn] = []
    source_override: list[RouteLabel] | None = None


class FeedbackRequest(BaseModel):
    message_id: UUID
    rating: Literal[-1, 1]
    comment: str | None = None


# ---- SSE events (event name -> data payload) ----
# event: status   data: StatusEvent        (before each stage; answers are BUFFERED and verified,
#                                           so `token` events are emitted only after verification)
# event: route    data: RouteDecision
# event: sources  data: {"chunks": [RetrievedChunk]}
# event: analytics_result data: AnalyticsResult          (Phase 3)
# event: token    data: {"text": str}
# event: done     data: {"conversation_id": UUID, "message_id": UUID, "not_found": bool}
# event: error    data: {"message": str}
class SourcesEvent(BaseModel):
    chunks: list[RetrievedChunk]


class TokenEvent(BaseModel):
    text: str


class StatusEvent(BaseModel):
    stage: Literal["routing", "retrieving", "generating", "verifying"]


class VerificationCheck(BaseModel):
    name: str                         # citation_validity | numeric_grounding | forbidden_advice | safety_tie_in
    passed: bool
    detail: str = ""


class Verification(BaseModel):
    passed: bool
    checks: list[VerificationCheck] = []
    regenerated: bool = False         # answer was regenerated once after a failed check
    replaced: bool = False            # answer was replaced with the not-found fallback


class DoneEvent(BaseModel):
    conversation_id: UUID
    message_id: UUID
    not_found: bool = False
    verification: Verification | None = None
