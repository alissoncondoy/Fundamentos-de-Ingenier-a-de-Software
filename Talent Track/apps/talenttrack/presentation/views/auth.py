from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from ...mixins import TTLoginRequiredMixin
from ...tt_auth import COOKIE_NAME, build_cookie_for_user, authenticate_login

# -----------------------
# Auth
# -----------------------
class TTLoginView(View):
    template_name = "account/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("tt_dashboard")
        return TemplateView.as_view(template_name=self.template_name)(request)

    def post(self, request):
        login = request.POST.get("login") or request.POST.get("email") or ""
        password = request.POST.get("password") or ""
        user, roles, err = authenticate_login(login, password)
        if err:
            messages.error(request, err)
            return redirect("tt_login")

        signed = build_cookie_for_user(user, roles)
        resp = redirect("tt_dashboard")
        resp.set_cookie(COOKIE_NAME, signed, max_age=60 * 60 * 24 * 14, httponly=True, samesite="Lax")
        return resp


class TTLogoutView(TTLoginRequiredMixin, View):
    def post(self, request):
        resp = redirect("tt_login")
        resp.delete_cookie(COOKIE_NAME)
        return resp

    def get(self, request):
        # allow GET for convenience
        resp = redirect("tt_login")
        resp.delete_cookie(COOKIE_NAME)
        return resp

