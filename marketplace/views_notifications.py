"""Notifications: list view and mark-as-read action."""

from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .decorators import role_required_raw

SELECT_NOTIFICATIONS = """
    SELECT notification_id, title, message, type, is_read, created_at
    FROM Notifications
    WHERE user_id = %s
    ORDER BY created_at DESC, notification_id DESC
"""

MARK_ALL_READ = """
    UPDATE Notifications SET is_read = TRUE
    WHERE user_id = %s AND is_read = FALSE
"""

MARK_ONE_READ = """
    UPDATE Notifications SET is_read = TRUE
    WHERE notification_id = %s AND user_id = %s
"""


@role_required_raw("buyer", "seller", "admin")
def notifications(request):
    """Show all notifications for the signed-in user and mark them all as read."""
    user_id = request.session["user_id"]
    try:
        with connection.cursor() as cursor:
            # Fetch first so the page still shows which rows were unread
            cursor.execute(SELECT_NOTIFICATIONS, [user_id])
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            # Now mark all read — next page load the badge resets to 0
            cursor.execute(MARK_ALL_READ, [user_id])
    except Exception:
        messages.error(request, "Could not load notifications. Please try again.")
        rows = []

    return render(request, "marketplace/notifications.html", {"notifications": rows})


@role_required_raw("buyer", "seller", "admin")
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a single notification as read and redirect back to the notifications page."""
    user_id = request.session["user_id"]
    try:
        with connection.cursor() as cursor:
            cursor.execute(MARK_ONE_READ, [notification_id, user_id])
    except Exception:
        pass  # Silent failure — badge will just stay until next visit
    return redirect("notifications")
