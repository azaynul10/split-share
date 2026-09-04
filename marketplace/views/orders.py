"""Checkout, order placement and order confirmation."""

from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from ..decorators import role_required_raw
from ..db_utils import QueryError, fetch_one

TWO_PLACES = Decimal("0.01")

SELECT_CHECKOUT_LISTING = """
    SELECT l.listing_id, l.seller_id, l.plan_name, l.price_per_slot,
           l.available_slots, l.status, l.billing_cycle,
           p.name AS platform_name
    FROM Listings l
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    WHERE l.listing_id = %s
"""

SELECT_ORDER_CONFIRMATION = """
    SELECT o.order_id, o.slots_ordered, o.unit_price, o.discount_amount,
           o.total_amount, o.order_status, o.payment_status, o.placed_at,
           l.plan_name, p.name AS platform_name
    FROM Orders o
    INNER JOIN Listings l ON l.listing_id = o.listing_id
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    WHERE o.order_id = %s AND o.buyer_id = %s
"""

SELECT_BUYER_ORDERS = """
    SELECT o.order_id, o.slots_ordered, o.total_amount, o.order_status,
           o.payment_status, o.payment_method, o.payment_ref, o.placed_at,
           l.plan_name, p.name AS platform_name
    FROM Orders o
    INNER JOIN Listings l ON l.listing_id = o.listing_id
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    WHERE o.buyer_id = %s
    ORDER BY o.placed_at DESC, o.order_id DESC
"""

SELECT_ADMIN_ORDERS = """
    SELECT o.order_id, o.slots_ordered, o.total_amount, o.order_status,
           o.payment_status, o.payment_method, o.payment_ref, o.placed_at,
           l.plan_name, l.available_slots, p.name AS platform_name,
           CONCAT(b.first_name, ' ', b.last_name) AS buyer_name,
           CONCAT(s.first_name, ' ', s.last_name) AS seller_name
    FROM Orders o
    INNER JOIN Listings l ON l.listing_id = o.listing_id
    INNER JOIN Platforms p ON p.platform_id = l.platform_id
    INNER JOIN Users b ON b.user_id = o.buyer_id
    INNER JOIN Users s ON s.user_id = l.seller_id
    ORDER BY (o.order_status = 'Pending' AND o.payment_status = 'pending_verification') DESC,
             o.placed_at DESC, o.order_id DESC
"""

PAYMENT_METHODS = ("bkash", "nagad", "rocket")


