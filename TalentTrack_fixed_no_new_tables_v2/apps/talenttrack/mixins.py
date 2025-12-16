from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


class TTLoginRequiredMixin:
    login_url_name = "tt_login"

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            messages.info(request, "Inicia sesión para continuar.")
            return redirect(reverse(self.login_url_name))
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin(TTLoginRequiredMixin):
    required_roles: tuple[str, ...] = tuple()

    def dispatch(self, request, *args, **kwargs):
        resp = super().dispatch(request, *args, **kwargs)
        # If parent returned a redirect response
        if hasattr(resp, "status_code") and resp.status_code in (301, 302):
            return resp
        if self.required_roles and not any(request.user.has_role(r) for r in self.required_roles):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("No tienes permisos para acceder a este módulo.")
        return resp
