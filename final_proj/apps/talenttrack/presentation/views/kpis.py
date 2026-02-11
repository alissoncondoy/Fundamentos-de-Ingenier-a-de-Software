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
        ctx["create_url"] = reverse_lazy("tt_kpi_create") if is_sa else reverse_lazy("tt_empleado_create")
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "kpis")

        # Vista "más dinámica" para empleados: mostrar KPIs calculados automáticamente
        is_employee_only = bool(getattr(self.request.user, "empleado_id", None)) and not ctx["can_create"]
        ctx["is_employee_only"] = is_employee_only

        if is_employee_only:
            empleado_id = self.request.user.empleado_id
            empresa_id = getattr(self.request.user, "empresa_id", None)

            desde = _parse_date(self.request.GET.get("desde"))
            hasta = _parse_date(self.request.GET.get("hasta"))
            hoy = date.today()
            if not hasta:
                hasta = hoy
            if not desde:
                # por defecto, mes actual
                desde = hasta.replace(day=1)

            jc_qs = JornadaCalculada.objects.filter(
                empresa_id=empresa_id,
                empleado_id=empleado_id,
                fecha__gte=desde,
                fecha__lte=hasta,
            )

            days_worked = jc_qs.exclude(minutos_trabajados=0).count()
            total_minutes = sum(j.minutos_trabajados or 0 for j in jc_qs)
            extra_minutes = sum(getattr(j, "minutos_extra", 0) or 0 for j in jc_qs)
            tard_minutes = sum(getattr(j, "minutos_tardanza", 0) or 0 for j in jc_qs)
            punctual_days = sum(
                1 for j in jc_qs
                if (j.minutos_trabajados or 0) > 0 and (getattr(j, "minutos_tardanza", 0) or 0) == 0
            )
            punctuality = round((punctual_days / days_worked) * 100) if days_worked else 100

            def _sev_color(pct: int) -> str:
                if pct >= 90:
                    return "success"
                if pct >= 75:
                    return "warning"
                return "danger"

            cards = [
                {
                    "title": "Puntualidad",
                    "value": f"{punctuality}%",
                    "sub": f"{punctual_days}/{days_worked} días sin tardanza" if days_worked else "Sin jornadas registradas",
                    "progress": punctuality,
                    "color": _sev_color(punctuality),
                    "icon": "ni ni-check-bold",
                },
                {
                    "title": "Días trabajados",
                    "value": str(days_worked),
                    "sub": f"Del {desde.strftime('%d/%m')} al {hasta.strftime('%d/%m')}",
                    "progress": None,
                    "color": "info",
                    "icon": "ni ni-calendar-grid-58",
                },
                {
                    "title": "Horas trabajadas",
                    "value": f"{round(total_minutes / 60, 1) if total_minutes else 0}h",
                    "sub": "Horas dentro de jornada",
                    "progress": None,
                    "color": "success",
                    "icon": "ni ni-time-alarm",
                },
                {
                    "title": "Horas extra",
                    "value": f"{round(extra_minutes / 60, 1) if extra_minutes else 0}h",
                    "sub": "Acumuladas en el periodo",
                    "progress": None,
                    "color": "warning",
                    "icon": "ni ni-fat-add",
                },
                {
                    "title": "Tardanzas",
                    "value": f"{tard_minutes} min",
                    "sub": "Total de minutos tarde",
                    "progress": None,
                    "color": "danger" if tard_minutes else "success",
                    "icon": "ni ni-bell-55",
                },
            ]

            ctx["kpi_cards"] = cards
            ctx["desde"] = desde.strftime("%Y-%m-%d")
            ctx["hasta"] = hasta.strftime("%Y-%m-%d")

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

