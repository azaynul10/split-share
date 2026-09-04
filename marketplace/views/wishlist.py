"""
Saved listings.

Wishlist has the composite primary key (user_id, listing_id), so the database
itself prevents the same listing being saved twice. INSERT IGNORE turns the
duplicate-key error into a no-op, which makes a double click harmless.
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..db_utils import QueryError, execute, fetch_all
from ..decorators import login_required_raw

SELECT_WISHLIST = """
    SELECT
        l.listing_id,
        l.plan_name,
        l.description,
        l.price_per_slot,
        l.total_slots,
        l.available_slots,
        l.billing_cycle,
        l.region,
        l.status,
        w.added_at,
        p.name        AS platform_name,
        p.brand_color AS brand_color,
        c.name        AS category_name,
        CONCAT(u.first_name, ' ', u.last_name) AS seller_name,
        ROUND(AVG(r.rating), 1) AS avg_rating,
        COUNT(r.review_id)      AS review_count
    FROM Wishlist w
    INNER JOIN Listings   l ON l.listing_id  = w.listing_id
    INNER JOIN Platforms  p ON p.platform_id = l.platform_id
    INNER JOIN Categories c ON c.category_id = p.category_id
    INNER JOIN Users      u ON u.user_id     = l.seller_id
    LEFT  JOIN Reviews    r ON r.listing_id  = l.listing_id
    WHERE w.user_id = %s
    GROUP BY
        l.listing_id, l.plan_name, l.description, l.price_per_slot,
        l.total_slots, l.available_slots, l.billing_cycle, l.region,
        l.status, w.added_at, p.name, p.brand_color, c.name,
        u.first_name, u.last_name
    ORDER BY w.added_at DESC
"""

INSERT_WISHLIST = """
    INSERT IGNORE INTO Wishlist (user_id, listing_id)
    VALUES (%s, %s)
"""

DELETE_WISHLIST = """
    DELETE FROM Wishlist
    WHERE user_id = %s AND listing_id = %s
"""


def _back_to(request, fallback="browse"):
    target = request.POST.get("next")
    if target and target.startswith("/"):
        return redirect(target)
    return redirect(fallback)


@login_required_raw
def wishlist(request):
    try:
        saved = fetch_all(SELECT_WISHLIST, [request.session["user_id"]])
        # Every row on this page is saved by definition, so the shared card
        # partial can render a filled heart without another query.
        for listing in saved:
            listing["in_wishlist"] = True
    except QueryError:
        messages.error(request, "We could not load your saved listings.")
        saved = []

    return render(request, "marketplace/wishlist.html", {"listings": saved})


@login_required_raw
@require_POST
def wishlist_add(request, listing_id):
    try:
        execute(INSERT_WISHLIST, [request.session["user_id"], listing_id])
        messages.success(request, "Saved to your wishlist.")
    except QueryError:
        messages.error(request, "We could not save that listing. Please try again.")

    return _back_to(request)


@login_required_raw
@require_POST
def wishlist_remove(request, listing_id):
    try:
        removed = execute(DELETE_WISHLIST, [request.session["user_id"], listing_id])
        if removed:
            messages.success(request, "Removed from your wishlist.")
        else:
            messages.info(request, "That listing was not on your wishlist.")
    except QueryError:
        messages.error(request, "We could not update your wishlist. Please try again.")

    return _back_to(request, fallback="wishlist")
