from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView, FormView
)

from ...mixins import TTLoginRequiredMixin, RoleRequiredMixin
from ...models import (
    Empresa, UnidadOrganizacional, Puesto, Turno,
    Empleado, EventoAsistencia, JornadaCalculada,
    TipoEventoAsistencia, FuenteMarcacion,
    AsignacionTurno, ReglaAsistencia, Geocerca,
    TipoAusencia, SolicitudAusencia, EstadoSolicitud,
    KPI, EvaluacionDesempeno, Usuario, Rol, UsuarioRol
)
from ...forms import (
    EmpresaForm, UnidadOrganizacionalForm, PuestoForm, TurnoForm,
    EmpleadoForm, EventoAsistenciaForm, TipoAusenciaForm, SolicitudAusenciaForm,
    KPIForm, UsuarioForm, UsuarioCreateWithRolForm, EmpleadoUsuarioAltaForm, RolForm, UsuarioRolForm
)

# shared helpers
from ...utils import *  # noqa: F401,F403

# -----------------------
# KPI (RRHH CRUD; others read-only)
# -----------------------
class KPIList(TTLoginRequiredMixin, ListView):
    model = KPI
    template_name = "talenttrack/kpi_list.html"
    context_object_name = "kpis"

    def get_queryset(self):
        qs = KPI.objects.select_related("empresa")
        qs = _apply_empresa_scope(qs, self.request)
        desde = _parse_date(self.request.GET.get("desde"))
        hasta = _parse_date(self.request.GET.get("hasta"))
        qs = _date_range_filter(qs, "creado_el", desde, hasta, is_datetime=True)
        return qs.order_by("codigo")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        is_sa = getattr(self.request.user, "is_superadmin", False) or self.request.user.has_role("SUPERADMIN")
        ctx["can_create"] = is_sa or self.request.user.has_role("ADMIN_RRHH")
        ctx["create_url"] = reverse_lazy("tt_empleado_usuario_alta") if is_sa else reverse_lazy("tt_empleado_create")
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "kpis")
        return ctx

class KPICreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = KPI
    form_class = KPIForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_kpi_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo KPI"
        return ctx

class KPIUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = KPI
    form_class = KPIForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_kpi_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar KPI"
        return ctx

class KPIDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = KPI
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_kpi_list")

