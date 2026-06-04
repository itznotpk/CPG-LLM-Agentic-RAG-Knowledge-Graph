"""
FastAPI endpoints for the agentic RAG system.
"""

import os
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextvars import ContextVar

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
import uvicorn
from dotenv import load_dotenv

from .agent import rag_agent, AgentDependencies
from .delivery_worker import start as start_delivery_worker, stop as stop_delivery_worker
from .db_utils import (
    initialize_database,
    initialize_supabase_db,
    close_supabase_db,
    close_database,
    create_session,
    get_session,
    add_message,
    get_session_messages,
    test_connection
)
from .graph_utils import initialize_graph, close_graph, test_graph_connection
from .models import (
    ChatRequest,
    ChatResponse,
    SearchRequest,
    SearchResponse,
    StreamDelta,
    ErrorResponse,
    HealthStatus,
    ToolCall,
    PatientCase,
    TreatmentPlan,
    SafetyReport,
)
from pydantic import BaseModel as _BaseModel


class ClinicalPlanRequest(_BaseModel):
    case: PatientCase
    session_id: str | None = None
    consultation_id: int | None = None  # Supabase row id; tags SSE log entries


class SelectedDiagnosis(_BaseModel):
    code: str
    title: str
    probability: float = 0.9
    reasoning: list[str] = []
    # Tier — "major" for the single primary diagnosis, "minor" for co-considerations.
    # Optional for backward-compat: when omitted, the first diagnosis is treated as Major
    # and the rest as Minor.
    tier: str | None = None


class ResynthesizeRequest(_BaseModel):
    case: PatientCase
    selected_diagnoses: list[SelectedDiagnosis]
    # Explicit Major code — must equal one of selected_diagnoses[*].code.
    # Optional for backward-compat: when None, falls back to (a) the diagnosis whose
    # tier=="major", else (b) the first entry of selected_diagnoses.
    major_code: str | None = None
    # Supabase consultation row id; tags the SSE log + pipeline timings so the
    # re-synth run is associated with the same consultation as the initial DDx run.
    # Optional — older callers may not send it.
    consultation_id: int | None = None


class ClinicalPlanResponse(_BaseModel):
    treatment_plan: TreatmentPlan
    ddx: list[dict]
    cpgs_matched: list[str]
    elapsed_ms: float
    stage_errors: list[dict] = []
    graph_navigator_rules: list[dict] = []
    safety_report: SafetyReport | None = None
    cpg_references: list[str] = []  # Derived from recommendations/monitoring citations
    follow_up_parsed: list[dict] = []  # Derived from treatment_plan.follow_up; drives TCA date picker
    evidence: list[dict] = []


import re as _re

# Matches the leading "WHEN:" segment of a follow-up string. Examples covered:
#   "1-2 weeks: reassess renal function …"     -> when="1-2 weeks"
#   "3 months: repeat HbA1c …"                 -> when="3 months"
#   "Ongoing: titrate β-blocker …"             -> when="Ongoing"
#   "Annual: review CPG currency …"            -> when="Annual"
#   "At 24h: review fluid status …"            -> when="At 24h"
_FOLLOWUP_WHEN_RE = _re.compile(
    r"^\s*(?P<when>"
    r"(?:at\s+)?(?:\d+\s*[-–to]+\s*)?\d+\s*(?:hours?|hrs?|h|days?|d|weeks?|wks?|w|months?|mo|years?|y)"
    r"|ongoing|annual(?:ly)?|biannual(?:ly)?|monthly|weekly|daily|long[-\s]?term|maintenance"
    r")\s*[:\-—]\s*(?P<rest>.+)$",
    _re.IGNORECASE,
)

# Days-from-now conversion for the TCA date picker. Conservative midpoints; the
# clinician still sees the verbatim "when" string and can override.
_WHEN_TO_DAYS = [
    (_re.compile(r"(\d+)\s*[-–to]+\s*(\d+)\s*(hours?|hrs?|h)\b", _re.I), lambda m: max(1, int((int(m.group(1)) + int(m.group(2))) / 48))),
    (_re.compile(r"(\d+)\s*(hours?|hrs?|h)\b", _re.I),                   lambda m: max(1, int(int(m.group(1)) / 24))),
    (_re.compile(r"(\d+)\s*[-–to]+\s*(\d+)\s*(days?|d)\b", _re.I),       lambda m: int((int(m.group(1)) + int(m.group(2))) / 2)),
    (_re.compile(r"(\d+)\s*(days?|d)\b", _re.I),                         lambda m: int(m.group(1))),
    (_re.compile(r"(\d+)\s*[-–to]+\s*(\d+)\s*(weeks?|wks?|w)\b", _re.I), lambda m: int((int(m.group(1)) + int(m.group(2))) / 2) * 7),
    (_re.compile(r"(\d+)\s*(weeks?|wks?|w)\b", _re.I),                   lambda m: int(m.group(1)) * 7),
    (_re.compile(r"(\d+)\s*[-–to]+\s*(\d+)\s*(months?|mo)\b", _re.I),    lambda m: int((int(m.group(1)) + int(m.group(2))) / 2) * 30),
    (_re.compile(r"(\d+)\s*(months?|mo)\b", _re.I),                      lambda m: int(m.group(1)) * 30),
    (_re.compile(r"(\d+)\s*(years?|y)\b", _re.I),                        lambda m: int(m.group(1)) * 365),
    (_re.compile(r"annual(?:ly)?", _re.I),                          lambda m: 365),
    (_re.compile(r"biannual(?:ly)?", _re.I),                        lambda m: 180),
    (_re.compile(r"monthly", _re.I),                                lambda m: 30),
    (_re.compile(r"weekly", _re.I),                                 lambda m: 7),
    (_re.compile(r"daily", _re.I),                                  lambda m: 1),
]


def _parse_follow_up(items: list[str]) -> list[dict]:
    """Best-effort parser. Returns one dict per item with:
       when         : str  — verbatim timeline phrase (or "" if unparseable)
       days_from_now: int | None — for TCA date picker; None if ongoing/unparseable
       action       : str  — the rest of the string after the timeline
       raw          : str  — the original string
    Unparseable items still return a dict so list lengths match by index.
    """
    out: list[dict] = []
    for raw in items or []:
        s = (raw or "").strip()
        if not s:
            continue
        m = _FOLLOWUP_WHEN_RE.match(s)
        if m:
            when = m.group("when").strip()
            rest = m.group("rest").strip()
        else:
            when = ""
            rest = s
        days = None
        if when:
            for pat, fn in _WHEN_TO_DAYS:
                mm = pat.search(when)
                if mm:
                    days = fn(mm)
                    break
        out.append({"when": when, "days_from_now": days, "action": rest, "raw": s})
    return out


