"""
Coupon service: a separate process that owns promo-code validation.

The Django app calls POST /validate over HTTP instead of querying the Coupons
table itself, which puts a real service boundary in the request path. Trace
context arrives in the `traceparent` header, so a browse-page promo check shows
up as one trace spanning both services.

Endpoints
    POST /validate        {"code": "SAVE10", "subtotal": "12.50"} -> validation result
    GET  /health          {"status": "ok"} once the database answers
    GET  /_fault?mode=X   demo-only fault injection: none | slow | error

Fault injection is what makes this service useful as a test subject. `slow`
sleeps past the caller's timeout; `error` raises inside the request so the
service returns a 500. Stopping the process altogether covers the third case.

Run with `python -m coupon_service` (defaults to port 8001).
"""

import os
import time
from decimal import Decimal, InvalidOperation

import MySQLdb
from flask import Flask, jsonify, request
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from .validation import validate_coupon

app = Flask(__name__)

FAULT = {"mode": "none"}
FAULT_MODES = ("none", "slow", "error")
SLOW_SECONDS = float(os.environ.get("COUPON_FAULT_SLOW_SECONDS", "5"))


def _connect():
    return MySQLdb.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        passwd=os.environ.get("DB_PASSWORD", ""),
        db=os.environ.get("DB_NAME", "split_share"),
        charset="utf8mb4",
        connect_timeout=3,
    )


def _fetch_one(sql, params):
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))
    finally:
        conn.close()


def _record_failure(exc):
    span = trace.get_current_span()
    if span.is_recording():
        span.record_exception(exc)
        span.set_status(StatusCode.ERROR, type(exc).__name__)


def _exported_service_name():
    resource = getattr(trace.get_tracer_provider(), "resource", None)
    if resource is None:
        return None
    return resource.attributes.get("service.name")


@app.get("/health")
def health():
    body = {"status": "ok", "service": _exported_service_name(), "fault": FAULT["mode"]}
    try:
        _fetch_one("SELECT 1", [])
    except MySQLdb.Error as exc:
        _record_failure(exc)
        body.update(status="degraded", database="unreachable")
        return jsonify(body), 503
    return jsonify(body)


@app.get("/_fault")
def set_fault():
    mode = request.args.get("mode", "none")
    if mode not in FAULT_MODES:
        return jsonify({"error": f"mode must be one of {FAULT_MODES}"}), 400
    FAULT["mode"] = mode
    return jsonify({"fault": mode})


@app.post("/validate")
def validate():
    if FAULT["mode"] == "slow":
        time.sleep(SLOW_SECONDS)
    elif FAULT["mode"] == "error":
        raise RuntimeError("Injected fault: coupon rules engine unavailable")

    payload = request.get_json(silent=True) or {}
    try:
        subtotal = Decimal(str(payload.get("subtotal", "0")))
    except InvalidOperation:
        return jsonify({"error": "subtotal must be a decimal string"}), 400

    try:
        outcome = validate_coupon(payload.get("code", ""), subtotal, _fetch_one)
    except MySQLdb.Error as exc:
        _record_failure(exc)
        return jsonify({"valid": False, "message": "We could not check that code."}), 503

    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("coupon.code", outcome["code"])
        span.set_attribute("coupon.valid", outcome["valid"])

    return jsonify(
        {
            "valid": outcome["valid"],
            "message": outcome["message"],
            "code": outcome["code"],
            "discount_percent": outcome["discount_percent"],
            "subtotal": f"{outcome['subtotal']:.2f}",
            "discount_amount": f"{outcome['discount_amount']:.2f}",
            "total": f"{outcome['total']:.2f}",
        }
    )
