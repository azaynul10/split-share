"""Make the signed-in user available to every template without passing it in."""

from django.db import connection


def current_user(request):
    user_id = request.session.get("user_id")
    return {
        "current_user": {
            "id": user_id,
            "name": request.session.get("user_name"),
            "role": request.session.get("role"),
            "is_authenticated": bool(user_id),
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