def _derive_cpg_references(plan: TreatmentPlan, safety_flags: list | None = None) -> list[str]:
    """Collect unique CPG citation strings from a TreatmentPlan for the UI's
    collapsible references section. Order preserved by first appearance so the
    primary CPG (cited most prominently) sorts to the top.

    Gap-flag strings written by the LLM when no relevant chunk was retrieved
    (e.g. 'No specific CPG chunk retrieved for ACS management…') are excluded —
    they are evidence-gap disclosures that belong in unresolved_questions, not
    in the references list.

    Graph-sourced safety flags contribute their provenance as "Interaction graph —
    …" entries (same style as navigator rules), so the KG relationships that drive
    the dual-source safety critic are cited rather than buried in flag prose.
    """
    seen: list[str] = []
    seen_set: set[str] = set()
    for r in plan.recommendations or []:
        src = (r.cpg_source or "").strip()
        # Skip LLM gap-flags — these are honest "no evidence" disclosures, not citations
        if not src or src.lower().startswith("no specific cpg"):
            continue
        if src not in seen_set:
            seen_set.add(src)
            seen.append(src)
    for m in plan.monitoring or []:
        ref = None
        if isinstance(m, dict):
            ref = (m.get("cpg_ref") or "").strip()
        else:
            ref = (getattr(m, "cpg_ref", None) or "").strip()
        if ref and not ref.lower().startswith("no specific cpg") and ref not in seen_set:
            seen_set.add(ref)
            seen.append(ref)
    for f in safety_flags or []:
        cite = getattr(f, "graph_citation", None) if not isinstance(f, dict) else f.get("graph_citation")
        cite = (cite or "").strip()
        if cite and cite not in seen_set:
            seen_set.add(cite)
            seen.append(cite)
    return seen

from .tools import (
    vector_search_tool,
    graph_search_tool,
    hybrid_search_tool,
    VectorSearchInput,
    GraphSearchInput,
    HybridSearchInput
)
from .offline_log import log_sse_event, log_failed_job

