"""
Session-based access control.

Django's own @login_required is tied to django.contrib.auth, which this
project does not use. These decorators read the session keys that the login
view writes: user_id, user_name and role.
"""

from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def _redirect_to_login(request):
    query = urlencode({"next": request.get_full_path()})
    return redirect(f"{reverse('login')}?{query}")


def login_required_raw(view_func):
    """Allow the request through only when a user_id is present in the session."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("user_id"):
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
            if not request.session.get("user_id"):
                messages.info(request, "Please sign in to continue.")
                return _redirect_to_login(request)

            if request.session.get("role") not in allowed_roles:
                messages.error(
                    request,
                    "Your account does not have permission to open that page.",
                )
                return redirect("browse")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def anonymous_only(view_func):
    """Send already signed-in users away from the login and register pages."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get("user_id"):
            return redirect("browse")
        return view_func(request, *args, **kwargs)

    return wrapper
