from django.db.models import Q
from django.views.generic import ListView

from ...mixins import TTLoginRequiredMixin
from ...models import EvaluacionDesempeno
from ...utils import *  # noqa

# -----------------------
# Evaluaciones (Lectura por rol)
# -----------------------
class EvaluacionList(TTLoginRequiredMixin, ListView):
    model = EvaluacionDesempeno
    template_name = "talenttrack/evaluacion_list.html"
    context_object_name = "evaluaciones"

    def get_queryset(self):
        qs = EvaluacionDesempeno.objects.select_related("empresa", "empleado", "evaluador")
        qs = _apply_empresa_scope(qs, self.request)

        # Filtro por empleado (si es EMPLEADO, solo ve lo propio)
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
        # Por ahora lectura (no rompemos requerimientos ni migraciones)
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH") or self.request.user.has_role("SUPERADMIN")
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "evaluaciones")
        return ctx

