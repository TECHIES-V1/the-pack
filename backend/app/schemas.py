"""All Pydantic request + response models for the Pack API.

Request models validate inbound bodies. Response models document and enforce what each route
returns — every route in app/routers/ carries response_model= pointing here.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Shared enums (reject junk with 422 before it reaches the engine)
# ---------------------------------------------------------------------------

Strategy = Literal["orchestrate", "deep_dive", "critique"]
Source = Literal["typed", "spoken", "dropped"]
Mode = Literal["wild", "on_signal", "on_command"]
InputKind = Literal["text", "pdf", "csv", "md", "url", "image", "audio", "video"]

_MAX_TASK = 10_000
_MAX_INPUT = 200_000

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateHunt(BaseModel):
    input: str | None = Field(None, max_length=_MAX_TASK, description="The task.")
    instinct_id: str | None = Field(None, max_length=120)
    source: Source = "typed"
    strategy: Strategy | None = Field(None, description="Research strategy.")
    team: list[dict] | None = Field(None, max_length=16)


class ApprovePlan(BaseModel):
    mode: Mode
    boundary_usd: float = Field(..., ge=0, le=1000, description="Dollar Boundary.")
    edits: dict | None = None


class ResolveHold(BaseModel):
    resolution: str = Field(..., max_length=2000)
    edited_text: str | None = Field(None, max_length=_MAX_INPUT)


class ResumeHunt(BaseModel):
    boundary_usd: float = Field(..., ge=0, le=1000)


class SaveInstinct(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    spec: dict = Field(default_factory=dict)


class InstinctPatch(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=200)
    spec: dict | None = None


class HuntPatch(BaseModel):
    title: str | None = Field(None, max_length=200)
    archived: bool | None = None
    project_id: str | None = None  # presence-checked; null explicitly unassigns


class MessageIn(BaseModel):
    role: Literal["user", "alpha"]
    content: str = Field(..., max_length=_MAX_INPUT)


class ProjectIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    instructions: str | None = Field(None, max_length=10_000)


class ProjectPatch(BaseModel):
    label: str | None = Field(None, max_length=200)
    instructions: str | None = Field(None, max_length=10_000)


class AddInput(BaseModel):
    text: str = Field(..., max_length=_MAX_INPUT, description="Text to fold into the hunt.")
    kind: InputKind = "text"


class RehearseBody(BaseModel):
    team: list[dict] | None = None
    strategy: str | None = None


class FeedbackBody(BaseModel):
    turn_index: int
    vote: str = Field(..., pattern="^(up|down)$")


class RefineBody(BaseModel):
    instruction: str = Field("", max_length=2000, description="How to re-angle/tighten the brief.")


class AskAlpha(BaseModel):
    question: str | None = Field(None, max_length=_MAX_TASK)
    messages: list[dict] = Field(default_factory=list, max_length=200)


class IntakeBody(BaseModel):
    messages: list[dict] = Field(default_factory=list, max_length=200)


# ---------------------------------------------------------------------------
# Generic response shapes
# ---------------------------------------------------------------------------


class OkResponse(BaseModel):
    ok: bool


class ClearedResponse(BaseModel):
    cleared: bool


# ---------------------------------------------------------------------------
# Hunt response models
# ---------------------------------------------------------------------------


class HuntCreated(BaseModel):
    hunt_id: str
    state: str


class HuntSnapshot(BaseModel):
    hunt_id: str
    state: str
    last_seq: int
    task: str = ""
    strategy: str = "orchestrate"


class HuntSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    hunt_id: str
    state: str


class HuntListResponse(BaseModel):
    hunts: list[HuntSummary]
    next_cursor: str | None = None


class HuntPatchResponse(BaseModel):
    hunt_id: str
    ok: bool


class HuntDeleteResponse(BaseModel):
    hunt_id: str
    deleted: bool


class CommandAccepted(BaseModel):
    hunt_id: str
    accepted: bool


class IntakeReply(BaseModel):
    reply: str
    ready: bool
    brief: str


class AskReply(BaseModel):
    reply: str


class MessageItem(BaseModel):
    role: str
    text: str


class MessagesResponse(BaseModel):
    messages: list[MessageItem]


class ShareResponse(BaseModel):
    token: str


class SharedResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str
    content: dict[str, Any] | None = None


class FeedbackResponse(BaseModel):
    votes: list[dict[str, Any]]
    up: int
    down: int


class RehearseResponse(BaseModel):
    est_cost_usd: float
    est_time_s: float
    calls: int
    scouts: int
    warnings: list[str]


class ArtifactMeta(BaseModel):
    artifact_id: str
    kind: str


class ArtifactsListResponse(BaseModel):
    artifacts: list[ArtifactMeta]


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    artifact_id: str
    hunt_id: str
    kind: str
    produced_by: str | None = None
    content: dict[str, Any] | None = None


class RefineResponse(BaseModel):
    hunt_id: str
    artifact_id: str
    accepted: bool


class ScorecardResponse(BaseModel):
    hunt_id: str
    scorecard: dict[str, Any]


class TracksResponse(BaseModel):
    hunt_id: str
    events: list[dict[str, Any]]
    redacted: bool


# ---------------------------------------------------------------------------
# Project response models
# ---------------------------------------------------------------------------


class ProjectItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    project_id: str
    label: str


class ProjectsListResponse(BaseModel):
    projects: list[ProjectItem]


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    project_id: str
    label: str


class ProjectCreatedResponse(BaseModel):
    project_id: str
    label: str


class ProjectPatchResponse(BaseModel):
    project_id: str
    ok: bool


class ProjectDeleteResponse(BaseModel):
    project_id: str
    deleted: bool


# ---------------------------------------------------------------------------
# Instinct response models
# ---------------------------------------------------------------------------


class InstinctItem(BaseModel):
    instinct_id: str
    label: str
    spec: dict[str, Any] = Field(default_factory=dict)


class InstinctsListResponse(BaseModel):
    instincts: list[InstinctItem]


class InstinctCreatedResponse(BaseModel):
    instinct_id: str
    accepted: bool


class InstinctPatchResponse(BaseModel):
    instinct_id: str
    ok: bool


class InstinctDeleteResponse(BaseModel):
    instinct_id: str
    deleted: bool


# ---------------------------------------------------------------------------
# Document response models
# ---------------------------------------------------------------------------


class DocMeta(BaseModel):
    id: int
    name: str
    kind: str
    chars: int


class DocumentsListResponse(BaseModel):
    documents: list[DocMeta]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    name: str
    kind: str
    chars: int


class DocumentDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    name: str
    kind: str
    chars: int
    text: str


class DocumentDeleteResponse(BaseModel):
    id: int
    deleted: bool


# ---------------------------------------------------------------------------
# Memory / Spend response models
# ---------------------------------------------------------------------------


class MemoryItem(BaseModel):
    text: str
    hunt_id: str | None = None


class MemoryResponse(BaseModel):
    memory: list[MemoryItem]


class SpendHuntItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    hunt_id: str
    cost_usd: float


class SpendResponse(BaseModel):
    total_usd: float
    hunts: list[SpendHuntItem]


# ---------------------------------------------------------------------------
# System response models
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    service: str


class ReadyResponse(BaseModel):
    ready: bool


class StrategyInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    label: str
    pattern: str


class StrategiesResponse(BaseModel):
    strategies: list[StrategyInfo]
    default: str


# ---------------------------------------------------------------------------
# Parse / Transcribe response models
# ---------------------------------------------------------------------------


class ParsedDocResponse(BaseModel):
    kind: str
    text: str
    chars: int
    filename: str | None = None


class TranscriptResponse(BaseModel):
    text: str
    provider: str
    duration_s: float