def _money(value):
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _slots(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _checkout_context(
    listing, slots, coupon_code="", coupon_error="", payment_method="", payment_ref=""
):
    slots = max(1, min(slots, listing["available_slots"])) if listing["available_slots"] else 0
    subtotal = _money(listing["price_per_slot"]) * slots
    return {
        "listing": listing,
        "slots": slots,
        "subtotal": subtotal,
        "coupon_code": coupon_code.strip().upper(),
        "coupon_error": coupon_error,
        "payment_method": payment_method,
        "payment_ref": payment_ref,
    }


@role_required_raw("buyer")
@require_http_methods(["GET", "POST"])
def checkout(request, listing_id):
    """Show checkout (GET) or atomically create a pending order (POST)."""
    try:
        listing = fetch_one(SELECT_CHECKOUT_LISTING, [listing_id])
    except QueryError:
        messages.error(request, "We could not load this listing for checkout.")
        return redirect("browse")

    if listing is None:
        messages.error(request, "That listing no longer exists.")
        return redirect("browse")
    if listing["seller_id"] == request.session["user_id"]:
        messages.error(request, "You cannot order a slot from your own listing.")
        return redirect("listing_detail", listing_id=listing_id)
    if listing["status"] != "active" or listing["available_slots"] < 1:
        messages.error(request, "This listing is no longer available.")
        return redirect("listing_detail", listing_id=listing_id)

    if request.method == "GET":
        requested_slots = _slots(request.GET.get("slots", 1))
        if requested_slots < 1 or requested_slots > listing["available_slots"]:
            requested_slots = 1
        return render(
            request,
            "marketplace/checkout.html",
            _checkout_context(listing, requested_slots, request.GET.get("coupon_code", "")),
        )

    requested_slots = _slots(request.POST.get("slots"))
    coupon_code = request.POST.get("coupon_code", "").strip().upper()
    payment_method = request.POST.get("payment_method", "").lower().strip()
    payment_ref = request.POST.get("payment_ref", "").strip()
    try:
        order_id = _create_order(
            request.session["user_id"], listing_id, requested_slots, coupon_code,
            payment_method, payment_ref,
        )
    except ValueError as exc:
        return render(
            request,
            "marketplace/checkout.html",
            _checkout_context(
                listing, requested_slots, coupon_code, str(exc), payment_method, payment_ref
            ),
        )
    except Exception:
        messages.error(request, "We could not place your order. Please try again.")
        return redirect("checkout", listing_id=listing_id)

    return redirect("order_confirmation", order_id=order_id)


def _create_order(buyer_id, listing_id, requested_slots, coupon_code, payment_method, payment_ref):
    """Create an order ready for administrator payment verification."""
    if requested_slots < 1:
        raise ValueError("Choose at least one slot.")
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Choose bKash, Nagad, or Rocket.")
    if not payment_ref or len(payment_ref) > 60:
        raise ValueError("Enter a transaction ID of up to 60 characters.")

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT seller_id, plan_name, price_per_slot, available_slots, status
                   FROM Listings WHERE listing_id = %s FOR UPDATE""",
                [listing_id],
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("That listing no longer exists.")
            seller_id, plan_name, unit_price, available_slots, status = row
            if seller_id == buyer_id:
                raise ValueError("You cannot order a slot from your own listing.")
            if status != "active" or available_slots < requested_slots:
                raise ValueError(f"Only {available_slots} slot(s) are currently available.")

            coupon_id = None
            discount = _money(0)
            if coupon_code:
                cursor.execute(
                    """SELECT coupon_id, discount_percent, is_active,
                              (CURDATE() BETWEEN valid_from AND valid_until),
                              (times_used < usage_limit)
                       FROM Coupons WHERE code = %s FOR UPDATE""",
                    [coupon_code],
                )
                coupon = cursor.fetchone()
                if coupon is None:
                    raise ValueError("That promo code does not exist.")
                coupon_id, percent, is_active, in_window, has_uses = coupon
                if not is_active:
                    raise ValueError("That promo code is no longer active.")
                if not in_window:
                    raise ValueError("That promo code has expired.")
                if not has_uses:
                    raise ValueError("That promo code has reached its usage limit.")
                discount = _money(_money(unit_price) * requested_slots * Decimal(percent) / 100)

            subtotal = _money(unit_price) * requested_slots
            total = _money(subtotal - discount)
            cursor.execute(
                """INSERT INTO Orders
                    (buyer_id, listing_id, coupon_id, slots_ordered, unit_price,
                     discount_amount, total_amount, order_status, payment_status,
                     payment_method, payment_ref)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending',
                           'pending_verification', %s, %s)""",
                [
                    buyer_id, listing_id, coupon_id, requested_slots, unit_price, discount,
                    total, payment_method, payment_ref,
                ],
            )
            order_id = cursor.lastrowid
            cursor.execute(
                """INSERT INTO OrderStatusHistory
                    (order_id, old_status, new_status, changed_by, reason)
                   VALUES (%s, NULL, 'Pending', %s, 'Order placed with payment reference')""",
                [order_id, buyer_id],
            )
            if coupon_id is not None:
                cursor.execute("UPDATE Coupons SET times_used = times_used + 1 WHERE coupon_id = %s", [coupon_id])
            cursor.execute(
                """INSERT INTO Notifications (user_id, title, message, type)
                   VALUES (%s, %s, %s, 'order'), (%s, %s, %s, 'order')""",
                [
                    buyer_id, f"Order #{order_id} received",
                    f"Your order for {plan_name} is awaiting payment verification.",
                    seller_id, f"New order #{order_id}",
                    f"A buyer submitted payment for {requested_slots} slot(s) on {plan_name}.",
                ],
            )
    return order_id


@role_required_raw("buyer")
def order_confirmation(request, order_id):
    try:
        order = fetch_one(SELECT_ORDER_CONFIRMATION, [order_id, request.session["user_id"]])
    except QueryError:
        messages.error(request, "We could not load that order.")
        return redirect("browse")
    if order is None:
        messages.error(request, "That order was not found.")
        return redirect("browse")
    return render(request, "marketplace/order_confirmation.html", {"order": order})


@role_required_raw("buyer")
def buyer_orders(request):
    """Show the signed-in buyer's complete order history."""
    try:
        orders = fetch_one("SELECT COUNT(*) AS total FROM Orders WHERE buyer_id = %s", [request.session["user_id"]])
        order_rows = []
        with connection.cursor() as cursor:
            cursor.execute(SELECT_BUYER_ORDERS, [request.session["user_id"]])
            columns = [column[0] for column in cursor.description]
            order_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception:
        messages.error(request, "We could not load your orders. Please try again.")
        order_rows = []
        orders = {"total": 0}
    return render(request, "marketplace/buyer_orders.html", {"orders": order_rows, "order_count": orders["total"]})


