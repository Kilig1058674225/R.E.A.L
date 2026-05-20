from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


CaseStatus = Literal["active", "paused", "decided", "archived"]
MessageRole = Literal["user", "assistant", "system"]
ActionType = Literal["reject", "observe", "small_experiment", "stage_gated_increase"]


class DecisionCaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    user_goal: str = Field(min_length=1, max_length=4000)
    current_question: str = Field(default="", max_length=4000)


class DecisionCaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    status: CaseStatus | None = None
    user_goal: str | None = Field(default=None, max_length=4000)
    current_question: str | None = Field(default=None, max_length=4000)
    summary: str | None = Field(default=None, max_length=8000)


class DecisionCase(BaseModel):
    id: int
    title: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    user_goal: str
    current_question: str
    classification: str
    urgency: str
    stakes: str
    search_required: bool
    summary: str


class DecisionState(BaseModel):
    case_id: int
    title: str
    summary: str
    current_action: ActionType | None = None
    concerns: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    candidate_options: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    message_count: int = 0
    updated_at: datetime


class PremortemItem(BaseModel):
    reason: str
    likelihood: str
    impact: str
    prevention: str


class DecisionBrief(BaseModel):
    case_id: int
    recommended_action: ActionType
    confidence: str
    summary: str
    reality_checks: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    premortem: list[PremortemItem] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class DecisionActionPlan(BaseModel):
    case_id: int
    action: ActionType
    commitment_level: str
    timebox_days: int
    review_date: str
    success_signals: list[str] = Field(default_factory=list)
    failure_signals: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    journal_rationale: str


class MessageCreate(BaseModel):
    role: MessageRole = "user"
    content: str = Field(min_length=1, max_length=12000)


class ConversationMessage(BaseModel):
    id: int
    case_id: int
    role: MessageRole
    content: str
    created_at: datetime


class OptionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class DecisionOption(BaseModel):
    id: int
    case_id: int
    label: str
    description: str
    expected_value: float | None = None
    mcda_score: float | None = None
    risk_notes: str = ""
    reversibility: float | None = None
    evidence_links: list[str] = Field(default_factory=list)


class CriterionScore(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    weight: float = Field(ge=0, le=1)
    scores: dict[str, float] = Field(default_factory=dict)


class OutcomeEstimate(BaseModel):
    probability: float = Field(ge=0, le=1)
    utility: float = Field(ge=-10, le=10)
    label: str = Field(default="", max_length=120)


class OptionEvaluationInput(BaseModel):
    option_label: str
    outcomes: list[OutcomeEstimate] = Field(default_factory=list)
    reversibility: float = Field(default=0.5, ge=0, le=1)
    control_cost: float = Field(default=0, ge=0, le=1)
    ruin_flags: list[str] = Field(default_factory=list)
    information_value: float = Field(default=0.5, ge=0, le=1)


class EvaluationRequest(BaseModel):
    criteria: list[CriterionScore] = Field(default_factory=list)
    options: list[OptionEvaluationInput] = Field(default_factory=list)


class OptionEvaluationResult(BaseModel):
    option_label: str
    expected_value: float | None
    mcda_score: float | None
    risk_level: str
    recommendation: ActionType
    notes: list[str]


class EvaluationResponse(BaseModel):
    results: list[OptionEvaluationResult]
    best_action: ActionType
    summary: str


class EvidenceSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    extra_sources: int = Field(default=2, ge=0, le=5)


class EvidenceItem(BaseModel):
    id: int
    case_id: int
    query: str
    url: str
    title: str
    source_type: str
    fetched_text: str
    confidence: str
    created_at: datetime


class JournalCreate(BaseModel):
    final_action: ActionType
    rationale: str = Field(default="", max_length=8000)
    stop_conditions: str = Field(default="", max_length=4000)
    follow_up_date: str = Field(default="", max_length=40)
    outcome: str = Field(default="", max_length=8000)


class JournalUpdate(BaseModel):
    final_action: ActionType | None = None
    rationale: str | None = Field(default=None, max_length=8000)
    stop_conditions: str | None = Field(default=None, max_length=4000)
    follow_up_date: str | None = Field(default=None, max_length=40)
    outcome: str | None = Field(default=None, max_length=8000)


class JournalEntry(BaseModel):
    id: int
    case_id: int
    final_action: ActionType
    rationale: str
    stop_conditions: str
    follow_up_date: str
    outcome: str
    created_at: datetime


class JournalReview(BaseModel):
    journal: JournalEntry
    case_title: str
    status: Literal["overdue", "due_today", "upcoming", "completed", "unscheduled"]
    days_delta: int | None = None
    review_prompt: str
    learning_summary: str = ""


class LLMConfigStatus(BaseModel):
    configured: bool
    base_url: str
    model: str
    api_key_set: bool


class AgentReplyRequest(BaseModel):
    note: str = Field(default="", max_length=2000)
    recent_message_limit: int = Field(default=12, ge=1, le=40)


class AgentReplyResponse(BaseModel):
    message: ConversationMessage
    model: str
    used_evidence_count: int


class AgentChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    recent_message_limit: int = Field(default=14, ge=1, le=40)


class AgentChatResponse(BaseModel):
    user_message: ConversationMessage
    assistant_message: ConversationMessage
    model: str
    used_evidence_count: int


JsonDict = dict[str, Any]
