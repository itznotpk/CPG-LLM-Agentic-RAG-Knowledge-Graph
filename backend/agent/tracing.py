"""
OpenTelemetry tracing setup — env-gated, fail-open.

Enabled only when OTEL_TRACING_ENABLED=true. When disabled (the default) or
when the opentelemetry packages are missing, every helper in this module is a
zero-overhead no-op — the pipeline must never break or slow down because of
tracing.

Env vars:
    OTEL_TRACING_ENABLED        — "true"/"1"/"yes" to enable (default: off)
    OTEL_SERVICE_NAME           — span service name (default: cpg-clinical-api)
    OTEL_TRACES_EXPORTER        — "otlp" (default) or "console" (print to stdout)
    OTEL_EXPORTER_OTLP_ENDPOINT — OTLP/HTTP collector base URL
                                  (default: http://localhost:4318, e.g. Jaeger all-in-one)
    LOGFIRE_TOKEN               — set to also send traces to the Logfire cloud UI
                                  (prompt/completion capture works locally without it)
    LOGFIRE_DISABLED            — "true" to skip logfire and use the plain OTel provider

What gets traced when enabled:
    - every FastAPI request (root span, via FastAPIInstrumentor)
    - every httpx call — all LLM calls (Gemini/MiMo/OpenAI-compat SDKs use httpx
      under the hood), Europe PMC EBM lookups, delivery polling
    - every asyncpg query — pgvector DDx/retrieval/routing + Supabase pool
    - every pipeline stage — stage spans opened by clinical_workflow._maybe_time
All spans carry the X-Request-ID correlation id (see tag_request) so one id
links the FastAPI log, SSE event log, failed-job record, Supabase row AND the
trace waterfall.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Mirrors api._request_id_var. Lives here (not imported from api) so that
# clinical_workflow → tracing never creates an import cycle with api → clinical_workflow.
request_id_var: ContextVar[str] = ContextVar("otel_request_id", default="")


def _env_enabled() -> bool:
    return os.getenv("OTEL_TRACING_ENABLED", "false").strip().lower() in ("1", "true", "yes")


try:
    from opentelemetry import trace as _trace
    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover — packages present in the project venv
    _trace = None
    _OTEL_AVAILABLE = False

_initialized = False


def tracing_active() -> bool:
    """True only when tracing was successfully set up this process."""
    return _initialized


def _build_exporter_processor():
    """BatchSpanProcessor for the configured exporter (otlp default, or console)."""
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    if os.getenv("OTEL_TRACES_EXPORTER", "otlp").strip().lower() == "console":
        return BatchSpanProcessor(ConsoleSpanExporter())
    # OTLPSpanExporter reads OTEL_EXPORTER_OTLP_ENDPOINT itself
    # (default http://localhost:4318) and appends /v1/traces.
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    return BatchSpanProcessor(OTLPSpanExporter())


def _try_logfire_setup() -> bool:
    """Prefer routing the TracerProvider through logfire when the package is
    available: this unlocks logfire.instrument_openai() — prompt/completion/
    token capture on every openai-SDK LLM call (MiMo, Gemini via OpenAI-compat).
    Those spans flow BOTH to the Logfire cloud UI (only when LOGFIRE_TOKEN is
    set) AND to the local OTLP/console exporter via additional_span_processors,
    so Jaeger shows prompt content even with no Logfire account.

    Opt out with LOGFIRE_DISABLED=true. Fail-open: any error falls back to the
    plain-OTel provider path."""
    if os.getenv("LOGFIRE_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        return False
    try:
        import logfire
        logfire.configure(
            service_name=os.getenv("OTEL_SERVICE_NAME", "cpg-clinical-api"),
            send_to_logfire="if-token-present",
            additional_span_processors=[_build_exporter_processor()],
            console=False,
        )
        logfire.instrument_openai()
        logger.info(
            "logfire configured (cloud send: %s; openai prompt capture: on)",
            "on" if os.getenv("LOGFIRE_TOKEN") else "off — set LOGFIRE_TOKEN to enable",
        )
        return True
    except Exception as e:
        logger.warning("logfire setup failed — falling back to plain OTel: %s", e)
        return False


def setup_tracing(app=None) -> bool:
    """Configure the TracerProvider + exporter and auto-instrument FastAPI,
    httpx, asyncpg and botocore. Call once at process start (api.py does this
    right after app creation). Idempotent; returns True when tracing is live.

    Every step is fail-open: a missing exporter/instrumentor logs a warning
    and the app continues untraced.
    """
    global _initialized
    if _initialized:
        return True
    if not (_env_enabled() and _OTEL_AVAILABLE):
        return False
    if not _try_logfire_setup():
        try:
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider

            resource = Resource.create({
                "service.name": os.getenv("OTEL_SERVICE_NAME", "cpg-clinical-api"),
            })
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(_build_exporter_processor())
            _trace.set_tracer_provider(provider)
        except Exception as e:
            logger.warning("OpenTelemetry setup failed — tracing disabled: %s", e)
            return False

    # Auto-instrumentors — each optional and fail-open.
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
        except Exception as e:
            logger.warning("FastAPI instrumentation failed (continuing): %s", e)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except Exception as e:
        logger.warning("httpx instrumentation failed (continuing): %s", e)
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
        AsyncPGInstrumentor().instrument()
    except Exception as e:
        logger.warning("asyncpg instrumentation failed (continuing): %s", e)
    try:
        # Bedrock Titan embedding calls (DDx vector search + Stage-4 retrieval)
        # go through boto3/botocore, not httpx — instrument separately.
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
        BotocoreInstrumentor().instrument()
    except Exception as e:
        logger.warning("botocore instrumentation failed (continuing): %s", e)

    _initialized = True
    logger.info(
        "OpenTelemetry tracing enabled (exporter=%s, endpoint=%s)",
        os.getenv("OTEL_TRACES_EXPORTER", "otlp"),
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
    )
    return True


def shutdown_tracing() -> None:
    """Flush pending spans on process shutdown. Fail-open."""
    if not _initialized:
        return
    try:
        provider = _trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception as e:
        logger.warning("OpenTelemetry shutdown flush failed: %s", e)


def tag_request(request_id: str) -> None:
    """Stamp the correlation id onto the tracing context + current (HTTP root)
    span. Called from api.py's correlation-id middleware. Fail-open no-op when
    tracing is off."""
    try:
        request_id_var.set(request_id)
        if _initialized:
            span = _trace.get_current_span()
            if span is not None:
                span.set_attribute("request_id", request_id)
    except Exception:
        pass


def add_span_attributes(**attributes) -> None:
    """Stamp key/value attributes onto the CURRENT span (e.g. the pipeline
    stage span opened by clinical_workflow._maybe_time). Lets stage runners
    record outcome summaries — ddx.count, cpg.names, plan.confidence — so a
    Jaeger trace reads as a story without cross-referencing logs.

    Fail-open no-op when tracing is off; None values are skipped; non-scalar
    values are stringified (OTel attributes must be scalars or scalar lists)."""
    if not _initialized:
        return
    try:
        span = _trace.get_current_span()
        if span is None:
            return
        for key, value in attributes.items():
            if value is None:
                continue
            if not isinstance(value, (str, bool, int, float)):
                value = str(value)
            span.set_attribute(key, value)
    except Exception:
        pass


@contextmanager
def stage_span(name: str, **attributes):
    """Open a named span (child of the current context — under FastAPI this is
    the HTTP request span, so stage spans nest into the request waterfall).

    Zero-overhead no-op when tracing is not active. Never raises."""
    if not _initialized:
        yield None
        return
    tracer = _trace.get_tracer("cpg.pipeline")
    with tracer.start_as_current_span(name) as span:
        try:
            rid = request_id_var.get()
            if rid:
                span.set_attribute("request_id", rid)
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        except Exception:
            pass
        yield span
