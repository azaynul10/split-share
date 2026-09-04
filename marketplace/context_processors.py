"""Make the signed-in user available to every template without passing it in.

The role comes from live_user() rather than straight from the session, so the
navigation shows what the database currently says instead of what the signed
cookie said at login time.
"""

from .decorators import live_user


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
