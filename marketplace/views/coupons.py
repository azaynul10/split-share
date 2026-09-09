"""
Coupon validation endpoint.

The promo code box on the listing page posts here. The listing price is read
locally so the browser never gets to state the subtotal, then the code itself
is checked by the coupon service over HTTP (see `coupon_service/`). The final
authoritative check still happens inside the order transaction in orders.py;
this endpoint is the interactive pre-check.

Each way the coupon service can fail maps to a distinct status here, and the
failure is recorded on the request span, so an outage at the service boundary
is visible to monitoring rather than hidden behind a friendly message:

    connection refused  -> 503
    timeout             -> 504
    upstream 5xx        -> 502
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from ..db_utils import QueryError, fetch_one

logger = logging.getLogger(__name__)

SELECT_LISTING_PRICE = """
    SELECT price_per_slot, available_slots, status
    FROM Listings
    WHERE listing_id = %s
"""

TWO_PLACES = Decimal("0.01")


class CouponServiceError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _money(value):
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _record_failure(exc):
    span = trace.get_current_span()
    if span.is_recording():
        span.record_exception(exc, attributes={"peer.service": "split-share-coupons"})
        span.set_status(StatusCode.ERROR, type(exc).__name__)


def check_coupon(code, subtotal):
    """Ask the coupon service to validate `code` against `subtotal`.

    Returns (status, body) from the service. Raises CouponServiceError with
    the HTTP status this endpoint should return when the service cannot answer.
    """
    url = f"{settings.COUPON_SERVICE_URL}/validate"
    try:
        response = requests.post(
            url,
            json={"code": code, "subtotal": f"{subtotal:.2f}"},
            timeout=settings.COUPON_SERVICE_TIMEOUT,
        )
    except requests.ConnectionError as exc:
        # Includes ConnectTimeout: failing to connect at all is "unreachable",
        # whether the port refused us or never answered.
        logger.error("coupon service unreachable: %s (%s)", url, exc)
        _record_failure(exc)
        raise CouponServiceError(503, "We could not check that code right now.") from exc
    except requests.Timeout as exc:
        logger.error("coupon service timed out after %ss: %s", settings.COUPON_SERVICE_TIMEOUT, url)
        _record_failure(exc)
        raise CouponServiceError(504, "Checking that code is taking too long. Try again.") from exc

    if response.status_code >= 500:
        exc = CouponServiceError(502, "We could not check that code right now.")
        logger.error("coupon service returned %s: %s", response.status_code, response.text[:200])
        _record_failure(exc)
        raise exc

    return response.status_code, response.json()


@require_POST
def validate_coupon_api(request):
    """JSON endpoint used by the promo code box on the listing page."""
    code = request.POST.get("code", "")
    listing_id = request.POST.get("listing_id", "")
    slots_raw = request.POST.get("slots", "1")

    try:
        slots = max(1, int(slots_raw))
    except (TypeError, ValueError):
        slots = 1

    try:
        listing = fetch_one(SELECT_LISTING_PRICE, [listing_id])
    except QueryError:
        return JsonResponse(
            {"valid": False, "message": "We could not reach the database."}, status=503
        )

    if listing is None:
        return JsonResponse(
            {"valid": False, "message": "That listing no longer exists."}, status=404
        )

    if slots > listing["available_slots"]:
        return JsonResponse(
            {
                "valid": False,
                "message": f"Only {listing['available_slots']} slot(s) are available.",
            }
        )

    subtotal = _money(listing["price_per_slot"]) * slots

    try:
        status, outcome = check_coupon(code, subtotal)
    except CouponServiceError as exc:
        return JsonResponse({"valid": False, "message": exc.message}, status=exc.status)

    return JsonResponse(outcome, status=status)
