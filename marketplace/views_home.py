"""
The public landing page.

The visual design and static/css/landing.css are Zahid's work. This module
converts that static mock-up into a server-rendered page.

Nothing on this page is hard-coded marketing copy. The stats strip, the
category row and the featured cards all come from the three queries below, so
the landing page can never claim a number the database does not support.
"""

from django.shortcuts import render

from .db_utils import QueryError, fetch_all, fetch_one

# One row of headline figures. Each column is its own scalar subquery, which
# keeps the whole strip to a single round trip.
SELECT_LANDING_STATS = """
    SELECT
        (SELECT COUNT(*) FROM Users)                     AS member_count,
        (SELECT COUNT(*) FROM Platforms)                 AS platform_count,
        (SELECT COUNT(*) FROM Listings
          WHERE status = 'active')                       AS listing_count,
        (SELECT SUM(available_slots) FROM Listings
          WHERE status = 'active')                       AS open_slots,
        (SELECT ROUND(AVG(rating), 1) FROM Reviews)      AS avg_rating,
        (SELECT COUNT(*) FROM Reviews)                   AS review_count,
        (SELECT ROUND(SUM(total_amount)) FROM Orders
          WHERE order_status = 'Approved')               AS total_paid
"""

# Only categories that actually have something to show. A pill that leads to an
# empty result list is worse than no pill at all.
SELECT_LANDING_CATEGORIES = """
    SELECT
        c.category_id,
        c.name,
        COUNT(l.listing_id) AS listing_count
    FROM Categories c
    LEFT JOIN Platforms p ON p.category_id = c.category_id
    LEFT JOIN Listings  l ON l.platform_id = p.platform_id
                         AND l.status = 'active'
    GROUP BY c.category_id, c.name
    HAVING COUNT(l.listing_id) > 0
    ORDER BY listing_count DESC, c.name
"""

# The six best-reviewed listings that still have a free slot.
#
# full_plan_price is what one person would pay for the whole plan alone, which
# is what the struck-through price on each card compares against. filled_slots
# and filled_percent drive the progress bar.
SELECT_FEATURED_LISTINGS = """
    SELECT
        l.listing_id,
        l.plan_name,
        l.price_per_slot,
        l.total_slots,
        l.available_slots,
        l.billing_cycle,
        l.region,
        l.price_per_slot * l.total_slots  AS full_plan_price,
        l.total_slots - l.available_slots AS filled_slots,
        ROUND((l.total_slots - l.available_slots) * 100 / l.total_slots)
                                          AS filled_percent,
        p.name        AS platform_name,
        p.brand_color AS brand_color,
        c.name        AS category_name,
        CONCAT(u.first_name, ' ', u.last_name) AS seller_name,
        UPPER(CONCAT(LEFT(u.first_name, 1), LEFT(u.last_name, 1)))
                                          AS seller_initials,
        ROUND(AVG(r.rating), 1) AS avg_rating,
        ROUND(AVG(r.rating))    AS rating_stars,
        COUNT(r.review_id)      AS review_count
    FROM Listings l
    INNER JOIN Platforms  p ON p.platform_id = l.platform_id
    INNER JOIN Categories c ON c.category_id = p.category_id
    INNER JOIN Users      u ON u.user_id     = l.seller_id
    LEFT  JOIN Reviews    r ON r.listing_id  = l.listing_id
    WHERE l.status = 'active'
      AND l.available_slots > 0
    GROUP BY
        l.listing_id, l.plan_name, l.price_per_slot, l.total_slots,
        l.available_slots, l.billing_cycle, l.region,
        p.name, p.brand_color, c.name, u.first_name, u.last_name
    ORDER BY avg_rating DESC, review_count DESC, l.created_at DESC
    LIMIT 6
"""

EMPTY_STATS = {
    "member_count": 0,
    "platform_count": 0,
    "listing_count": 0,
    "open_slots": 0,
    "avg_rating": None,
    "review_count": 0,
    "total_paid": 0,
}

CYCLE_LABELS = {"monthly": "mo", "quarterly": "qtr", "yearly": "yr"}


def landing(request):
    """Public home page, readable without an account."""
    stats = dict(EMPTY_STATS)
    categories = []
    featured = []

    try:
        stats = fetch_one(SELECT_LANDING_STATS) or stats
        categories = fetch_all(SELECT_LANDING_CATEGORIES)
        featured = fetch_all(SELECT_FEATURED_LISTINGS)
    except QueryError:
        # This page is public and has no place to show a flash message, so a
        # database outage degrades to the static copy instead of an error page.
        stats = dict(EMPTY_STATS)

    for listing in featured:
        listing["cycle_label"] = CYCLE_LABELS.get(
            listing["billing_cycle"], listing["billing_cycle"]
        )

    context = {
        "stats": stats,
        "categories": categories,
        "featured": featured,
        "star_range": range(1, 6),
    }
    return render(request, "marketplace/home.html", context)
