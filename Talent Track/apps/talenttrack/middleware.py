from .tt_auth import load_user_from_cookie


class TTAuthMiddleware:
    """Attach request.user from our signed cookie (no DB sessions, no Django auth tables)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = load_user_from_cookie(request)
        return self.get_response(request)