# Load environment variables
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# Application configuration
APP_ENV = os.getenv("APP_ENV", "development")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", 8000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Set debug level for our module during development
if APP_ENV == "development":
    logger.setLevel(logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    logger.info("Starting up agentic RAG API...")
    
    try:
        # Initialize database connections with timeout
        logger.info("Initializing database...")
        await asyncio.wait_for(initialize_database(), timeout=15.0)
        logger.info("Database initialized")

        try:
            await asyncio.wait_for(initialize_supabase_db(), timeout=15.0)
        except Exception as se:
            logger.warning(f"Supabase pool init failed (delivery disabled): {se}")
        
        # Initialize graph database (Optional - don't crash if it fails)
        try:
            logger.info("Initializing graph database...")
            await asyncio.wait_for(initialize_graph(), timeout=15.0)
            logger.info("Graph database initialized")
        except Exception as ge:
            logger.warning(f"Graph database initialization failed (Optional): {ge}")
            logger.warning("Continuing without Knowledge Graph functionality")
        
        # Test connections
        db_ok = await test_connection()
        graph_ok = await test_graph_connection()
        
        if not db_ok:
            logger.error("Database connection failed")
        if not graph_ok:
            logger.warning("Graph database connection failed - searching will fall back to vector search only")
        
        logger.info("Agentic RAG API startup complete")
        start_delivery_worker()

    except asyncio.TimeoutError:
        logger.error("Startup timed out during database initialization")
        # Don't raise, let the app start in a degraded state if possible
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # Only raise for critical failures (like Postgres)
        if "database" in str(e).lower():
            raise
    yield
    
    # Shutdown
    logger.info("Shutting down agentic RAG API...")

    try:
        await stop_delivery_worker()
        await close_supabase_db()
        await close_database()
        await close_graph()
        logger.info("Connections closed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# Create FastAPI app
app = FastAPI(
    title="Agentic RAG with Knowledge Graph",
    description="AI agent combining vector search and knowledge graph for tech company analysis",
    version="0.1.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def _correlation_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    _request_id_var.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# Add middleware with flexible CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── rPPG vital scanner ──────────────────────────────────────────────────────
# Mount the standalone rPPG POC (<repo-root>/rppg-poc/rppg_vitals.py) as a sub-app
# so it runs inside this backend. With the API on :8058 the scanner is reachable
# at  ws://<host>:8058/rppg/ws  and  http://<host>:8058/rppg/api/vitals .
# Optional: if its deps (opencv/scipy/etc.) aren't installed the API still boots.
try:
    import sys as _sys
    # __file__ is backend/agent/api.py -> climb three levels to repo root,
    # where rppg-poc/ lives alongside backend/ and frontend/.
    _rppg_dir = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ),
        "rppg-poc",
    )
    if _rppg_dir not in _sys.path:
        _sys.path.insert(0, _rppg_dir)
    from rppg_vitals import app as rppg_app  # noqa: E402
    app.mount("/rppg", rppg_app)
    logger.info("rPPG vital scanner mounted at /rppg (ws: /rppg/ws)")
except Exception as _rppg_err:  # pragma: no cover - optional dependency
    logger.warning(
        "rPPG vital scanner not mounted (optional): %s. "
        "Install its deps with: pip install opencv-python scipy mediapipe",
        _rppg_err,
    )


# Helper functions for agent execution
async def get_or_create_session(request: ChatRequest) -> str:
    """Get existing session or create new one."""
    if request.session_id:
        session = await get_session(request.session_id)
        if session:
            return request.session_id
    
    # Create new session
    return await create_session(
        user_id=request.user_id,
        metadata=request.metadata
    )


async def get_conversation_context(
    session_id: str,
    max_messages: int = 10
) -> List[Dict[str, str]]:
    """
    Get recent conversation context.
    
    Args:
        session_id: Session ID
        max_messages: Maximum number of messages to retrieve
    
    Returns:
        List of messages
    """
    messages = await get_session_messages(session_id, limit=max_messages)
    
    return [
        {
            "role": msg["role"],
            "content": msg["content"]
        }
        for msg in messages
    ]


def extract_tool_calls(result) -> List[ToolCall]:
    """
    Extract tool calls from Pydantic AI result.

    Args:
        result: Pydantic AI result object

    Returns:
        List of ToolCall objects
    """
    tools_used = []

    try:
        # Get all messages from the result
        messages = result.all_messages()

        for message in messages:
            if hasattr(message, 'parts'):
                for part in message.parts:
                    # Check if this is a tool call part
                    if part.__class__.__name__ == 'ToolCallPart':
                        try:
                            tool_name = str(part.tool_name) if hasattr(part, 'tool_name') else 'unknown'

                            tool_args = {}
                            if hasattr(part, 'args') and part.args is not None:
                                if isinstance(part.args, str):
                                    try:
                                        tool_args = json.loads(part.args)
                                    except json.JSONDecodeError:
                                        tool_args = {}
                                elif isinstance(part.args, dict):
                                    tool_args = part.args

                            if hasattr(part, 'args_as_dict'):
                                try:
                                    tool_args = part.args_as_dict()
                                except:
                                    pass

                            tool_call_id = None
                            if hasattr(part, 'tool_call_id'):
                                tool_call_id = str(part.tool_call_id) if part.tool_call_id else None

                            tools_used.append(ToolCall(
                                tool_name=tool_name,
                                args=tool_args,
                                tool_call_id=tool_call_id
                            ))
                        except Exception as e:
                            logger.debug(f"Failed to parse tool call part: {e}")
                            continue
    except Exception as e:
        logger.warning(f"Failed to extract tool calls: {e}")

    return tools_used


def extract_sources(result) -> List[Dict[str, Any]]:
    """
    Extract source documents/chunks from tool results.

    Args:
        result: Pydantic AI result object

    Returns:
        List of source documents with content and metadata
    """
    sources = []
    seen_content = set()  # Deduplicate by content

    def parse_content(content):
        """Parse content that may be string, dict, or list."""
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
        return content

    def extract_from_item(item, tool_name):
        """Extract source info from a single item."""
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except json.JSONDecodeError:
                return None

        if not isinstance(item, dict):
            return None

        # For vector/hybrid search results
        if tool_name in ['vector_search', 'hybrid_search']:
            content = item.get('content', '')
            if content:
                return {
                    'tool': tool_name,
                    'content': content[:300],
                    'document_title': item.get('document_title', 'CPG Document'),
                    'document_source': item.get('document_source', ''),
                    'score': round(float(item.get('score', 0.8)), 3)
                }

        # For graph search results
        elif tool_name == 'graph_search':
            fact = item.get('fact', '')
            if fact:
                return {
                    'tool': 'graph_search',
                    'content': fact,
                    'document_title': 'Knowledge Graph',
                    'document_source': 'graph',
                    'score': 1.0
                }

        # For drug info results
        elif tool_name in ['get_drug_information', 'get_drug_info']:
            info = item.get('drug_info') or item.get('info') or item.get('content', '')
            if info:
                return {
                    'tool': 'drug_info',
                    'content': str(info)[:300],
                    'document_title': f"Drug: {item.get('drug_name', 'Unknown')}",
                    'document_source': 'knowledge_graph',
                    'score': 1.0
                }

        return None

    try:
        messages = result.all_messages()
        logger.info(f"[SOURCES] Processing {len(messages)} messages")

        for message in messages:
            if hasattr(message, 'parts'):
                for part in message.parts:
                    # Look for tool returns
                    if hasattr(part, 'tool_name') and hasattr(part, 'content'):
                        tool_name = str(part.tool_name)
                        content = parse_content(part.content)

                        logger.info(f"[SOURCES] Found tool result: {tool_name}, type: {type(content)}")

                        # Handle list of results
                        if isinstance(content, list):
                            for item in content:
                                source = extract_from_item(item, tool_name)
                                if source:
                                    chunk_key = source['content'][:100]
                                    if chunk_key not in seen_content:
                                        seen_content.add(chunk_key)
                                        sources.append(source)

                        # Handle single dict result
                        elif isinstance(content, dict):
                            source = extract_from_item(content, tool_name)
                            if source:
                                chunk_key = source['content'][:100]
                                if chunk_key not in seen_content:
                                    seen_content.add(chunk_key)
                                    sources.append(source)

        logger.info(f"[SOURCES] Extracted {len(sources)} sources")

    except Exception as e:
        logger.error(f"[SOURCES] Error: {e}")
        import traceback
        logger.error(f"[SOURCES] Traceback: {traceback.format_exc()}")

    # Fallback: if no sources found, add a default source
    if not sources:
        sources.append({
            'tool': 'system',
            'content': 'Response based on CPG clinical guidelines knowledge base.',
            'document_title': 'CPG Guidelines',
            'document_source': 'knowledge_base',
            'score': 0.9
        })

    return sources


async def save_conversation_turn(
    session_id: str,
    user_message: str,
    assistant_message: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Save a conversation turn to the database.
    
    Args:
        session_id: Session ID
        user_message: User's message
        assistant_message: Assistant's response
        metadata: Optional metadata
    """
    # Save user message
    await add_message(
        session_id=session_id,
        role="user",
        content=user_message,
        metadata=metadata or {}
    )
    
    # Save assistant message
    await add_message(
        session_id=session_id,
        role="assistant",
        content=assistant_message,
        metadata=metadata or {}
    )


async def execute_agent(
    message: str,
    session_id: str,
    user_id: Optional[str] = None,
    save_conversation: bool = True
) -> tuple[str, List[ToolCall], List[Dict[str, Any]]]:
    """
    Execute the agent with a message.

    Args:
        message: User message
        session_id: Session ID
        user_id: Optional user ID
        save_conversation: Whether to save the conversation

    Returns:
        Tuple of (agent response, tools used, sources)
    """
    try:
        # Create dependencies
        deps = AgentDependencies(
            session_id=session_id,
            user_id=user_id
        )

        # Get conversation context
        context = await get_conversation_context(session_id)

        # Build prompt with context
        full_prompt = message
        if context:
            context_str = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in context[-6:]  # Last 3 turns
            ])
            full_prompt = f"Previous conversation:\n{context_str}\n\nCurrent question: {message}"

        # Run the agent
        result = await rag_agent.run(full_prompt, deps=deps)

        response = result.output
        tools_used = extract_tool_calls(result)
        sources = extract_sources(result)

        # Save conversation if requested
        if save_conversation:
            await save_conversation_turn(
                session_id=session_id,
                user_message=message,
                assistant_message=response,
                metadata={
                    "user_id": user_id,
                    "tool_calls": len(tools_used),
                    "sources_count": len(sources)
                }
            )

        return response, tools_used, sources

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

        error_response = f"I encountered an error while processing your request: {str(e)}"

        if save_conversation:
            await save_conversation_turn(
                session_id=session_id,
                user_message=message,
                assistant_message=error_response,
                metadata={"error": str(e)}
            )

        # Always return at least one fallback source
        fallback_sources = [{
            'tool': 'system',
            'content': 'Unable to retrieve specific sources due to an error.',
            'document_title': 'System Message',
            'document_source': 'system',
            'score': 0.0
        }]

        return error_response, [], fallback_sources


async def _probe_llm(base_url: str | None, api_key: str | None, model: str, timeout: float = 2.0) -> bool:
    """Send a minimal completion to check reachability. Returns True if the provider responds."""
    if not base_url or not api_key:
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            )
        return resp.status_code < 500
    except Exception:
        return False


# API Endpoints
@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint."""
    try:
        db_status, graph_status = await asyncio.gather(
            test_connection(), test_graph_connection()
        )

        synthesis_ok, safety_ok = await asyncio.gather(
            _probe_llm(
                os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL"),
                os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY"),
                os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", ""),
            ),
            _probe_llm(
                os.getenv("SAFETY_CRITIC_BASE_URL") or os.getenv("STAGE5_LLM_BASE_URL") or os.getenv("LLM_BASE_URL"),
                os.getenv("SAFETY_CRITIC_API_KEY") or os.getenv("STAGE5_LLM_API_KEY") or os.getenv("LLM_API_KEY"),
                os.getenv("SAFETY_CRITIC_MODEL") or os.getenv("STAGE5_LLM_CHOICE") or os.getenv("LLM_CHOICE", ""),
            ),
        )

        llm_ok = synthesis_ok and safety_ok
        if db_status and graph_status and llm_ok:
            status = "healthy"
        elif db_status:
            status = "degraded"
        else:
            status = "unhealthy"

        return HealthStatus(
            status=status,
            database=db_status,
            graph_database=graph_status,
            llm_connection=llm_ok,
            llm_synthesis="ok" if synthesis_ok else "degraded",
            llm_safety="ok" if safety_ok else "degraded",
            version="0.1.0",
            timestamp=datetime.now()
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming chat endpoint."""
    try:
        # Get or create session
        session_id = await get_or_create_session(request)

        # Execute agent
        response, tools_used, sources = await execute_agent(
            message=request.message,
            session_id=session_id,
            user_id=request.user_id
        )

        return ChatResponse(
            message=response,
            session_id=session_id,
            tools_used=tools_used,
            sources=sources,
            metadata={"search_type": str(request.search_type)}
        )

    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clinical/plan", response_model=ClinicalPlanResponse)
async def clinical_plan(request: ClinicalPlanRequest):
    """
    Run the full clinical workflow for a patient case.
    Accepts PatientCase, returns TreatmentPlan + DDx candidates + matched CPGs.
    """
    from .clinical_workflow import run_clinical_workflow

    try:
        result = await run_clinical_workflow(request.case)
        return ClinicalPlanResponse(
            treatment_plan=result.treatment_plan,
            ddx=[d.model_dump() for d in result.ddx],
            cpgs_matched=[c.cpg_name for c in result.cpgs],
            elapsed_ms=result.elapsed_ms,
            stage_errors=[e.model_dump() for e in result.stage_errors],
            graph_navigator_rules=result.graph_navigator_rules,
            safety_report=result.safety_report,
            cpg_references=_derive_cpg_references(result.treatment_plan, getattr(result.safety_report, "flags", None)),
            follow_up_parsed=_parse_follow_up(result.treatment_plan.follow_up),
            evidence=[e.model_dump() for e in result.evidence] if hasattr(result, 'evidence') else [],
        )
    except ConnectionError as e:
        # Data-store unreachable (pgvector / Neo4j) — this is a transient
        # infrastructure outage, not a request defect. 503 tells the client it's
        # safe to retry, rather than masking it as a generic 500 (INF-03).
        logger.error("Clinical plan data-store unavailable: %s", e)
        log_failed_job("clinical_plan", request.case, str(e), request_id=_request_id_var.get())
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        logger.error("Clinical plan synthesis failed: %s", e)
        log_failed_job("clinical_plan", request.case, str(e), request_id=_request_id_var.get())
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Clinical plan endpoint failed: %s", e)
        log_failed_job("clinical_plan", request.case, str(e), request_id=_request_id_var.get())
        raise HTTPException(status_code=500, detail=str(e))


class SummarisePriorRequest(_BaseModel):
    consultation_date: str
    clinical_notes: str
    care_plan_summary: Optional[str] = None
    prior_icd_primary: Optional[str] = None
    medication_recommendations: Optional[Any] = None


@app.post("/clinical/summarise-prior")
async def summarise_prior(request: SummarisePriorRequest):
    """Generate a lean PriorVisitSummary from a saved consultation.

    Called by the Doctor UI immediately after the consultation is persisted to
    Supabase. Returns the JSON the caller should write into
    consultations.prior_visit_summary so the next visit can read it back.
    """
    from .clinical_stages import summarise_prior_visit

    try:
        summary = await summarise_prior_visit(
            consultation_date=request.consultation_date,
            clinical_notes=request.clinical_notes,
            care_plan_summary=request.care_plan_summary,
            prior_icd_primary=request.prior_icd_primary,
            medication_recommendations=request.medication_recommendations,
        )
        return summary.model_dump()
    except Exception as e:
        logger.error("summarise-prior failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class PrepBriefRequest(_BaseModel):
    patient_nric: str
    prior_visit: dict
    current_medications: list = []
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    comorbidities: list = []


@app.post("/clinical/prep-brief")
async def prep_brief(request: PrepBriefRequest):
    """30-second pre-consultation briefing for returning patients.

    Returns 3 bullets: since_last_visit, med_flags, ask_today.
    Only call when prior_visit is non-null (returning patients only).
    """
    from .clinical_stages import generate_prep_brief

    try:
        brief = await generate_prep_brief(
            prior_visit=request.prior_visit,
            current_medications=request.current_medications,
            patient_age=request.patient_age,
            patient_sex=request.patient_sex,
            comorbidities=request.comorbidities,
        )
        return brief
    except Exception as e:
        logger.error("prep-brief failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Shared SSE plumbing for clinical streaming endpoints.
#
# Guarantees:
#   - Ordered, gap-free delivery via monotonic `id:` sequence numbers per response.
#   - Bounded back-pressure (queue cap) so a slow client throttles the producer
#     instead of leaking memory.
#   - Client-disconnect detection cancels the producer task immediately, so
#     Stage 5 (Gemini synthesis) and Stage 6 (LLM critic + Neo4j KG verify)
#     stop burning tokens the moment the browser drops.
#   - Periodic heartbeat comment keeps proxies (nginx/CloudFront) from idling
#     the TCP connection and doubles as a disconnect probe.
#   - Producer exceptions are surfaced as a final `event: error` then `done`,
#     never an HTTP 500 mid-stream (which clients render as a hard failure).
# ---------------------------------------------------------------------------

_SSE_QUEUE_MAX = 256          # back-pressure cap; producer awaits when full
_SSE_HEARTBEAT_SEC = 15.0     # also the disconnect-probe interval
_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",   # disables nginx response buffering
    "Content-Encoding": "identity",
}
_SSE_DONE = object()


async def _sse_stream(request: Request, producer, log_label: str, consultation_id=None) -> StreamingResponse:
    """
    Run `producer(emit)` and stream its events as SSE.

    `producer` is `async def producer(emit) -> None` where
    `emit(event_type: str, data: dict)` is awaitable.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=_SSE_QUEUE_MAX)

    async def emit(event_type: str, data: dict) -> None:
        log_sse_event(consultation_id, event_type, data, request_id=_request_id_var.get())
        await queue.put((event_type, data))

    async def run_producer() -> None:
        try:
            await producer(emit)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("%s producer failed", log_label)
            try:
                queue.put_nowait(("error", {"detail": str(e)}))
            except asyncio.QueueFull:
                pass
        finally:
            # Always terminate the consumer loop, even under cancellation.
            try:
                queue.put_nowait(_SSE_DONE)
            except asyncio.QueueFull:
                pass

    async def generate():
        seq = 0
        prod_task = asyncio.create_task(run_producer(), name=f"sse-{log_label}")
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=_SSE_HEARTBEAT_SEC)
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        return
                    # SSE comment line — keeps the socket warm, never fires UI handlers.
                    yield ": ping\n\n"
                    continue

                if item is _SSE_DONE:
                    seq += 1
                    yield f"id: {seq}\nevent: done\ndata: {{}}\n\n"
                    return

                event_type, data = item
                seq += 1
                payload = json.dumps(data, separators=(",", ":"), default=str)
                yield f"id: {seq}\nevent: {event_type}\ndata: {payload}\n\n"
        finally:
            # Client closed the connection, response was cancelled, or we
            # exited normally. Either way, stop the producer to free LLM /
            # DB / KG work that nobody will see.
            if not prod_task.done():
                prod_task.cancel()
                try:
                    await prod_task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _harvest_machine_signals(result, consultation_id) -> None:
    """Persist pipeline insights the workflow already computed (gate failures,
    unresolved/coverage gaps, stage errors) to the machine_signals table — the
    "Machine Signals" feed of the Layer-3 feedback ecosystem.

    Pure read of structures that already exist on `result`, then async writes
    AFTER final_result is emitted — never affects clinical content or timing.
    Fully fail-open: a failure here must not break the producer. Naturally
    no-ops when SUPABASE_DB_URL is unset (e.g. eval/CLI runs), since
    log_machine_signal short-circuits on a None pool.
    """
    try:
        from .db_utils import log_machine_signal
        rid = _request_id_var.get()
        plan = getattr(result, "treatment_plan", None)

        for line in getattr(plan, "gate_audit", []) or []:
            await log_machine_signal(
                "gate_failure", consultation_id=consultation_id, request_id=rid,
                detail=str(line), severity="info",
            )
        for q in getattr(plan, "unresolved_questions", []) or []:
            await log_machine_signal(
                "coverage_gap", consultation_id=consultation_id, request_id=rid,
                detail=str(q), severity="info",
            )
        for err in getattr(result, "stage_errors", []) or []:
            await log_machine_signal(
                "stage_error", consultation_id=consultation_id, request_id=rid,
                detail=f"{getattr(err, 'stage', '')}: {getattr(err, 'message', '')}",
                severity="warning" if getattr(err, "recoverable", True) else "critical",
                payload={"error_type": getattr(err, "error_type", None),
                         "recoverable": getattr(err, "recoverable", None)},
            )
    except Exception as exc:
        logger.warning("_harvest_machine_signals failed (non-fatal): %s", exc)


@app.post("/clinical/plan/stream")
async def clinical_plan_stream(request: Request, payload: ClinicalPlanRequest):
    """
    Run clinical workflow and stream stage progress + DDx thinking as SSE events.

    Event order is contractual:
      stage_update (2→5) · thinking_delta · sub_step · safety_review · final_result · done
    Each frame carries a monotonic `id:` so the UI can dedupe on EventSource reconnect.
    """
    from .clinical_workflow import run_clinical_workflow_streaming

    async def producer(emit):
        from .db_utils import save_pipeline_timings
        try:
            result = await run_clinical_workflow_streaming(payload.case, emit)
        except Exception as e:
            log_failed_job("clinical_plan_stream", payload.case, str(e), request_id=_request_id_var.get())
            raise
        final = ClinicalPlanResponse(
            treatment_plan=result.treatment_plan,
            ddx=[d.model_dump() for d in result.ddx],
            cpgs_matched=[c.cpg_name for c in result.cpgs],
            elapsed_ms=result.elapsed_ms,
            stage_errors=[e.model_dump() for e in result.stage_errors],
            graph_navigator_rules=result.graph_navigator_rules,
            safety_report=result.safety_report,
            cpg_references=_derive_cpg_references(result.treatment_plan, getattr(result.safety_report, "flags", None)),
            follow_up_parsed=_parse_follow_up(result.treatment_plan.follow_up),
            evidence=[e.model_dump() for e in result.evidence] if hasattr(result, 'evidence') else [],
        )
        await emit("final_result", final.model_dump())
        if payload.consultation_id:
            await save_pipeline_timings(
                payload.consultation_id, result.stage_timings, _request_id_var.get()
            )
        await _harvest_machine_signals(result, payload.consultation_id)

    return await _sse_stream(request, producer, "clinical_plan_stream", consultation_id=payload.consultation_id)


@app.post("/clinical/plan/ddx/stream")
async def clinical_ddx_stream(request: Request, payload: ClinicalPlanRequest):
    """
    Stop-and-confirm phase 1: run ONLY Stage 2 (DDx) and stream it, then stop.

    Terminal event: `ddx_ready` with the ranked candidates.
    """
    from .clinical_workflow import run_ddx_only_streaming

    async def producer(emit):
        await run_ddx_only_streaming(payload.case, emit)

    return await _sse_stream(request, producer, "clinical_ddx_stream")


@app.post("/clinical/plan/resynthesize/stream")
async def clinical_resynthesize_stream(request: Request, payload: ResynthesizeRequest):
    """
    Re-run Stages 3–5 with clinician-selected diagnoses and stream SSE events.
    """
    from .clinical_workflow import run_resynthesize_streaming
    from .clinical_stages import DDxResult

    async def producer(emit):
        from .db_utils import save_pipeline_timings
        selected_ddx = [
            DDxResult(
                code=d.code,
                title=d.title,
                similarity=d.probability,
                reasoning=d.reasoning,
            )
            for d in payload.selected_diagnoses
        ]
        # Resolve Major: explicit payload.major_code wins; else the entry
        # tagged tier=="major"; else the first selected diagnosis.
        major_code = payload.major_code
        if major_code is None:
            tagged = next(
                (d.code for d in payload.selected_diagnoses if (d.tier or "").lower() == "major"),
                None,
            )
            major_code = tagged or (selected_ddx[0].code if selected_ddx else None)
        try:
            result = await run_resynthesize_streaming(
                payload.case, selected_ddx, emit, major_code=major_code,
            )
        except Exception as e:
            log_failed_job("clinical_resynthesize_stream", payload.case, str(e), request_id=_request_id_var.get())
            raise
        final = ClinicalPlanResponse(
            treatment_plan=result.treatment_plan,
            ddx=[d.model_dump() for d in result.ddx],
            cpgs_matched=[c.cpg_name for c in result.cpgs],
            elapsed_ms=result.elapsed_ms,
            stage_errors=[e.model_dump() for e in result.stage_errors],
            graph_navigator_rules=result.graph_navigator_rules,
            safety_report=result.safety_report,
            cpg_references=_derive_cpg_references(result.treatment_plan, getattr(result.safety_report, "flags", None)),
            follow_up_parsed=_parse_follow_up(result.treatment_plan.follow_up),
            evidence=[e.model_dump() for e in result.evidence] if hasattr(result, 'evidence') else [],
        )
        await emit("final_result", final.model_dump())
        if payload.consultation_id:
            await save_pipeline_timings(
                payload.consultation_id, result.stage_timings, _request_id_var.get()
            )
        await _harvest_machine_signals(result, payload.consultation_id)

    return await _sse_stream(request, producer, "clinical_resynthesize_stream", consultation_id=payload.consultation_id)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events."""
    try:
        # Get or create session
        session_id = await get_or_create_session(request)
        
        async def generate_stream():
            """Generate streaming response. Falls back to non-streaming for Bedrock (no tool+stream support)."""
            try:
                yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
                
                # Create dependencies
                deps = AgentDependencies(
                    session_id=session_id,
                    user_id=request.user_id
                )
                
                # Get conversation context
                context = await get_conversation_context(session_id)
                
                # Build input with context
                full_prompt = request.message
                if context:
                    context_str = "\n".join([
                        f"{msg['role']}: {msg['content']}"
                        for msg in context[-6:]
                    ])
                    full_prompt = f"Previous conversation:\n{context_str}\n\nCurrent question: {request.message}"
                
                # Save user message immediately
                await add_message(
                    session_id=session_id,
                    role="user",
                    content=request.message,
                    metadata={"user_id": request.user_id}
                )
                
                full_response = ""
                tools_used = []
                sources = []
                
                # Check if provider supports streaming with tools
                llm_provider = os.getenv('LLM_PROVIDER', 'openai').lower()
                
                if llm_provider == 'bedrock':
                    # Bedrock Llama 3.3 doesn't support tool use in streaming mode
                    # Fall back to non-streaming execution, then emit as SSE
                    result = await rag_agent.run(full_prompt, deps=deps)
                    full_response = result.output
                    tools_used = extract_tool_calls(result)
                    sources = extract_sources(result)
                    
                    # Emit the full response as a single text event
                    yield f"data: {json.dumps({'type': 'text', 'content': full_response})}\n\n"
                
                else:
                    # Stream using agent.iter() pattern (OpenAI, etc.)
                    async with rag_agent.iter(full_prompt, deps=deps) as run:
                        async for node in run:
                            if rag_agent.is_model_request_node(node):
                                # Stream tokens from the model
                                async with node.stream(run.ctx) as request_stream:
                                    async for event in request_stream:
                                        from pydantic_ai.messages import PartStartEvent, PartDeltaEvent, TextPartDelta
                                        
                                        if isinstance(event, PartStartEvent) and event.part.part_kind == 'text':
                                            delta_content = event.part.content
                                            yield f"data: {json.dumps({'type': 'text', 'content': delta_content})}\n\n"
                                            full_response += delta_content
                                            
                                        elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                                            delta_content = event.delta.content_delta
                                            yield f"data: {json.dumps({'type': 'text', 'content': delta_content})}\n\n"
                                            full_response += delta_content
                        
                        # Extract tools used and sources from the final result INSIDE the context manager
                        try:
                            result = run.result
                            if result:
                                tools_used = extract_tool_calls(result)
                                sources = extract_sources(result)
                        except Exception as e:
                            logger.warning(f"Failed to extract tools/sources: {e}")

                # Send tools used information
                if tools_used:
                    tools_data = [
                        {
                            "tool_name": tool.tool_name,
                            "args": tool.args,
                            "tool_call_id": tool.tool_call_id
                        }
                        for tool in tools_used
                    ]
                    yield f"data: {json.dumps({'type': 'tools', 'tools': tools_data})}\n\n"

                # Send sources information
                if sources:
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

                # Save assistant response
                await add_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    metadata={
                        "streamed": True,
                        "tool_calls": len(tools_used),
                        "sources_count": len(sources)
                    }
                )

                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                
            except Exception as e:
                import traceback
                logger.error(f"Stream error: {e}")
                logger.error(f"Full traceback: {traceback.format_exc()}")
                error_chunk = {
                    "type": "error",
                    "content": f"Stream error: {str(e)}"
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/vector")
async def search_vector(request: SearchRequest):
    """Vector search endpoint."""
    try:
        input_data = VectorSearchInput(
            query=request.query,
            limit=request.limit
        )
        
        start_time = datetime.now()
        results = await vector_search_tool(input_data)
        end_time = datetime.now()
        
        query_time = (end_time - start_time).total_seconds() * 1000
        
        return SearchResponse(
            results=results,
            total_results=len(results),
            search_type="vector",
            query_time_ms=query_time
        )
        
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/graph")
async def search_graph(request: SearchRequest):
    """Knowledge graph search endpoint."""
    try:
        input_data = GraphSearchInput(
            query=request.query
        )
        
        start_time = datetime.now()
        results = await graph_search_tool(input_data)
        end_time = datetime.now()
        
        query_time = (end_time - start_time).total_seconds() * 1000
        
        return SearchResponse(
            graph_results=results,
            total_results=len(results),
            search_type="graph",
            query_time_ms=query_time
        )
        
    except Exception as e:
        logger.error(f"Graph search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/hybrid")
async def search_hybrid(request: SearchRequest):
    """Hybrid search endpoint."""
    try:
        input_data = HybridSearchInput(
            query=request.query,
            limit=request.limit
        )
        
        start_time = datetime.now()
        results = await hybrid_search_tool(input_data)
        end_time = datetime.now()
        
        query_time = (end_time - start_time).total_seconds() * 1000
        
        return SearchResponse(
            results=results,
            total_results=len(results),
            search_type="hybrid",
            query_time_ms=query_time
        )
        
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Google Cloud Speech-to-Text proxy ──────────────────────────────────────
# Keeps the API key on the server; the frontend just POSTs raw audio.
@app.post("/clinical/stt")
async def speech_to_text(request: Request):
    """
    Accepts an audio file upload and returns Google Cloud STT transcript.

    The frontend sends audio recorded via MediaRecorder (webm/ogg/wav).
    This endpoint forwards it to Google Cloud Speech-to-Text REST API v1
    using the API key stored in .env (GOOGLE_CLOUD_STT_API_KEY).
    """
    import base64
    import httpx

    api_key = os.getenv("GOOGLE_CLOUD_STT_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_CLOUD_STT_API_KEY not configured")

    # Read the raw audio bytes from the request body
    content_type = request.headers.get("content-type", "")

    # Support both multipart/form-data and raw binary body
    if "multipart" in content_type:
        form = await request.form()
        audio_file = form.get("audio")
        if not audio_file:
            raise HTTPException(status_code=400, detail="No 'audio' field in form data")
        audio_bytes = await audio_file.read()
        file_content_type = getattr(audio_file, "content_type", "audio/webm")
    else:
        audio_bytes = await request.body()
        file_content_type = content_type or "audio/webm"

    if not audio_bytes or len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Audio data too small or empty")

    # Map browser MIME types to Google Cloud encoding enums
    encoding_map = {
        "audio/webm":       "WEBM_OPUS",
        "audio/ogg":        "OGG_OPUS",
        "audio/wav":        "LINEAR16",
        "audio/x-wav":      "LINEAR16",
        "audio/mp4":        "MP4",        # Chrome sometimes sends mp4
        "audio/mpeg":       "MP3",
    }

    # Determine encoding; fall back to WEBM_OPUS (most common from browsers)
    gcloud_encoding = "WEBM_OPUS"
    for mime, enc in encoding_map.items():
        if mime in file_content_type.lower():
            gcloud_encoding = enc
            break

    # Sample rate hint (WEBM_OPUS / OGG_OPUS auto-detect; LINEAR16 needs explicit)
    sample_rate = 48000 if "OPUS" in gcloud_encoding else 16000

    payload = {
        "config": {
            "encoding": gcloud_encoding,
            "sampleRateHertz": sample_rate,
            "languageCode": "en-US",
            "enableAutomaticPunctuation": True,
            "model": "latest_long",
            "useEnhanced": True,
            # Medical-specific hints for better clinical dictation
            "speechContexts": [{
                "phrases": [
                    "HPI", "CC", "PE", "ROS", "PMH", "PSH",
                    "NYHA", "LVEF", "eGFR", "HbA1c", "CKD",
                    "systolic", "diastolic", "mmHg", "bpm",
                    "hypertension", "diabetes", "diaphoresis",
                    "dyspnea", "tachycardia", "bradycardia",
                    "murmur", "edema", "crackles", "wheezing",
                    "metformin", "atorvastatin", "amlodipine",
                    "lisinopril", "aspirin", "clopidogrel",
                    "T2DM", "HTN", "CKD", "AF", "COPD",
                ],
                "boost": 15,
            }],
        },
        "audio": {
            "content": base64.b64encode(audio_bytes).decode("utf-8"),
        },
    }

    url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            detail = resp.text[:500]
            logger.error("Google STT API error %s: %s", resp.status_code, detail)
            raise HTTPException(status_code=502, detail=f"Google STT error: {detail}")

        result = resp.json()
        results = result.get("results", [])

        # Concatenate all transcript alternatives
        transcript_parts = []
        confidence_sum = 0.0
        count = 0
        for r in results:
            alts = r.get("alternatives", [])
            if alts:
                transcript_parts.append(alts[0].get("transcript", ""))
                confidence_sum += alts[0].get("confidence", 0.0)
                count += 1

        transcript = " ".join(transcript_parts).strip()
        avg_confidence = round(confidence_sum / count, 3) if count > 0 else 0.0

        return {
            "transcript": transcript,
            "confidence": avg_confidence,
            "language": "en-US",
        }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Google STT request timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("STT endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Consultation recording → GCS → diarize → summarize ────────────────────
@app.post("/clinical/consultation/process")
async def process_consultation(request: Request):
    """
    Accept a consultation audio recording, upload to GCS, diarize via Google
    Cloud STT longrunningrecognize (2-speaker), then summarize via Gemini Flash.

    Audio is deleted from GCS in a finally block — no PHI persists.
    Returns { transcript: [...], summary: str, confidence: float, duration_seconds: int }.
    If LLM summarization fails, summary is null and the transcript is still returned (200).
    """
    import asyncio
    import httpx
    from .clinical_stages import summarise_consultation
    from .gcs_audio import upload_consultation_audio, delete_consultation_audio

    api_key = os.getenv("GOOGLE_CLOUD_STT_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_CLOUD_STT_API_KEY not configured")

    bucket = os.getenv("GCS_CONSULTATION_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="GCS_CONSULTATION_BUCKET not configured")

    # ── Read audio (same multipart / raw-body logic as /clinical/stt) ────────
    content_type = request.headers.get("content-type", "")
    if "multipart" in content_type:
        form = await request.form()
        audio_file = form.get("audio")
        if not audio_file:
            raise HTTPException(status_code=400, detail="No 'audio' field in form data")
        audio_bytes = await audio_file.read()
        file_content_type = getattr(audio_file, "content_type", "audio/webm")
    else:
        audio_bytes = await request.body()
        file_content_type = content_type or "audio/webm"

    if not audio_bytes or len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Audio data too small or empty")

    audio_size = len(audio_bytes)

    # ── Encoding map (identical to /clinical/stt) ────────────────────────────
    encoding_map = {
        "audio/webm":  "WEBM_OPUS",
        "audio/ogg":   "OGG_OPUS",
        "audio/wav":   "LINEAR16",
        "audio/x-wav": "LINEAR16",
        "audio/mp4":   "MP4",
        "audio/mpeg":  "MP3",
    }
    gcloud_encoding = "WEBM_OPUS"
    for mime, enc in encoding_map.items():
        if mime in file_content_type.lower():
            gcloud_encoding = enc
            break
    sample_rate = 48000 if "OPUS" in gcloud_encoding else 16000

    # ── Upload to GCS ─────────────────────────────────────────────────────────
    try:
        gs_uri, object_key = upload_consultation_audio(audio_bytes, file_content_type)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("GCS upload failed: %s", e)
        raise HTTPException(status_code=502, detail=f"GCS upload failed: {e}")

    # ── Everything below is wrapped in try/finally to guarantee GCS cleanup ──
    result_data = None
    operation_name = None
    try:
        payload = {
            "config": {
                "encoding": gcloud_encoding,
                "sampleRateHertz": sample_rate,
                "languageCode": "en-US",
                "enableAutomaticPunctuation": True,
                "model": "latest_long",
                "useEnhanced": True,
                "diarizationConfig": {
                    "enableSpeakerDiarization": True,
                    "minSpeakerCount": 2,
                    "maxSpeakerCount": 2,
                },
                "speechContexts": [{
                    "phrases": [
                        "HPI", "CC", "PE", "ROS", "PMH", "PSH",
                        "NYHA", "LVEF", "eGFR", "HbA1c", "CKD",
                        "systolic", "diastolic", "mmHg", "bpm",
                        "hypertension", "diabetes", "diaphoresis",
                        "dyspnea", "tachycardia", "bradycardia",
                        "murmur", "edema", "crackles", "wheezing",
                        "metformin", "atorvastatin", "amlodipine",
                        "lisinopril", "aspirin", "clopidogrel",
                        "T2DM", "HTN", "CKD", "AF", "COPD",
                    ],
                    "boost": 15,
                }],
            },
            "audio": {"uri": gs_uri},  # gs:// URI — no base64 size limit
        }

        # ── Get OAuth Bearer token from ADC so Speech presents its service
        #    agent identity to GCS (API-key calls present "anonymous caller").
        #    x-goog-user-project is required for user ADC credentials to select
        #    the billing/quota project for the Speech API call.
        try:
            import google.auth
            import google.auth.transport.requests as ga_requests
            adc_creds, adc_project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            adc_creds.refresh(ga_requests.Request())
            bearer_token = adc_creds.token
            quota_project = (
                getattr(adc_creds, "_quota_project_id", None)
                or adc_project
                or os.getenv("GOOGLE_CLOUD_PROJECT", "")
            )
        except Exception as e:
            logger.error("Failed to obtain ADC token for Speech: %s", e)
            raise HTTPException(status_code=500, detail=f"ADC token error: {e}")

        speech_headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "x-goog-user-project": quota_project,
        }
        long_running_url = "https://speech.googleapis.com/v1/speech:longrunningrecognize"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(long_running_url, json=payload, headers=speech_headers)

            if resp.status_code != 200:
                detail = resp.text[:500]
                logger.error("Google LongRunning STT error %s: %s", resp.status_code, detail)
                raise HTTPException(status_code=502, detail=f"Google STT error: {detail}")

            operation = resp.json()
            operation_name = operation.get("name")
            if not operation_name:
                raise HTTPException(status_code=502, detail="Google STT did not return an operation name")

        except HTTPException:
            raise
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Google STT longrunningrecognize timed out")
        except Exception as e:
            logger.error("Consultation STT submit error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

        # ── Poll until done (3 s intervals, 10 min hard timeout) ─────────────
        poll_url = f"https://speech.googleapis.com/v1/operations/{operation_name}"
        max_wait_seconds = 600  # 10 min — covers 10-min recordings with headroom
        poll_interval = 3
        elapsed = 0

        try:
            async with httpx.AsyncClient(timeout=15.0) as poll_client:
                while elapsed < max_wait_seconds:
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval
                    poll_resp = await poll_client.get(poll_url, headers=speech_headers)
                    if poll_resp.status_code != 200:
                        logger.warning("Consultation STT poll HTTP %s", poll_resp.status_code)
                        continue
                    op = poll_resp.json()
                    if op.get("done"):
                        if "error" in op:
                            raise HTTPException(
                                status_code=502,
                                detail=f"Google STT operation failed: {op['error']}",
                            )
                        result_data = op.get("response", {})
                        break

            if result_data is None:
                raise HTTPException(status_code=504, detail="Google STT operation timed out after 10 minutes")

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Consultation STT poll error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

        # ── Parse diarized result ─────────────────────────────────────────────
        results = result_data.get("results", [])
        confidence_sum = 0.0
        confidence_count = 0
        for r in results:
            alts = r.get("alternatives", [])
            if alts and alts[0].get("confidence"):
                confidence_sum += alts[0]["confidence"]
                confidence_count += 1
        avg_confidence = round(confidence_sum / confidence_count, 3) if confidence_count > 0 else 0.0

        # With diarization the last result carries the full word list with speakerTag
        word_list = []
        for r in reversed(results):
            alts = r.get("alternatives", [])
            if alts:
                words = alts[0].get("words", [])
                if words:
                    word_list = words
                    break

        if not word_list:
            # No word-level data — fall back to flat transcript, label as Doctor
            flat = " ".join(
                alts[0].get("transcript", "")
                for r in results
                for alts in [r.get("alternatives", [])]
                if alts
            ).strip()
            transcript_turns = [{"speaker": "Doctor", "text": flat}] if flat else []
            labeled_str = f"Doctor: {flat}" if flat else ""
        else:
            turns: list[dict] = []
            current_tag = word_list[0].get("speakerTag", 1)
            current_words: list[str] = []
            for w in word_list:
                tag = w.get("speakerTag", current_tag)
                word = w.get("word", "")
                if tag == current_tag:
                    current_words.append(word)
                else:
                    turns.append({"tag": current_tag, "text": " ".join(current_words)})
                    current_tag = tag
                    current_words = [word]
            if current_words:
                turns.append({"tag": current_tag, "text": " ".join(current_words)})

            first_tag = turns[0]["tag"] if turns else 1
            tag_to_label: dict[int, str] = {first_tag: "Doctor"}
            transcript_turns = []
            labeled_lines = []
            for t in turns:
                label = tag_to_label.setdefault(t["tag"], "Patient")
                transcript_turns.append({"speaker": label, "text": t["text"]})
                labeled_lines.append(f"{label}: {t['text']}")
            labeled_str = "\n".join(labeled_lines)

        # Estimate duration (~15 KB/s for WEBM_OPUS 48 kHz)
        duration_seconds = max(1, audio_size // 15_000)

        # ── Summarize via Gemini Flash ────────────────────────────────────────
        summary = None
        if labeled_str:
            try:
                summary = await summarise_consultation(labeled_str)
            except Exception as e:
                logger.warning("summarise_consultation raised unexpectedly: %s", e)
                summary = None

        return {
            "transcript": transcript_turns,
            "summary": summary or None,
            "confidence": avg_confidence,
            "duration_seconds": duration_seconds,
        }

    finally:
        # Always delete the GCS blob — gcs_audio.delete_consultation_audio
        # logs a warning on failure and never raises.
        delete_consultation_audio(object_key)


# Documents endpoint removed - use vector_search or graph_search instead


@app.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Get session information."""
    try:
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Delivery endpoints ───────────────────────────────────────────────────────

class DeliveryEnqueueRequest(_BaseModel):
    consultation_id: int
    clinician_name: Optional[str] = None
    # Recipient address supplied by the clinician via the UI form. When set,
    # it overrides the patient's stored email and bypasses the on-file/consent
    # gate (the clinician is explicitly directing the send).
    recipient: Optional[str] = None


@app.post("/delivery/enqueue")
async def delivery_enqueue(body: DeliveryEnqueueRequest):
    """Enqueue a care-plan delivery job for the given consultation."""
    from .db_utils import db_pool as _pool
    recipient = (body.recipient or "").strip() or None
    try:
        async with _pool.acquire() as conn:
            if recipient:
                # Find the patient NRIC for this consultation and persist the email
                patient_nric = await conn.fetchval(
                    "SELECT patient_nric FROM consultations WHERE id = $1",
                    body.consultation_id
                )
                if patient_nric:
                    await conn.execute(
                        """
                        UPDATE patients 
                        SET email = $1, 
                            email_consent_at = now(), 
                            updated_at = now()
                        WHERE nric = $2
                        """,
                        recipient, patient_nric
                    )

            rows = await conn.fetch(
                "SELECT * FROM enqueue_delivery_job($1::integer, $2::text, $3::text)",
                body.consultation_id,
                body.clinician_name,
                recipient,
            )
        if not rows:
            raise HTTPException(status_code=400, detail="enqueue returned no row")
        row = rows[0]
        return {"job_id": str(row["job_id"]), "status": row["status"], "recipient": row["recipient"]}
    except Exception as exc:
        msg = str(exc)
        if "no email" in msg or "no_email" in msg:
            raise HTTPException(status_code=400, detail="patient has no email on file")
        if "not consented" in msg or "no_consent" in msg:
            raise HTTPException(status_code=400, detail="patient has not consented to email delivery")
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        logger.error("delivery enqueue error: %s", exc)
        raise HTTPException(status_code=500, detail=msg)


@app.get("/delivery/status/{consultation_id}")
async def delivery_status(consultation_id: int):
    """Return the latest delivery job for a consultation."""
    from .db_utils import db_pool as _pool
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, status, message_id, error, attempts, created_at, delivered_at
              FROM delivery_jobs
             WHERE consultation_id = $1
             ORDER BY created_at DESC
             LIMIT 1
            """,
            consultation_id,
        )
    if not row:
        return None
    return {
        "job_id": str(row["id"]),
        "status": row["status"],
        "message_id": row["message_id"],
        "error": row["error"],
        "attempts": row["attempts"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "delivered_at": row["delivered_at"].isoformat() if row["delivered_at"] else None,
    }


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler.

    Returns a real `JSONResponse` instead of a bare Pydantic model — FastAPI
    needs a `Response` here, not the model, otherwise it tries to *call* the
    model and raises `TypeError: 'ErrorResponse' object is not callable`,
    masking whatever real error fired in the first place.

    `exc_info=True` logs the traceback so the actual root-cause line shows up
    in the uvicorn console rather than just the one-liner.
    """
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    payload = ErrorResponse(
        error=str(exc),
        error_type=type(exc).__name__,
        request_id=str(uuid.uuid4()),
    )
    return JSONResponse(status_code=500, content=payload.model_dump())


# Development server
if __name__ == "__main__":
    uvicorn.run(
        "agent.api:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=APP_ENV == "development",
        log_level=LOG_LEVEL.lower()
    )