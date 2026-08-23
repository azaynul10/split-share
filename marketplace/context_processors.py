"""Make the signed-in user available to every template without passing it in."""


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
