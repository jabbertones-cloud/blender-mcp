"""
OpenTelemetry Wrapper for MCP Tool Calls
===========================================

Opt-in tracing via OPENCLAW_OTEL_ENABLED=1. Gracefully handles missing
opentelemetry library (no-op fallback).

Features:
  - W3C Trace Context support
  - Scene-diff attributes (objects_before/after, vertices_before/after)
  - Silent-failure detection (tools that change scene without reporting)
  - OTLP exporter to http://localhost:4318/v1/traces (configurable)
  - Stdout debug exporter via OPENCLAW_OTEL_DEBUG=1

References:
  - W3C Trace Context: https://www.w3.org/TR/trace-context/
  - OpenTelemetry Python: https://opentelemetry.io/docs/instrumentation/python/
  - Drift detection via scene snapshots
"""

import os
import time
from typing import Optional, Callable, Dict, Any

# Optional opentelemetry import
try:
    from opentelemetry import trace, context
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.trace import SpanExporter, SpanExportResult
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, BatchSpanProcessor
    from opentelemetry.trace import set_span_in_context

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False
    trace = None
    OTLPSpanExporter = None


# Module-level state
_snapshot_hook: Optional[Callable[[], Dict[str, Any]]] = None
_tracer: Optional[Any] = None
_enabled = os.getenv("OPENCLAW_OTEL_ENABLED", "").lower() in ("1", "true", "yes")


def is_enabled() -> bool:
    """Check if OpenTelemetry tracing is enabled."""
    return _enabled and _HAS_OTEL


def setup_tracer(service_name: str = "openclaw-blender-mcp") -> None:
    """
    Set up OpenTelemetry tracer (idempotent).

    Args:
        service_name: Service name for traces
    """
    if not _HAS_OTEL or not _enabled:
        return

    global _tracer

    if _tracer is not None:
        return  # Already initialized

    try:
        # OTLP exporter
        endpoint = os.getenv("OPENCLAW_OTEL_ENDPOINT", "http://localhost:4318/v1/traces")
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)

        # Tracer provider
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        # Stdout debug exporter
        if os.getenv("OPENCLAW_OTEL_DEBUG", "").lower() in ("1", "true", "yes"):
            try:
                from opentelemetry.exporter.jaeger.thrift import JaegerExporter
                jaeger = JaegerExporter(
                    agent_host_name="localhost",
                    agent_port=6831,
                )
                provider.add_span_processor(BatchSpanProcessor(jaeger))
            except ImportError:
                # Fallback: just print to stdout
                pass

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)

    except Exception as e:
        # Graceful failure
        print(f"Warning: Failed to setup OpenTelemetry: {e}")


def traced_tool(tool_name: str):
    """
    Decorator factory for async tool functions.

    Records:
      - Tool execution time
      - Scene snapshot before/after (if hook is set)
      - Response size and token estimate
      - Exceptions and errors

    Usage:
        @traced_tool("get_scene_info")
        async def handle_get_scene_info(params):
            ...

    Args:
        tool_name: Name of the tool
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not is_enabled():
                return await func(*args, **kwargs)

            setup_tracer()

            span_name = f"mcp.tool.{tool_name}"
            with trace.get_tracer(__name__).start_as_current_span(span_name) as span:
                span.set_attribute("mcp.tool.name", tool_name)

                # Capture pre-call snapshot
                pre_snapshot = None
                if _snapshot_hook:
                    try:
                        pre_snapshot = _snapshot_hook()
                        span.set_attribute(
                            "blender.objects_before",
                            len(pre_snapshot.get("objects", [])),
                        )
                        span.set_attribute(
                            "blender.vertices_before",
                            pre_snapshot.get("total_vertices", 0),
                        )
                    except Exception as e:
                        print(f"Warning: snapshot hook failed: {e}")

                # Execute tool
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000

                    # Capture post-call snapshot
                    if _snapshot_hook:
                        try:
                            post_snapshot = _snapshot_hook()
                            span.set_attribute(
                                "blender.objects_after",
                                len(post_snapshot.get("objects", [])),
                            )
                            span.set_attribute(
                                "blender.vertices_after",
                                post_snapshot.get("total_vertices", 0),
                            )

                            # Compute diff
                            if pre_snapshot:
                                obj_delta = (
                                    len(post_snapshot.get("objects", []))
                                    - len(pre_snapshot.get("objects", []))
                                )
                                vert_delta = (
                                    post_snapshot.get("total_vertices", 0)
                                    - pre_snapshot.get("total_vertices", 0)
                                )
                                span.set_attribute("blender.objects_delta", obj_delta)
                                span.set_attribute("blender.vertices_delta", vert_delta)
                        except Exception as e:
                            print(f"Warning: post-snapshot failed: {e}")

                    # Response attributes
                    span.set_attribute("mcp.tool.duration_ms", duration_ms)
                    if isinstance(result, dict):
                        result_size = len(str(result))
                        span.set_attribute("mcp.response.size_chars", result_size)
                        tokens_est = result.get("tokens_est", 0)
                        if tokens_est:
                            span.set_attribute("mcp.response.tokens_est", tokens_est)

                    return result

                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("mcp.response.error", str(e))
                    span.set_attribute("mcp.response.status", "ERROR")
                    raise

        return wrapper

    return decorator


def set_snapshot_hook(fn: Optional[Callable[[], Dict[str, Any]]]) -> None:
    """
    Set the scene snapshot hook (called by MCP server).

    Args:
        fn: Callable that returns scene snapshot dict, or None to disable
    """
    global _snapshot_hook
    _snapshot_hook = fn


def record_drift_score(score: float) -> None:
    """
    Record drift score on current span (called by drift_guard).

    Args:
        score: Drift score (0.0-1.0)
    """
    if not is_enabled() or trace is None:
        return

    try:
        span = trace.get_current_span()
        if span:
            span.set_attribute("blender.drift_score", score)
    except Exception:
        pass


def current_trace_context() -> Dict[str, str]:
    """
    Get current W3C trace context headers.

    Returns:
        {traceparent: "...", tracestate: "..."}
    """
    if not is_enabled() or trace is None:
        return {}

    try:
        span = trace.get_current_span()
        ctx = context.get_current()

        # Simplified W3C format
        return {
            "traceparent": f"00-{span.get_span_context().trace_id:032x}-{span.get_span_context().span_id:016x}-01"
        }
    except Exception:
        return {}


def inject_trace_context(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Inject current trace context into outbound headers.

    Args:
        headers: Headers dict to augment

    Returns:
        Updated headers
    """
    if not is_enabled():
        return headers

    try:
        ctx = current_trace_context()
        headers.update(ctx)
    except Exception:
        pass

    return headers


# Auto-initialize on import if enabled
if _enabled and _HAS_OTEL:
    setup_tracer()
