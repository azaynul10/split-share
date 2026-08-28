"""Buyer reviews for completed, approved purchases."""

from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .decorators import role_required_raw


@role_required_raw("buyer")
@require_POST
def create_review(request, listing_id):
    """Create the buyer's single review after confirming an approved order."""
    try:
        rating = int(request.POST.get("rating", ""))
    except (TypeError, ValueError):
        rating = 0
    comment = request.POST.get("comment", "").strip()

    if rating not in (1, 2, 3, 4, 5):
        messages.error(request, "Choose a rating from 1 to 5 stars.")
        return redirect("listing_detail", listing_id=listing_id)
    if len(comment) > 500:
        messages.error(request, "Your review must be 500 characters or fewer.")
        return redirect("listing_detail", listing_id=listing_id)

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT l.seller_id, l.plan_name
                       FROM Listings l
                       WHERE l.listing_id = %s
                         AND EXISTS (
                            SELECT 1 FROM Orders o
                            WHERE o.buyer_id = %s AND o.listing_id = l.listing_id
                              AND o.order_status = 'Approved'
                         )
                         AND NOT EXISTS (
                            SELECT 1 FROM Reviews r
                            WHERE r.reviewer_id = %s AND r.listing_id = l.listing_id
                         )
                       FOR UPDATE""",
                    [listing_id, request.session["user_id"], request.session["user_id"]],
                )
                listing = cursor.fetchone()
                if listing is None:
                    raise ValueError("You can review this listing once after an approved purchase, and only once.")
                seller_id, plan_name = listing
                cursor.execute(
                    """INSERT INTO Reviews (reviewer_id, listing_id, rating, comment)
                       VALUES (%s, %s, %s, %s)""",
                    [request.session["user_id"], listing_id, rating, comment or None],
                )
                cursor.execute(
                    """INSERT INTO Notifications (user_id, title, message, type)
                       VALUES (%s, %s, %s, 'system')""",
                    [
                        seller_id,
                        f"New review for {plan_name}",
                        f"A buyer left a {rating}-star review on your listing.",
                    ],
                )
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "We could not save your review. Please try again.")
    else:
        messages.success(request, "Thanks — your review has been published.")
    return redirect("listing_detail", listing_id=listing_id)
