"""Seller dashboard: live earnings, listing performance, orders and reviews."""

from django.contrib import messages
from django.db import connection
from django.shortcuts import render

from .decorators import role_required_raw

# ---------------------------------------------------------------------------
# Overall stats for the seller — one round-trip scalar subquery row.
# ---------------------------------------------------------------------------
SELECT_SELLER_STATS = """
    SELECT
        COALESCE(SUM(CASE WHEN o.order_status = 'Approved' THEN o.total_amount END), 0)
            AS total_earned,
        COALESCE(SUM(CASE WHEN o.order_status = 'Pending'  THEN o.total_amount END), 0)
            AS pending_amount,
        COUNT(DISTINCT o.order_id)                          AS total_orders,
        COUNT(DISTINCT CASE WHEN o.order_status = 'Approved' THEN o.order_id END)
            AS approved_orders,
        ROUND(AVG(r.rating), 1)                             AS avg_rating,
        COUNT(DISTINCT r.review_id)                         AS total_reviews,
        COUNT(DISTINCT l.listing_id)                        AS listing_count,
        SUM(l.available_slots)                              AS open_slots
    FROM Listings l
    LEFT JOIN Orders  o ON o.listing_id = l.listing_id
    LEFT JOIN Reviews r ON r.listing_id = l.listing_id
    WHERE l.seller_id = %s
"""

# ---------------------------------------------------------------------------
# Per-listing breakdown: slots, revenue, rating.
# ---------------------------------------------------------------------------
SELECT_SELLER_LISTINGS = """
    SELECT
        l.listing_id,
        l.plan_name,
        l.total_slots,
        l.available_slots,
        l.total_slots - l.available_slots          AS filled_slots,
        ROUND((l.total_slots - l.available_slots) * 100.0 / l.total_slots)
                                                   AS filled_percent,
        l.price_per_slot,
        l.billing_cycle,
        l.status,
        p.name                                     AS platform_name,
        p.brand_color,
        COALESCE(SUM(CASE WHEN o.order_status = 'Approved'
                          THEN o.total_amount END), 0)
                                                   AS listing_earned,
        ROUND(AVG(r.rating), 1)                    AS avg_rating,
        COUNT(DISTINCT r.review_id)                AS review_count
    FROM Listings l
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    LEFT  JOIN Orders    o ON o.listing_id  = l.listing_id
    LEFT  JOIN Reviews   r ON r.listing_id  = l.listing_id
    WHERE l.seller_id = %s
    GROUP BY
        l.listing_id, l.plan_name, l.total_slots, l.available_slots,
        l.price_per_slot, l.billing_cycle, l.status,
        p.name, p.brand_color
    ORDER BY listing_earned DESC, l.created_at DESC
"""

# ---------------------------------------------------------------------------
# Recent orders across all seller listings — newest 10.
# ---------------------------------------------------------------------------
SELECT_SELLER_RECENT_ORDERS = """
    SELECT
        o.order_id,
        o.slots_ordered,
        o.total_amount,
        o.order_status,
        o.payment_status,
        o.placed_at,
        l.listing_id,
        l.plan_name,
        p.name                                     AS platform_name,
        CONCAT(b.first_name, ' ', b.last_name)     AS buyer_name
    FROM Orders  o
    INNER JOIN Listings  l ON l.listing_id = o.listing_id
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    INNER JOIN Users     b ON b.user_id     = o.buyer_id
    WHERE l.seller_id = %s
    ORDER BY o.placed_at DESC, o.order_id DESC
    LIMIT 10
"""

# ---------------------------------------------------------------------------
# Recent reviews across all seller listings — newest 5.
# ---------------------------------------------------------------------------
SELECT_SELLER_RECENT_REVIEWS = """
    SELECT
        r.review_id,
        r.rating,
        r.comment,
        r.created_at,
        l.listing_id,
        l.plan_name,
        p.name                                     AS platform_name,
        CONCAT(u.first_name, ' ', u.last_name)     AS reviewer_name
    FROM Reviews  r
    INNER JOIN Listings  l ON l.listing_id = r.listing_id
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    INNER JOIN Users     u ON u.user_id     = r.reviewer_id
    WHERE l.seller_id = %s
    ORDER BY r.created_at DESC, r.review_id DESC
    LIMIT 5
"""

EMPTY_STATS = {
    "total_earned": 0,
    "pending_amount": 0,
    "total_orders": 0,
    "approved_orders": 0,
    "avg_rating": None,
    "total_reviews": 0,
    "listing_count": 0,
    "open_slots": 0,
}


def _fetch_all(cursor, sql, params):
    cursor.execute(sql, params)
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@role_required_raw("seller")
def seller_dashboard(request):
    """Live seller dashboard: earnings, listing performance, orders, reviews."""
    seller_id = request.session["user_id"]

    stats = dict(EMPTY_STATS)
    listings = []
    recent_orders = []
    recent_reviews = []

    try:
        with connection.cursor() as cursor:
            # Stats row
            cursor.execute(SELECT_SELLER_STATS, [seller_id])
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()
            if row:
                stats = dict(zip(columns, row))
                # Coerce None open_slots to 0 if seller has no listings yet
                if stats["open_slots"] is None:
                    stats["open_slots"] = 0

            listings      = _fetch_all(cursor, SELECT_SELLER_LISTINGS,       [seller_id])
            recent_orders = _fetch_all(cursor, SELECT_SELLER_RECENT_ORDERS,  [seller_id])
            recent_reviews = _fetch_all(cursor, SELECT_SELLER_RECENT_REVIEWS, [seller_id])

    except Exception:
        messages.error(request, "Some dashboard data could not be loaded. Please try again.")

    context = {
        "stats": stats,
        "listings": listings,
        "recent_orders": recent_orders,
        "recent_reviews": recent_reviews,
        "star_range": range(1, 6),
    }
    return render(request, "marketplace/seller_dashboard.html", context)
