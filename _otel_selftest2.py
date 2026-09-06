"""Capture real Django request spans and POST them to the OTLP endpoint, then
print the raw response including partialSuccess (which the SDK ignores).

Run from the terminal where OTEL_EXPORTER_OTLP_ENDPOINT / _HEADERS are set.
"""

import os
from urllib.parse import unquote

import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "split_share_core.settings")

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402
from opentelemetry import trace  # noqa: E402
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans  # noqa: E402
from opentelemetry.instrumentation.django import DjangoInstrumentor  # noqa: E402
from opentelemetry.instrumentation.mysqlclient import MySQLClientInstrumentor  # noqa: E402
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse  # noqa: E402
from opentelemetry.sdk.resources import Resource  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult  # noqa: E402

endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].rstrip("/") + "/v1/traces"
headers = {"Content-Type": "application/x-protobuf"}
for pair in os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "").split(","):
    if "=" in pair:
        k, v = pair.split("=", 1)
        headers[k.strip()] = unquote(v.strip())


class Collect(SpanExporter):
    def __init__(self):
        self.items = []

    def export(self, batch):
        self.items.extend(batch)
        return SpanExportResult.SUCCESS


collector = Collect()
provider = TracerProvider(resource=Resource.create({"service.name": "split-share-web"}))
provider.add_span_processor(SimpleSpanProcessor(collector))
trace.set_tracer_provider(provider)
DjangoInstrumentor().instrument()
MySQLClientInstrumentor().instrument(enable_commenter=False, capture_parameters=False)

c = Client(HTTP_HOST="127.0.0.1")
print("GET /browse/     ->", c.get("/browse/").status_code)
print("GET /listing/1/  ->", c.get("/listing/1/").status_code)
print(f"captured {len(collector.items)} spans:")
for s in collector.items:
    attrs = s.attributes or {}
    longest = max((len(str(v)) for v in attrs.values()), default=0)
    print(f"  {s.kind.name:<7} {s.name:<35} attrs={len(attrs):<3} longest_value={longest}")


def post(spans, label):
    body = encode_spans(spans).SerializePartialToString()
    r = requests.post(endpoint, data=body, headers=headers, timeout=15)
    print(f"\n[{label}] {len(spans)} spans, {len(body)} bytes -> HTTP {r.status_code}")
    if r.content:
        try:
            resp = ExportTraceServiceResponse()
            resp.ParseFromString(r.content)
            ps = resp.partial_success
            print(f"  partialSuccess: rejected_spans={ps.rejected_spans} error={ps.error_message!r}")
        except Exception:
            print("  body:", r.text[:500])
    else:
        print("  empty body (full success)")


post(collector.items, "all spans")
servers = [s for s in collector.items if s.kind.name == "SERVER"]
clients = [s for s in collector.items if s.kind.name == "CLIENT"]
post(servers, "SERVER only")
post(clients[:3], "first 3 CLIENT")
post(clients[3:], "remaining CLIENT")
