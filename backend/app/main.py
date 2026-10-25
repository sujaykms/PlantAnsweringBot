import json
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from app import answer, embeddings, graph, store
from app.contracts import ChatRequest, DoneEvent, SourcesEvent, TokenEvent

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_in_threadpool(embeddings.warm_up)
    app.state.graph = graph.build_graph(await run_in_threadpool(graph.make_checkpointer))
    yield


app = FastAPI(title="Plant Docs Q&A", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    g = app.state.graph
    # History: request-passed (the checkpoint stores per-thread state for inspection/resume).
    cid = req.conversation_id or uuid4()
    cfg = {"configurable": {"thread_id": str(cid)}}

    async def events():
        try:
            state: dict = {}
            route_sent = None
            inp = graph.initial_input(req.message, req.history, req.source_override)
            async for upd in iterate_in_threadpool(g.stream(inp, cfg, stream_mode="updates")):
                for node, delta in upd.items():
                    if not delta:
                        continue
                    state.update({k: v for k, v in delta.items() if k != "hits"})
                    if node == "route":
                        route_sent = delta["decision"].model_dump_json()
                        yield {"event": "route", "data": route_sent}
            decision = state["decision"]
            if decision.model_dump_json() != route_sent:  # widened during retries (fallback)
                yield {"event": "route", "data": decision.model_dump_json()}
            chunks = state.get("chunks") or []
            not_found = bool(state.get("not_found"))
            yield {"event": "sources", "data": SourcesEvent(chunks=chunks).model_dump_json()}

            parts: list[str] = []
            if state.get("answer"):  # canned reply from the graph
                gen = iter([state["answer"]])
            else:
                gen = answer.stream_answer(req.message, chunks, decision, not_found, req.history)
            async for tok in iterate_in_threadpool(gen):
                parts.append(tok)
                yield {"event": "token", "data": TokenEvent(text=tok).model_dump_json()}

            nf = not_found or not decision.searched
            cited = [c.id for c in chunks] if not nf else []
            cid2, mid = await run_in_threadpool(
                store.save_turn, cid, req.message, "".join(parts), decision, cited
            )
            yield {
                "event": "done",
                "data": DoneEvent(conversation_id=cid2, message_id=mid, not_found=nf).model_dump_json(),
            }
        except Exception as e:
            log.exception("chat failed")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(events())