@role_required_raw("buyer")
@require_POST
def submit_payment(request, order_id):
    """Attach an off-platform payment reference to an eligible buyer order."""
    method = request.POST.get("payment_method", "").lower().strip()
    payment_ref = request.POST.get("payment_ref", "").strip()
    if method not in PAYMENT_METHODS:
        messages.error(request, "Choose bKash, Nagad, or Rocket.")
        return redirect("buyer_orders")
    if not payment_ref or len(payment_ref) > 60:
        messages.error(request, "Enter a transaction ID of up to 60 characters.")
        return redirect("buyer_orders")

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT o.order_status, o.payment_status, o.listing_id, l.seller_id, l.plan_name
                       FROM Orders o
                       INNER JOIN Listings l ON l.listing_id = o.listing_id
                       WHERE o.order_id = %s AND o.buyer_id = %s
                       FOR UPDATE""",
                    [order_id, request.session["user_id"]],
                )
                order = cursor.fetchone()
                if order is None:
                    raise ValueError("That order was not found.")
                order_status, payment_status, _listing_id, seller_id, plan_name = order
                if order_status != "Pending" or payment_status != "unpaid":
                    raise ValueError("A payment reference cannot be submitted for this order.")

                cursor.execute(
                    """UPDATE Orders
                       SET payment_method = %s, payment_ref = %s,
                           payment_status = 'pending_verification'
                       WHERE order_id = %s""",
                    [method, payment_ref, order_id],
                )
                # The order remains Pending, but this preserves the audit trail
                # of the buyer action in the existing append-only history table.
                cursor.execute(
                    """INSERT INTO OrderStatusHistory
                       (order_id, old_status, new_status, changed_by, reason)
                       VALUES (%s, 'Pending', 'Pending', %s, 'Payment reference submitted for verification')""",
                    [order_id, request.session["user_id"]],
                )
                cursor.execute(
                    """INSERT INTO Notifications (user_id, title, message, type)
                       VALUES (%s, %s, %s, 'order'), (%s, %s, %s, 'order')""",
                    [
                        request.session["user_id"], f"Payment submitted for order #{order_id}",
                        "Your transaction ID is awaiting verification.",
                        seller_id, f"Payment submitted for order #{order_id}",
                        f"A buyer submitted a payment reference for {plan_name}.",
                    ],
                )
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "We could not submit that payment reference. Please try again.")
    else:
        messages.success(request, "Payment reference submitted for verification.")
    return redirect("buyer_orders")


@role_required_raw("admin")
def admin_orders(request):
    """Show all orders, with payment-verification work first."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(SELECT_ADMIN_ORDERS)
            columns = [column[0] for column in cursor.description]
            orders = [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception:
        messages.error(request, "We could not load orders for review.")
        orders = []
    pending_count = sum(
        1
        for order in orders
        if order["order_status"] == "Pending"
        and order["payment_status"] == "pending_verification"
    )
    return render(request, "marketplace/admin_orders.html", {"orders": orders, "pending_count": pending_count})


@role_required_raw("admin")
@require_POST
def review_order(request, order_id):
    """Approve or reject an order after an administrator verifies its payment."""
    decision = request.POST.get("decision", "")
    reason = request.POST.get("reason", "").strip()[:255]
    if decision not in ("approve", "reject"):
        messages.error(request, "Choose whether to approve or reject the order.")
        return redirect("admin_orders")

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT o.buyer_id, o.listing_id, o.slots_ordered, o.order_status,
                              o.payment_status, l.seller_id, l.plan_name, l.available_slots
                       FROM Orders o
                       INNER JOIN Listings l ON l.listing_id = o.listing_id
                       WHERE o.order_id = %s FOR UPDATE""",
                    [order_id],
                )
                order = cursor.fetchone()
                if order is None:
                    raise ValueError("That order was not found.")
                buyer_id, listing_id, slots, status, payment_status, seller_id, plan_name, available = order
                if status != "Pending" or payment_status != "pending_verification":
                    raise ValueError("Only pending orders with a submitted payment reference can be reviewed.")

                if decision == "approve":
                    cursor.execute(
                        """UPDATE Listings SET available_slots = available_slots - %s
                           WHERE listing_id = %s AND available_slots >= %s""",
                        [slots, listing_id, slots],
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("There are no longer enough available slots to approve this order.")
                    new_status, new_payment, title = "Approved", "paid", f"Order #{order_id} approved"
                    buyer_message = f"Your {plan_name} slot is confirmed. The seller will contact you shortly."
                    seller_message = f"Order #{order_id} for {plan_name} was approved."
                    history_reason = reason or "Payment reference verified, slot released to buyer"
                else:
                    new_status, new_payment, title = "Rejected", "refunded", f"Order #{order_id} rejected"
                    buyer_message = f"Your order for {plan_name} was rejected. Please contact support about the refund."
                    seller_message = f"Order #{order_id} for {plan_name} was rejected."
                    history_reason = reason or "Payment reference could not be verified"

                cursor.execute(
                    """UPDATE Orders SET order_status = %s, payment_status = %s
                       WHERE order_id = %s""",
                    [new_status, new_payment, order_id],
                )
                cursor.execute(
                    """INSERT INTO OrderStatusHistory
                       (order_id, old_status, new_status, changed_by, reason)
                       VALUES (%s, 'Pending', %s, %s, %s)""",
                    [order_id, new_status, request.session["user_id"], history_reason],
                )
                cursor.execute(
                    """INSERT INTO Notifications (user_id, title, message, type)
                       VALUES (%s, %s, %s, 'order'), (%s, %s, %s, 'order')""",
                    [buyer_id, title, buyer_message, seller_id, title, seller_message],
                )
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "We could not review this order. Please try again.")
    else:
        messages.success(request, f"Order #{order_id} {new_status.lower()}.")
    return redirect("admin_orders")
