"""
Registration, login and logout.

Passwords are hashed with Django's make_password() and verified with
check_password(). The plaintext password is never stored or logged.

Both successful entry points call session.cycle_key() before writing any
identity into the session. That discards whatever session the visitor arrived
with, so a session value fixed before login cannot be replayed afterwards to
inherit the new privileges.
"""

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .db_utils import QueryError, fetch_one, insert_returning_id
from .decorators import anonymous_only

SELECT_USER_BY_EMAIL = """
    SELECT user_id, first_name, last_name, email, password_hash, role, is_active
    FROM Users
    WHERE email = %s
"""

INSERT_USER = """
    INSERT INTO Users (first_name, last_name, email, password_hash, phone, role)
    VALUES (%s, %s, %s, %s, %s, %s)
"""

ALLOWED_ROLES = ("buyer", "seller")
MIN_PASSWORD_LENGTH = 8


def _safe_next(request, fallback="browse"):
    """Only follow a ?next= value that points back at this site."""
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return None if fallback is None else fallback


def _validate_registration(form):
    """Return a dict of field name to error message. Empty means valid."""
    errors = {}

    if not form["first_name"]:
        errors["first_name"] = "First name is required."
    elif len(form["first_name"]) > 50:
        errors["first_name"] = "First name cannot be longer than 50 characters."

    if not form["last_name"]:
        errors["last_name"] = "Last name is required."
    elif len(form["last_name"]) > 50:
        errors["last_name"] = "Last name cannot be longer than 50 characters."

    if not form["email"]:
        errors["email"] = "Email is required."
    else:
        try:
            validate_email(form["email"])
        except ValidationError:
            errors["email"] = "Enter a valid email address."

    if form["phone"] and len(form["phone"]) > 20:
        errors["phone"] = "Phone number cannot be longer than 20 characters."

    if not form["password"]:
        errors["password"] = "Password is required."
    elif len(form["password"]) < MIN_PASSWORD_LENGTH:
        errors["password"] = (
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    if form["password"] != form["confirm_password"]:
        errors["confirm_password"] = "The two passwords do not match."

    if form["role"] not in ALLOWED_ROLES:
        errors["role"] = "Choose whether you want to buy or sell slots."

    return errors


@anonymous_only
def register(request):
    form = {
        "first_name": "",
        "last_name": "",
        "email": "",
        "phone": "",
        "password": "",
        "confirm_password": "",
        "role": "buyer",
    }

    if request.method != "POST":
        return render(request, "auth/register.html", {"form": form, "errors": {}})

    form = {
        "first_name": request.POST.get("first_name", "").strip(),
        "last_name": request.POST.get("last_name", "").strip(),
        "email": request.POST.get("email", "").strip().lower(),
        "phone": request.POST.get("phone", "").strip(),
        "password": request.POST.get("password", ""),
        "confirm_password": request.POST.get("confirm_password", ""),
        "role": request.POST.get("role", "buyer"),
    }

    errors = _validate_registration(form)

    if not errors:
        try:
            if fetch_one(SELECT_USER_BY_EMAIL, [form["email"]]):
                errors["email"] = "An account with that email already exists."
        except QueryError:
            messages.error(
                request, "We could not reach the database. Please try again."
            )
            return render(request, "auth/register.html", {"form": form, "errors": errors})

    if errors:
        return render(request, "auth/register.html", {"form": form, "errors": errors})

    try:
        user_id = insert_returning_id(
            INSERT_USER,
            [
                form["first_name"],
                form["last_name"],
                form["email"],
                make_password(form["password"]),
                form["phone"] or None,
                form["role"],
            ],
        )
    except QueryError:
        messages.error(
            request, "Something went wrong creating your account. Please try again."
        )
        return render(request, "auth/register.html", {"form": form, "errors": errors})

    request.session.cycle_key()
    request.session["user_id"] = user_id
    request.session["user_name"] = f"{form['first_name']} {form['last_name']}"
    request.session["role"] = form["role"]

    messages.success(request, f"Welcome to Sub-Share, {form['first_name']}.")
    return redirect(_safe_next(request) or "browse")


@anonymous_only
def login_view(request):
    email = ""

    if request.method != "POST":
        return render(
            request,
            "auth/login.html",
            {"email": email, "errors": {}, "next": request.GET.get("next", "")},
        )

    email = request.POST.get("email", "").strip().lower()
    password = request.POST.get("password", "")
    errors = {}

    if not email:
        errors["email"] = "Email is required."
    if not password:
        errors["password"] = "Password is required."

    if errors:
        return render(
            request,
            "auth/login.html",
            {"email": email, "errors": errors, "next": request.POST.get("next", "")},
        )

    try:
        user = fetch_one(SELECT_USER_BY_EMAIL, [email])
    except QueryError:
        messages.error(request, "We could not reach the database. Please try again.")
        return render(
            request,
            "auth/login.html",
            {"email": email, "errors": {}, "next": request.POST.get("next", "")},
        )

    # The same message is shown whether the email or the password was wrong,
    # so the form cannot be used to discover which emails are registered.
    if user is None or not check_password(password, user["password_hash"]):
        errors["form"] = "Those details do not match an account."
        return render(
            request,
            "auth/login.html",
            {"email": email, "errors": errors, "next": request.POST.get("next", "")},
        )

    if not user["is_active"]:
        errors["form"] = "This account has been deactivated."
        return render(
            request,
            "auth/login.html",
            {"email": email, "errors": errors, "next": request.POST.get("next", "")},
        )

    request.session.cycle_key()
    request.session["user_id"] = user["user_id"]
    request.session["user_name"] = f"{user['first_name']} {user['last_name']}"
    request.session["role"] = user["role"]

    messages.success(request, f"Signed in as {user['first_name']}.")
    return redirect(_safe_next(request) or "browse")


def logout_view(request):
    request.session.flush()
    messages.success(request, "You have been signed out.")
    return redirect("browse")
