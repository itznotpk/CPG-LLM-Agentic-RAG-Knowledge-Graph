"""
Pydantic models for data validation and serialization.
"""

from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from enum import Enum


class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SearchType(str, Enum):
    """Search type enumeration."""
    VECTOR = "vector"
    HYBRID = "hybrid"
    GRAPH = "graph"


# Request Models
class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field(None, description="User identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    search_type: SearchType = Field(default=SearchType.HYBRID, description="Type of search to perform")
    
    model_config = ConfigDict(use_enum_values=True)


class SearchRequest(BaseModel):
    """Search request model."""
    query: str = Field(..., description="Search query")
    search_type: SearchType = Field(default=SearchType.HYBRID, description="Type of search")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Search filters")
    
    model_config = ConfigDict(use_enum_values=True)


# Response Models
class DocumentMetadata(BaseModel):
    """Document metadata model."""
    id: str
    title: str
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    chunk_count: Optional[int] = None


class ChunkResult(BaseModel):
    """Chunk search result model."""
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    document_title: str
    document_source: str
    # Populated by _prefetch_parent_content() in Stage 5
    parent_content: Optional[str] = None   # H1 context (always the top-level parent)
    section_content: Optional[str] = None  # cap-split H2 context (h3 hits only)
    chunk_level: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None

    @field_validator('score')
    @classmethod
    def validate_score(cls, v: float) -> float:
        """Ensure score is between 0 and 1."""
        return max(0.0, min(1.0, v))


class GraphSearchResult(BaseModel):
    """Knowledge graph search result model."""
    fact: str
    uuid: str
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    source_node_uuid: Optional[str] = None


class EntityRelationship(BaseModel):
    """Entity relationship model."""
    from_entity: str
    to_entity: str
    relationship_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Search response model."""
    results: List[ChunkResult] = Field(default_factory=list)
    graph_results: List[GraphSearchResult] = Field(default_factory=list)
    total_results: int = 0
    search_type: SearchType
    query_time_ms: float


class ToolCall(BaseModel):
    """Tool call information model."""
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    tool_call_id: Optional[str] = None


class SourceInfo(BaseModel):
    """Source information from search results."""
    tool: str = "unknown"
    content: str = ""
    document_title: str = "Unknown"
    document_source: str = ""
    score: float = 0.0


class ChatResponse(BaseModel):
    """Chat response model."""
    message: str
    session_id: str
    sources: List[SourceInfo] = Field(default_factory=list)
    tools_used: List[ToolCall] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StreamDelta(BaseModel):
    """Streaming response delta."""
    content: str
    delta_type: Literal["text", "tool_call", "end"] = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Database Models
class Document(BaseModel):
    """Document model."""
    id: Optional[str] = None
    title: str
    source: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Chunk(BaseModel):
    """Document chunk model."""
    id: Optional[str] = None
    document_id: str
    content: str
    embedding: Optional[List[float]] = None
    chunk_index: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    token_count: Optional[int] = None
    created_at: Optional[datetime] = None
    
    @field_validator('embedding')
    @classmethod
    def validate_embedding(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        """Validate embedding dimensions."""
        if v is not None and len(v) != 1536:  # OpenAI text-embedding-3-small
            raise ValueError(f"Embedding must have 1536 dimensions, got {len(v)}")
        return v


class Session(BaseModel):
    """Session model."""
    id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class Message(BaseModel):
    """Message model."""
    id: Optional[str] = None
    session_id: str
    role: MessageRole
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(use_enum_values=True)


# Agent Models
class AgentDependencies(BaseModel):
    """Dependencies for the agent."""
    session_id: str
    database_url: Optional[str] = None
    neo4j_uri: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)




class AgentContext(BaseModel):
    """Agent execution context."""
    session_id: str
    messages: List[Message] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    search_results: List[ChunkResult] = Field(default_factory=list)
    graph_results: List[GraphSearchResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Clinical Workflow Models

class DDxCandidate(BaseModel):
    """One ranked DDx candidate surfaced to the clinician for tier selection."""

    rank: int = Field(..., ge=1, description="1-based rank from Stage 2 rerank")
    code: str = Field(..., description="ICD-11 code")
    title: str = Field(..., description="Code title / disease name")
    probability: float = Field(..., ge=0.0, le=1.0, description="Stage 2 similarity score (0–1)")
    reasoning: List[str] = Field(default_factory=list, description="Per-candidate rationale lines")
    suggested_tier: Optional[Literal["major", "minor"]] = Field(
        None,
        description="System hint: 'major' for rank-1, 'minor' for rank-2 when within STAGE3_HEADLESS_GAP; None otherwise",
    )


class DDxSuggestion(BaseModel):
    """Payload of the `ddx_suggestion` SSE event — top-5 DDx surfaced for clinician
    Major/Minor selection between Stage 2 and Stage 3."""

    candidates: List[DDxCandidate] = Field(..., description="Top-N ranked DDx candidates")
    headless_default_major: Optional[str] = Field(
        None,
        description="ICD code the headless rule would pick as Major if the clinician doesn't choose",
    )
    headless_default_minors: List[str] = Field(
        default_factory=list,
        description="ICD codes the headless rule would route as Minor (empty when single-code default)",
    )


class DDxSelection(BaseModel):
    """Clinician selection payload — posted back via `ddx_selection` / the
    resynthesize request body. Drives Stage 3 Major/Minor allocation."""

    selected_codes: List[str] = Field(
        ...,
        min_length=1,
        description="ICD-11 codes the clinician picked as Major or Minor (1–5)",
    )
    major_code: str = Field(..., description="The single Major code — must appear in selected_codes")

    @model_validator(mode="after")
    def major_in_selected(self) -> "DDxSelection":
        if self.major_code not in self.selected_codes:
            raise ValueError(
                f"major_code {self.major_code!r} must appear in selected_codes "
                f"{self.selected_codes!r}"
            )
        if len(self.selected_codes) > 5:
            raise ValueError(
                f"selected_codes may contain at most 5 entries (got {len(self.selected_codes)})"
            )
        return self


class StageError(BaseModel):
    """Structured error from a pipeline stage."""
    stage: str                          # e.g. "Stage 2 DDx", "Stage 4 Retrieval"
    error_type: str                     # exception class name
    message: str
    recoverable: bool                   # True = pipeline continued with degraded output

    @classmethod
    def from_exc(cls, stage: str, exc: Exception, recoverable: bool) -> "StageError":
        return cls(
            stage=stage,
            error_type=type(exc).__name__,
            message=str(exc),
            recoverable=recoverable,
        )


class StagedComorbidity(BaseModel):
    """Structured comorbidity entry — supersedes free-text strings.
    Frontend submits this when the clinician picks from a dropdown."""
    icd_code: Optional[str] = Field(None, description="ICD-11 code if known, e.g. '5A11', 'GB61.3'")
    label: str = Field(..., description="Human-readable label, e.g. 'Type 2 Diabetes Mellitus', 'CKD Stage 3'")
    severity: Optional[str] = Field(None, description="Severity qualifier, e.g. 'Stage 3b', 'NYHA III'")


class PriorVisitSummary(BaseModel):
    """Lean summary of the most recent prior consultation. Generated at write-time
    by an LLM from the saved consultation note + care plan and stored in Supabase.
    Surfaced back into PatientCase so Stage 4/5 prompts and the UI patient card
    can see what was tried previously without paying the cost of the full note."""

    visit_date: Optional[str] = Field(None, description="ISO date of prior visit, e.g. '2026-04-12'")
    prior_icd_primary: Optional[str] = Field(None, description="Primary ICD-11 code from the prior visit")
    prior_plan_summary: Optional[str] = Field(None, description="1-3 lines: what was prescribed / done last visit")
    key_labs_delta: Optional[str] = Field(None, description="Short free-text: notable lab changes since prior visit")
    what_changed: Optional[str] = Field(None, description="Short free-text: clinical status change vs prior visit")


class PatientCase(BaseModel):
    """Stage 1 input — structured patient record passed into the clinical workflow."""

    chief_complaint: str = Field(..., description="Presenting symptoms — required, non-empty free text")
    history: Optional[str] = Field(None, description="Patient history narrative")
    age: Optional[int] = Field(None, ge=0, le=130, description="Patient age in years")
    sex: Optional[Literal["M", "F", "other"]] = Field(None, description="Biological sex")
    # KEEP the free-text comorbidities list for backward compatibility with existing CLI / older UI
    comorbidities: List[str] = Field(default_factory=list, description="Free-text comorbidity list (legacy)")
    current_medications: List[str] = Field(default_factory=list, description="Current medication names")
    allergies: List[str] = Field(default_factory=list, description="Known allergies")
    vitals: Dict[str, float] = Field(default_factory=dict, description="Vital signs, e.g. {'sbp': 165, 'dbp': 95, 'hr': 110}")
    # NEW — structured severity staging dictionary
    severity_staging: Dict[str, str] = Field(
        default_factory=dict,
        description="Structured staging: NYHA, WHO_FC, WHO_pregnancy_class, CKD_stage, HbA1c, LVEF, eGFR, etc.",
    )
    # NEW — optional structured comorbidities (retires Gap D1 deterministic map)
    staged_comorbidities: List[StagedComorbidity] = Field(
        default_factory=list,
        description="Structured comorbidities with ICD codes. Frontend may populate either this OR comorbidities (free text).",
    )
    # NEW — lean prior-visit summary (generated at write-time, stored in Supabase consultations.prior_visit_summary)
    prior_visit: Optional[PriorVisitSummary] = Field(
        None,
        description="Summary of the most recent prior consultation, when available. Frontend passes through verbatim from Supabase.",
    )

    @field_validator("chief_complaint")
    @classmethod
    def chief_complaint_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("chief_complaint must not be empty or whitespace-only")
        return stripped


class Recommendation(BaseModel):
    """Single clinical recommendation produced in Stage 5."""

    intervention: str = Field(..., description="What to do, e.g. 'Sildenafil 50 mg PRN'")
    type: Literal["pharmacological", "procedure", "lifestyle", "referral", "investigation"] = Field(
        ..., description="Category of the recommendation"
    )
    action: Optional[Literal["start", "stop", "change", "continue", "contraindicated"]] = Field(
        None, description="For pharmacological only: medication action. Null for non-drug types."
    )
    evidence_grade: Optional[str] = Field(None, description="Evidence grade, e.g. 'Grade A, Level 1'")
    cpg_source: str = Field(..., description="Required citation, e.g. 'CPG AF Management §4.2'")
    rationale: str = Field(..., description="Clinical rationale — required, non-empty")
    contraindications_checked: List[str] = Field(default_factory=list, description="Contraindications reviewed before recommending")


class MonitoringItem(BaseModel):
    """Structured monitoring entry produced in Stage 5."""
    parameter: str = Field(..., description="What to monitor, e.g. 'LFTs', '6-Minute Walk Test'")
    schedule: str = Field(..., description="Frequency / timeline, e.g. 'monthly for 4 months, then quarterly'")
    target: Optional[str] = Field(None, description="Target value or threshold, e.g. 'within normal range', 'eGFR >45'")
    cpg_ref: Optional[str] = Field(None, description="CPG section reference, e.g. 'CPG PAH §7.3'")


class TreatmentPlan(BaseModel):
    """Stage 5 output — the final structured plan returned to the doctor."""

    icd_primary: str = Field(..., description="Highest-confidence ICD-11 code")
    icd_alternates: List[str] = Field(default_factory=list, description="Alternative ICD-11 codes considered")
    summary: str = Field(..., description="Clinical assessment: diagnosis type, key risk factors, safety alerts, and classification")
    recommendations: List[Recommendation] = Field(..., description="Clinical recommendations — must contain at least one entry")
    monitoring: List[MonitoringItem] = Field(default_factory=list, description="Structured monitoring parameters with schedule and target")
    red_flags: List[str] = Field(default_factory=list, description="Symptoms or signs that warrant escalation or immediate review")
    follow_up: List[str] = Field(default_factory=list, description="Follow-up timeline, reassessment criteria, and outcome-based actions")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for the plan (0.0–1.0)")
    unresolved_questions: List[str] = Field(default_factory=list, description="Clinical questions that could not be resolved from available evidence")
    gate_audit: List[str] = Field(default_factory=list, description="Referrals evaluated and ruled out by the trigger gate, with reasoning — for clinician transparency")

    @model_validator(mode="after")
    def actionable_or_unresolved(self) -> "TreatmentPlan":
        """A plan must carry actionable content OR an honest reason it can't.

        Empty `recommendations` is allowed ONLY when `unresolved_questions` explains
        why there is no actionable guidance (e.g. no CPG evidence retrieved). This
        matches the documented contract — and prevents the unrecoverable crash where
        the model correctly returns an evidence-honest, recommendation-free plan but
        the schema rejected it. Both empty = a genuinely empty plan = invalid.
        """
        if len(self.recommendations) < 1 and len(self.unresolved_questions) < 1:
            raise ValueError(
                "recommendations must contain at least one entry, or "
                "unresolved_questions must explain why no actionable guidance is available"
            )
        return self


# Safety Critic Models
class SafetyFlag(BaseModel):
    title: str = Field(
        ...,
        description="Short clinician-facing headline, e.g. 'enalapril + spironolactone - hyperkalemia interaction caution'",
    )
    severity: Literal["CRITICAL", "MAJOR", "MODERATE"]
    recommendation_index: int = Field(..., ge=0, description="0-based index into TreatmentPlan.recommendations")
    flag_type: Literal["drug_allergy", "drug_interaction", "dose", "contraindication"]
    detail: str = Field(..., description="One-sentence patient-specific explanation of the concern")
    suggested_alternative: Optional[str] = None
    # "llm" = adversarial LLM critic (default — covers everything pre-existing)
    # "graph" = deterministic Neo4j KG verification of the final plan (hybrid Agent 1
    #   addition). UI may render a "graph-verified" badge for these.
    source: Literal["llm", "graph"] = "llm"
    # Provenance for graph-sourced flags (None for llm flags): the KG relationship
    # type, the originating CPG, and a ready-made citation string for the references
    # list (mirrors the navigator-rule "Interaction graph — …" style).
    kg_relation: Optional[str] = None
    source_document: Optional[str] = None
    graph_citation: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _remap_type_field(cls, data: Any) -> Any:
        if isinstance(data, dict) and "flag_type" not in data and "type" in data:
            data = {**data, "flag_type": data["type"]}
        return data


class SafetyReport(BaseModel):
    flags: List[SafetyFlag] = Field(default_factory=list)
    safe_to_proceed: bool = Field(..., description="False if any CRITICAL or MAJOR flag is present")
    reviewer_notes: Optional[str] = None


# Ingestion Models
class IngestionConfig(BaseModel):
    """Configuration for document ingestion."""
    chunk_size: int = Field(default=1000, ge=100, le=5000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    max_chunk_size: int = Field(default=2000, ge=500, le=10000)
    use_semantic_chunking: bool = True
    extract_entities: bool = True
    # New option for faster ingestion
    skip_graph_building: bool = Field(default=False, description="Skip knowledge graph building for faster ingestion")
    skip_vector_db: bool = Field(default=False, description="Skip PostgreSQL vector DB saving (graph-only mode)")
    
    @field_validator('chunk_overlap')
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        """Ensure overlap is less than chunk size."""
        chunk_size = info.data.get('chunk_size', 1000)
        if v >= chunk_size:
            raise ValueError(f"Chunk overlap ({v}) must be less than chunk size ({chunk_size})")
        return v


class IngestionResult(BaseModel):
    """Result of document ingestion."""
    document_id: str
    title: str
    chunks_created: int
    entities_extracted: int
    relationships_created: int
    processing_time_ms: float
    errors: List[str] = Field(default_factory=list)


# Error Models
class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    error_type: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


# Health Check Models
class HealthStatus(BaseModel):
    """Health check status."""
    status: Literal["healthy", "degraded", "unhealthy"]
    database: bool
    graph_database: bool
    llm_connection: bool
    llm_synthesis: Literal["ok", "degraded", "unknown"] = "unknown"
    llm_safety: Literal["ok", "degraded", "unknown"] = "unknown"
    version: str
    timestamp: datetime
