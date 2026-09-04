"""
Session-based access control.

Django's own @login_required is tied to django.contrib.auth, which this
project does not use. These decorators read the session keys that the login
view writes: user_id, user_name and role.

Sessions live in a signed cookie, so there is no server-side session record
and the cookie is only a snapshot of who the user was at login. Trusting it
for the whole of its lifetime means a deactivated account keeps working and a
demoted administrator keeps administrator access. Every protected request
therefore re-reads the user's row and reconciles it with the session.
"""

from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from .db_utils import QueryError, fetch_one

SELECT_SESSION_USER = """
    SELECT user_id, role, is_active
    FROM Users
    WHERE user_id = %s
"""

_CACHE_ATTR = "_live_user_cache"


def _redirect_to_login(request):
    query = urlencode({"next": request.get_full_path()})
    return redirect(f"{reverse('login')}?{query}")


def live_user(request):
    """Return the signed-in user's current row, or None if signed out.

    The result is cached on the request, so the decorator and the template
    context processor share one query per request rather than two.

    Fails closed: a missing row, a deactivated account, or an unreadable
    database all clear the session instead of being trusted.
    """
    if hasattr(request, _CACHE_ATTR):
        return getattr(request, _CACHE_ATTR)

    user = None
    user_id = request.session.get("user_id")

    if user_id:
        try:
            row = fetch_one(SELECT_SESSION_USER, [user_id])
        except QueryError:
            row = None

        if row is None or not row["is_active"]:
            request.session.flush()
        else:
            # The database is the authority on role, not the cookie.
            if row["role"] != request.session.get("role"):
                request.session["role"] = row["role"]
            user = row

    setattr(request, _CACHE_ATTR, user)
    return user


def login_required_raw(view_func):
    """Allow the request through only for a user who is still active."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if live_user(request) is None:
            messages.info(request, "Please sign in to continue.")
            return _redirect_to_login(request)
        return view_func(request, *args, **kwargs)

    return wrapper


def role_required_raw(*allowed_roles):
    """Allow the request through only for the listed roles.

    Usage:
        @role_required_raw("seller", "admin")
        def create_listing(request): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = live_user(request)
            if user is None:
                messages.info(request, "Please sign in to continue.")
                return _redirect_to_login(request)

            if user["role"] not in allowed_roles:
                messages.error(
                    request,
                    "Your account does not have permission to open that page.",
                )
                return redirect("browse")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def anonymous_only(view_func):
    """Send already signed-in users away from the login and register pages.

    A stale cookie must not block the login page, so this checks the live row
    too: a deactivated user can still reach the form and sign in again.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if live_user(request) is not None:
            return redirect("browse")
        return view_func(request, *args, **kwargs)

    return wrapper
