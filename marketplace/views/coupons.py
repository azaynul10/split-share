"""
Coupon validation.

A code has to clear three separate gates before it discounts anything:
switched on, inside its date window, and not used up. The seed data contains
one code that fails each gate, so all four outcomes are demonstrable.

The amount is always recalculated from the listing price held in the database.
The browser never gets to tell the server what the subtotal is.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from ..db_utils import QueryError, fetch_one

SELECT_COUPON_BY_CODE = """
    SELECT
        coupon_id,
        code,
        description,
        discount_percent,
        valid_from,
        valid_until,
        usage_limit,
        times_used,
        is_active,
        (CURDATE() BETWEEN valid_from AND valid_until) AS in_date_window,
        (times_used < usage_limit)                     AS has_uses_left
    FROM Coupons
    WHERE code = %s
"""

SELECT_LISTING_PRICE = """
    SELECT price_per_slot, available_slots, status
    FROM Listings
    WHERE listing_id = %s
"""

TWO_PLACES = Decimal("0.01")


def _money(value):
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def validate_coupon(code, subtotal):
    """Check a coupon code against a subtotal.

    Returns a dictionary with a `valid` flag, a human message, and the
    discount and final total as Decimals.
    """
    result = {
        "valid": False,
        "message": "",
        "code": (code or "").strip().upper(),
        "discount_percent": 0,
        "discount_amount": _money(0),
        "subtotal": _money(subtotal),
        "total": _money(subtotal),
    }

    if not result["code"]:
        result["message"] = "Enter a promo code."
        return result

    coupon = fetch_one(SELECT_COUPON_BY_CODE, [result["code"]])

    if coupon is None:
        result["message"] = "That promo code does not exist."
        return result

    if not coupon["is_active"]:
        result["message"] = "That promo code is no longer active."
        return result

    if not coupon["in_date_window"]:
        result["message"] = "That promo code has expired."
        return result

    if not coupon["has_uses_left"]:
        result["message"] = "That promo code has reached its usage limit."
        return result

    percent = int(coupon["discount_percent"])
    discount = _money(_money(subtotal) * Decimal(percent) / Decimal(100))

    result.update(
        {
            "valid": True,
            "message": f"{percent}% off applied.",
            "coupon_id": coupon["coupon_id"],
            "discount_percent": percent,
            "discount_amount": discount,
            "total": _money(_money(subtotal) - discount),
        }
    )
    return result


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
        outcome = validate_coupon(code, subtotal)
    except QueryError:
        return JsonResponse(
            {"valid": False, "message": "We could not check that code."}, status=503
        )

    return JsonResponse(
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
