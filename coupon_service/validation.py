"""
Coupon validation rules.

A code has to clear three separate gates before it discounts anything:
switched on, inside its date window, and not used up. The seed data contains
one code that fails each gate, so all four outcomes are demonstrable.

This module is storage-agnostic: `validate_coupon` takes a `fetch_one`
callable so the same rules run against any DB-API connection.
"""

from decimal import ROUND_HALF_UP, Decimal

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

TWO_PLACES = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def validate_coupon(code, subtotal, fetch_one):
    """Check a coupon code against a subtotal.

    Returns a dictionary with a `valid` flag, a human message, and the
    discount and final total as Decimals.
    """
    result = {
        "valid": False,
        "message": "",
        "code": (code or "").strip().upper(),
        "discount_percent": 0,
        "discount_amount": money(0),
        "subtotal": money(subtotal),
        "total": money(subtotal),
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
    discount = money(money(subtotal) * Decimal(percent) / Decimal(100))

    result.update(
        {
            "valid": True,
            "message": f"{percent}% off applied.",
            "coupon_id": coupon["coupon_id"],
            "discount_percent": percent,
            "discount_amount": discount,
            "total": money(money(subtotal) - discount),
        }
    )
    return result
