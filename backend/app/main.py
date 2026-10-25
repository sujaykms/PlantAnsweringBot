import asyncio
import json
import re
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app import answer, embeddings, emergency, graph, store
from app.guards.input import InputRejected, RateLimiter, sanitize_history, validate_message
from app.contracts import ChatRequest, DoneEvent, SourcesEvent, StatusEvent, TokenEvent

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_in_threadpool(embeddings.warm_up)
    app.state.graph = graph.build_graph(await run_in_threadpool(graph.make_checkpointer))
    yield


app = FastAPI(title="Plant Docs Q&A", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(emergency.router)
rate_limiter = RateLimiter(max_requests=20, window_s=60)


def _status(stage: str) -> dict:
    return {"event": "status", "data": StatusEvent(stage=stage).model_dump_json()}


def _word_chunks(text: str, n: int = 4) -> list[str]:
    """Split into pieces of ~n words, preserving whitespace so concatenation is lossless."""
    words = re.findall(r"\S+\s*", text)
    pieces = ["".join(words[i : i + n]) for i in range(0, len(words), n)]
    lead = text[: len(text) - len(text.lstrip())]
    return ([lead + pieces[0]] + pieces[1:]) if lead and pieces else pieces


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    if not rate_limiter.check(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="Too many requests — please wait a moment.")
    try:
        req.message = validate_message(req.message)
    except InputRejected as e:
        raise HTTPException(status_code=422, detail=str(e))
    req.history = sanitize_history(req.history)
    g = app.state.graph
    # History: request-passed (the checkpoint stores per-thread state for inspection/resume).
    cid = req.conversation_id or uuid4()
    cfg = {"configurable": {"thread_id": str(cid)}}

    async def events():
        try:
            state: dict = {}
            route_sent = None
            yield _status("routing")
            inp = graph.initial_input(req.message, req.history, req.source_override)
            async for upd in iterate_in_threadpool(g.stream(inp, cfg, stream_mode="updates")):
                for node, delta in upd.items():
                    if not delta:
                        continue
                    state.update({k: v for k, v in delta.items() if k != "hits"})
                    if node == "route":
                        route_sent = delta["decision"].model_dump_json()
                        yield {"event": "route", "data": route_sent}  # UI shows emergency banner from this
                        if delta["decision"].searched:
                            yield _status("retrieving")
                    elif node == "grade" and graph.after_grade(state) == "generate":
                        yield _status("generating")
                    elif node == "generate":
                        yield _status("verifying")
                    elif node == "verify" and delta.get("retry"):
                        yield _status("generating")
            decision = state["decision"]
            if decision.model_dump_json() != route_sent:  # widened during retries (fallback)
                yield {"event": "route", "data": decision.model_dump_json()}
            chunks = state.get("chunks") or []
            nf = bool(state.get("not_found")) or not decision.searched
            yield {"event": "sources", "data": SourcesEvent(chunks=chunks).model_dump_json()}

            # Answer is released only after generation + verification (buffered delivery).
            text = state.get("answer") or answer.NOT_FOUND_REPLY
            verification = state.get("verification")
            for piece in _word_chunks(text):
                yield {"event": "token", "data": TokenEvent(text=piece).model_dump_json()}
                await asyncio.sleep(0)

            cited = [c.id for c in chunks] if not nf else []
            cid2, mid = await run_in_threadpool(
                store.save_turn, cid, req.message, text, decision, cited, verification
            )
            yield {
                "event": "done",
                "data": DoneEvent(
                    conversation_id=cid2, message_id=mid, not_found=nf, verification=verification
                ).model_dump_json(),
            }
        except Exception as e:
            log.exception("chat failed")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(events())
