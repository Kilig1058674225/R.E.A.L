from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import repository
from app.config import get_settings, load_env_file
from app.db import get_db, init_db
from app.models import (
    AgentChatRequest,
    AgentChatResponse,
    AgentReplyRequest,
    AgentReplyResponse,
    ConversationMessage,
    DecisionCase,
    DecisionCaseCreate,
    DecisionCaseUpdate,
    DecisionOption,
    DecisionBrief,
    DecisionState,
    DecisionActionPlan,
    EvaluationRequest,
    EvaluationResponse,
    EvidenceItem,
    EvidenceSearchRequest,
    JournalCreate,
    JournalEntry,
    JournalReview,
    JournalUpdate,
    LLMConfigStatus,
    MessageCreate,
    OptionCreate,
)
from app.services.decision_agent import generate_reply, generate_reply_stream
from app.services.decision_brief import build_decision_brief
from app.services.decision_engine import evaluate
from app.services.decision_memory import build_decision_state
from app.services.decision_plan import build_action_plan, create_journal_from_brief
from app.services.decision_review import build_case_reviews, build_due_reviews
from app.services.llm import LLMConfigurationError, LLMRequestError
from app.services.smart_search import SmartSearchError, run_search


STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_env_file()
    init_db()
    yield


app = FastAPI(title="REAL Decision Agent", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def db():
    with get_db() as conn:
        yield conn


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/llm/config", response_model=LLMConfigStatus)
def llm_config() -> LLMConfigStatus:
    settings = get_settings()
    return LLMConfigStatus(
        configured=settings.llm_configured,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key_set=bool(settings.llm_api_key),
    )


@app.post("/api/cases", response_model=DecisionCase)
def create_case(payload: DecisionCaseCreate, conn=Depends(db)):
    return repository.create_case(conn, payload)


@app.get("/api/cases", response_model=list[DecisionCase])
def list_cases(conn=Depends(db)):
    return repository.list_cases(conn)


@app.get("/api/cases/{case_id}", response_model=DecisionCase)
def get_case(case_id: int, conn=Depends(db)):
    try:
        return repository.get_case(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.get("/api/cases/{case_id}/state", response_model=DecisionState)
def get_case_state(case_id: int, conn=Depends(db)):
    try:
        return build_decision_state(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.get("/api/cases/{case_id}/brief", response_model=DecisionBrief)
def get_case_brief(case_id: int, conn=Depends(db)):
    try:
        return build_decision_brief(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.get("/api/cases/{case_id}/action-plan", response_model=DecisionActionPlan)
def get_case_action_plan(case_id: int, conn=Depends(db)):
    try:
        return build_action_plan(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.patch("/api/cases/{case_id}", response_model=DecisionCase)
def update_case(case_id: int, payload: DecisionCaseUpdate, conn=Depends(db)):
    try:
        return repository.update_case(conn, case_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: int, conn=Depends(db)):
    try:
        repository.delete_case(conn, case_id)
        return Response(status_code=204)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.post("/api/cases/{case_id}/messages", response_model=ConversationMessage)
def add_message(case_id: int, payload: MessageCreate, conn=Depends(db)):
    try:
        return repository.add_message(conn, case_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.get("/api/cases/{case_id}/messages", response_model=list[ConversationMessage])
def list_messages(case_id: int, conn=Depends(db)):
    try:
        return repository.list_messages(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.post("/api/cases/{case_id}/agent/respond", response_model=AgentReplyResponse)
def agent_respond(case_id: int, payload: AgentReplyRequest, conn=Depends(db)):
    try:
        message = generate_reply(conn, case_id, payload)
        settings = get_settings()
        used_evidence_count = len(repository.list_evidence(conn, case_id))
        return AgentReplyResponse(
            message=message,
            model=settings.llm_model,
            used_evidence_count=used_evidence_count,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/cases/{case_id}/agent/message", response_model=AgentChatResponse)
def agent_message(case_id: int, payload: AgentChatRequest, conn=Depends(db)):
    try:
        user_message = repository.add_message(conn, case_id, MessageCreate(role="user", content=payload.content))
        assistant_message = generate_reply(
            conn,
            case_id,
            AgentReplyRequest(recent_message_limit=payload.recent_message_limit),
        )
        settings = get_settings()
        return AgentChatResponse(
            user_message=user_message,
            assistant_message=assistant_message,
            model=settings.llm_model,
            used_evidence_count=len(repository.list_evidence(conn, case_id)),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def sse_event(event_type: str, data: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_agent_reply(conn, case_id: int, payload: AgentReplyRequest) -> Iterator[str]:
    try:
        for chunk in generate_reply_stream(conn, case_id, payload):
            yield sse_event("delta", {"content": chunk})
        yield sse_event("done", {"ok": True})
    except LLMConfigurationError as exc:
        yield sse_event("error", {"detail": str(exc)})
    except LLMRequestError as exc:
        yield sse_event("error", {"detail": str(exc)})
    except KeyError:
        yield sse_event("error", {"detail": "Decision case not found"})


@app.post("/api/cases/{case_id}/agent/respond/stream")
def agent_respond_stream(case_id: int, payload: AgentReplyRequest, conn=Depends(db)):
    try:
        repository.get_case(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc
    return StreamingResponse(
        stream_agent_reply(conn, case_id, payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/cases/{case_id}/agent/message/stream")
def agent_message_stream(case_id: int, payload: AgentChatRequest, conn=Depends(db)):
    try:
        repository.add_message(conn, case_id, MessageCreate(role="user", content=payload.content))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc
    return StreamingResponse(
        stream_agent_reply(
            conn,
            case_id,
            AgentReplyRequest(recent_message_limit=payload.recent_message_limit),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/cases/{case_id}/options", response_model=DecisionOption)
def add_option(case_id: int, payload: OptionCreate, conn=Depends(db)):
    try:
        return repository.add_option(conn, case_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.get("/api/cases/{case_id}/options", response_model=list[DecisionOption])
def list_options(case_id: int, conn=Depends(db)):
    try:
        return repository.list_options(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.post("/api/cases/{case_id}/evaluate", response_model=EvaluationResponse)
def evaluate_case(case_id: int, payload: EvaluationRequest, conn=Depends(db)):
    try:
        repository.get_case(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc
    return evaluate(payload)


@app.post("/api/cases/{case_id}/evidence/search", response_model=list[EvidenceItem])
def search_evidence(case_id: int, payload: EvidenceSearchRequest, conn=Depends(db)):
    try:
        repository.get_case(conn, case_id)
        data = run_search(payload.query, payload.extra_sources)
        return repository.store_search_result(conn, case_id, payload.query, data)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc
    except SmartSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/cases/{case_id}/evidence", response_model=list[EvidenceItem])
def list_evidence(case_id: int, conn=Depends(db)):
    try:
        return repository.list_evidence(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.post("/api/cases/{case_id}/journal", response_model=JournalEntry)
def add_journal(case_id: int, payload: JournalCreate, conn=Depends(db)):
    try:
        return repository.add_journal(conn, case_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.post("/api/cases/{case_id}/journal/from-brief", response_model=JournalEntry)
def add_journal_from_brief(case_id: int, conn=Depends(db)):
    try:
        return create_journal_from_brief(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.patch("/api/cases/{case_id}/journal/{journal_id}", response_model=JournalEntry)
def update_journal(case_id: int, journal_id: int, payload: JournalUpdate, conn=Depends(db)):
    try:
        return repository.update_journal(conn, case_id, journal_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Journal entry not found") from exc


@app.delete("/api/cases/{case_id}/journal/{journal_id}", status_code=204)
def delete_journal(case_id: int, journal_id: int, conn=Depends(db)):
    try:
        repository.delete_journal(conn, case_id, journal_id)
        return Response(status_code=204)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Journal entry not found") from exc


@app.get("/api/cases/{case_id}/journal", response_model=list[JournalEntry])
def list_journals(case_id: int, conn=Depends(db)):
    try:
        return repository.list_journals(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.get("/api/cases/{case_id}/reviews", response_model=list[JournalReview])
def list_case_reviews(case_id: int, conn=Depends(db)):
    try:
        return build_case_reviews(conn, case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Decision case not found") from exc


@app.get("/api/reviews/due", response_model=list[JournalReview])
def list_due_reviews(conn=Depends(db)):
    return build_due_reviews(conn)
