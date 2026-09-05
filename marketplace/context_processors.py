"""Make the signed-in user available to every template without passing it in.

The role comes from live_user() rather than straight from the session, so the
navigation shows what the database currently says instead of what the signed
cookie said at login time.
"""

from .decorators import live_user

from django.db import connection


def current_user(request):
    user = live_user(request)
    return {
        "current_user": {
            "id": user["user_id"] if user else None,
            "name": request.session.get("user_name") if user else None,
            "role": user["role"] if user else None,
            "is_authenticated": user is not None,
        }
    }


def unread_notifications_count(request):
    """Inject the count of unread notifications for the bell-badge on every page."""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"unread_notifications_count": 0}
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM Notifications WHERE user_id = %s AND is_read = FALSE",
                [user_id],
            )
            count = cursor.fetchone()[0]
    except Exception:
        count = 0
    return {"unread_notifications_count": count}

