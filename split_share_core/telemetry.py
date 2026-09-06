"""
OpenTelemetry setup for Sub-Share.

Called once from manage.py and wsgi.py, before Django builds its request
handler. Produces one server span per HTTP request (Django instrumentor) with
child spans for every SQL statement (MySQLdb instrumentor). Because the app
uses raw SQL through db_utils, the DB spans carry the exact statement text,
which is what makes the traces useful to an observability tool.

Where spans go is decided purely by standard OTel environment variables, so
pointing this at Bluebox, a Dynatrace tenant, or a local collector is a config
change and not a code change:

    OTEL_EXPORTER_OTLP_ENDPOINT   base URL, e.g. http://localhost:4318 or
                                  https://{env}.live.dynatrace.com/api/v2/otlp
    OTEL_EXPORTER_OTLP_HEADERS    e.g. Authorization=Api-Token%20dt0c01.XXXX
    OTEL_SERVICE_NAME             defaults to split-share-web
    OTEL_SDK_DISABLED=true        turn everything off

If OTEL_EXPORTER_OTLP_ENDPOINT is not set, spans are printed to the console so
the instrumentation can be verified with nothing else running.
"""

import os

_configured = False


def setup_telemetry():
    global _configured
    if _configured or os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true":
        return
    _configured = True

    from opentelemetry import trace
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.mysqlclient import MySQLClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "split-share-web"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "dev"),
            "deployment.environment": os.environ.get("DEPLOYMENT_ENV", "local"),
        }
    )
    provider = TracerProvider(resource=resource)

    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(formatter=_one_line)))

    trace.set_tracer_provider(provider)

    DjangoInstrumentor().instrument(response_hook=_tag_user)
    MySQLClientInstrumentor().instrument(
        enable_commenter=False,
        capture_parameters=False,
    )


def _tag_user(span, request, response):
    """Attach the logged-in user id and role once SessionMiddleware has run."""
    if not span.is_recording():
        return
    user_id = request.session.get("user_id")
    if user_id:
        span.set_attribute("enduser.id", str(user_id))
        role = request.session.get("role")
        if role:
            span.set_attribute("enduser.role", role)


def _one_line(span):
    """Compact console format: one span per line instead of a JSON blob."""
    ctx = span.get_span_context()
    duration_ms = (span.end_time - span.start_time) / 1_000_000 if span.end_time else 0
    attrs = span.attributes or {}
    detail = attrs.get("db.statement") or attrs.get("http.target") or ""
    detail = " ".join(str(detail).split())[:90]
    status = span.status.status_code.name
    return (
        f"[otel] {ctx.trace_id:032x} {span.kind.name:<6} {duration_ms:7.1f}ms "
        f"{status:<5} {span.name} {detail}\n"
    )
