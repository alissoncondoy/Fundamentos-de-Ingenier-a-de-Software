from django.views import View
from django.views.generic import TemplateView

from ...mixins import TTLoginRequiredMixin
from ...models import Empresa, Empleado, EventoAsistencia, SolicitudAusencia, KPI
from ...services.dashboard_factory import DashboardFactory
from ...utils import *  # noqa

# -----------------------
# Dashboard
# -----------------------
class TT_DashboardView(TTLoginRequiredMixin, TemplateView):
    template_name = "talenttrack/dashboard.html"

    def get_template_names(self):
        days = int(self.request.GET.get("days", "14") or 14)
        return [DashboardFactory.build_for(self.request.user, days=days, empresa_id=(self.request.GET.get("empresa") or None)).template]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))

        days = int(self.request.GET.get("days", "14") or 14)
        dash = DashboardFactory.build_for(self.request.user, days=days, empresa_id=(self.request.GET.get("empresa") or None))
        ctx.update(dash.payload)

        # Counts based on scope
        ctx["empresa_count"] = Empresa.objects.count() if self.request.user.is_superadmin else 1
        ctx["empleado_count"] = _apply_empresa_scope(Empleado.objects.all(), self.request).count()
        ctx["asistencia_count"] = _apply_empresa_scope(EventoAsistencia.objects.all(), self.request).count()
        ctx["ausencia_count"] = _apply_empresa_scope(SolicitudAusencia.objects.all(), self.request).count()
        ctx["kpi_count"] = _apply_empresa_scope(KPI.objects.all(), self.request).count()
        return ctx


class TT_DashboardDataView(TTLoginRequiredMixin, View):
    """Endpoint JSON para alimentar charts/tablas del dashboard según el rol."""

    def get(self, request):
        from django.http import JsonResponse

        days = int(request.GET.get("days", "14") or 14)
        dash = DashboardFactory.build_for(request.user, days=days, empresa_id=(request.GET.get("empresa") or None))
        return JsonResponse(dash.payload)

