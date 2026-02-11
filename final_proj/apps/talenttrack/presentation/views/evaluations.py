from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from ...mixins import TTLoginRequiredMixin, RoleRequiredMixin
from ...models import EvaluacionDesempeno
from ...forms import EvaluacionForm
from ...utils import *  # noqa

# -----------------------
# Evaluaciones
# - EMPLEADO: solo lectura de lo propio
# - MANAGER / RRHH / SUPERADMIN: lectura y CRUD
# -----------------------

class EvaluacionList(TTLoginRequiredMixin, ListView):
    model = EvaluacionDesempeno
    template_name = "talenttrack/evaluacion_list.html"
    context_object_name = "evaluaciones"

    def get_queryset(self):
        qs = EvaluacionDesempeno.objects.select_related("empresa", "empleado", "evaluador")
        qs = _apply_empresa_scope(qs, self.request)

        # EMPLEADO: ve solo lo propio (si no es RRHH/Manager/Auditor/SA)
        if self.request.user.has_role("EMPLEADO") and not (
            self.request.user.has_role("ADMIN_RRHH")
            or self.request.user.has_role("MANAGER")
            or self.request.user.has_role("AUDITOR")
            or getattr(self.request.user, "is_superadmin", False)
            or self.request.user.has_role("SUPERADMIN")
        ):
            if self.request.user.empleado_id:
                qs = qs.filter(empleado_id=self.request.user.empleado_id)
            else:
                qs = qs.none()

        # Filtros básicos
        desde = _parse_date(self.request.GET.get("desde"))
        hasta = _parse_date(self.request.GET.get("hasta"))
        qs = _date_range_filter(qs, "fecha", desde, hasta, is_datetime=True)

        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(empleado__nombres__icontains=q)
                | Q(empleado__apellidos__icontains=q)
                | Q(periodo__icontains=q)
                | Q(tipo__icontains=q)
            )

        return qs.order_by("-fecha", "empleado__apellidos")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        can_create = (
            self.request.user.has_role("ADMIN_RRHH")
            or self.request.user.has_role("MANAGER")
            or self.request.user.has_role("SUPERADMIN")
            or getattr(self.request.user, "is_superadmin", False)
        )
        ctx["can_create"] = can_create
        ctx["create_url"] = reverse_lazy("tt_evaluacion_create")
        ctx["readonly"] = not can_create
        ctx["can_export"] = _can_export(self.request.user, "evaluaciones")
        return ctx


class EvaluacionCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH", "MANAGER", "SUPERADMIN")
    model = EvaluacionDesempeno
    form_class = EvaluacionForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_evaluacion_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva evaluación"
        return ctx


class EvaluacionUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH", "MANAGER", "SUPERADMIN")
    model = EvaluacionDesempeno
    form_class = EvaluacionForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_evaluacion_list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar evaluación"
        return ctx


class EvaluacionDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH", "MANAGER", "SUPERADMIN")
    model = EvaluacionDesempeno
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_evaluacion_list")
