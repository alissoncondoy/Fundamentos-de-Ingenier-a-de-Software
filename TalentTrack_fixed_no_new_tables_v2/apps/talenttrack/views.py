import csv
from datetime import datetime, date, time
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView

from .mixins import TTLoginRequiredMixin, RoleRequiredMixin
from .tt_auth import COOKIE_NAME, build_cookie_for_user, authenticate_login
from .models import (
    Empresa, UnidadOrganizacional, Puesto, Turno,
    Empleado, EventoAsistencia, TipoAusencia, SolicitudAusencia, EstadoSolicitud,
    KPI, Usuario, Rol, UsuarioRol
)
from .forms import (
    EmpresaForm, UnidadOrganizacionalForm, PuestoForm, TurnoForm,
    EmpleadoForm, EventoAsistenciaForm, TipoAusenciaForm, SolicitudAusenciaForm,
    KPIForm, UsuarioForm, RolForm, UsuarioRolForm
)


# -----------------------
# Helpers (scope + filters)
# -----------------------
def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _empresa_scope_id(request):
    """
    Returns:
      - For SUPERADMIN: optional ?empresa=<uuid> else None (global)
      - Others: user's empresa_id (string) or None
    """
    if request.user.is_superadmin:
        return request.GET.get("empresa") or None
    return request.user.empresa_id


def _apply_empresa_scope(qs, request, field="empresa_id"):
    emp = _empresa_scope_id(request)
    if emp:
        return qs.filter(**{field: emp})
    return qs


def _date_range_filter(qs, field_name: str, desde: date | None, hasta: date | None, is_datetime=True):
    """
    Applies inclusive date range. For datetime field, converts to start/end of day.
    """
    if desde:
        if is_datetime:
            qs = qs.filter(**{f"{field_name}__gte": timezone.make_aware(datetime.combine(desde, time.min))})
        else:
            qs = qs.filter(**{f"{field_name}__gte": desde})
    if hasta:
        if is_datetime:
            qs = qs.filter(**{f"{field_name}__lte": timezone.make_aware(datetime.combine(hasta, time.max))})
        else:
            qs = qs.filter(**{f"{field_name}__lte": hasta})
    return qs


# Cache simple para IDs de catálogos (evita hits repetidos)
_ESTADO_SOLICITUD_CACHE: dict[str, str] = {}


def _estado_solicitud_id(codigo: str):
    """Devuelve el UUID (string) del catálogo config.estado_solicitud por código."""
    if not codigo:
        return None
    if codigo in _ESTADO_SOLICITUD_CACHE:
        return _ESTADO_SOLICITUD_CACHE[codigo]
    try:
        estado_id = str(EstadoSolicitud.objects.only("id").get(codigo=codigo).id)
    except EstadoSolicitud.DoesNotExist:
        return None
    _ESTADO_SOLICITUD_CACHE[codigo] = estado_id
    return estado_id


def _companies_for_filter():
    return Empresa.objects.all().order_by("razon_social")


def _ctx_common_filters(request):
    return {
        "is_superadmin": request.user.is_superadmin,
        "empresa_filter": request.GET.get("empresa") if request.user.is_superadmin else None,
        "empresa_options": _companies_for_filter() if request.user.is_superadmin else [],
        "desde": request.GET.get("desde", ""),
        "hasta": request.GET.get("hasta", ""),
    }


def _forbid():
    return HttpResponseForbidden("No tienes permisos para esta acción.")


def _can_export(user, module: str) -> bool:
    # Auditor can export for their company, Superadmin global, RRHH for their company, Manager maybe for team
    if user.has_role("SUPERADMIN"):
        return True
    if user.has_role("AUDITOR"):
        return True
    if user.has_role("ADMIN_RRHH"):
        return True
    if user.has_role("MANAGER") and module in ("asistencia", "ausencias", "empleados"):
        return True
    return False


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


# -----------------------
# Dashboard
# -----------------------
class TT_DashboardView(TTLoginRequiredMixin, TemplateView):
    template_name = "talenttrack/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))

        # Counts based on scope
        ctx["empresa_count"] = Empresa.objects.count() if self.request.user.is_superadmin else 1
        ctx["empleado_count"] = _apply_empresa_scope(Empleado.objects.all(), self.request).count()
        ctx["asistencia_count"] = _apply_empresa_scope(EventoAsistencia.objects.all(), self.request).count()
        ctx["ausencia_count"] = _apply_empresa_scope(SolicitudAusencia.objects.all(), self.request).count()
        ctx["kpi_count"] = _apply_empresa_scope(KPI.objects.all(), self.request).count()
        return ctx


# -----------------------
# Empresas (SUPERADMIN only)
# -----------------------
class EmpresaList(RoleRequiredMixin, ListView):
    required_roles = ("SUPERADMIN",)
    model = Empresa
    template_name = "talenttrack/empresa_list.html"
    context_object_name = "empresas"

class EmpresaCreate(RoleRequiredMixin, CreateView):
    required_roles = ("SUPERADMIN",)
    model = Empresa
    form_class = EmpresaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_empresa_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva Empresa"
        return ctx

class EmpresaUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("SUPERADMIN",)
    model = Empresa
    form_class = EmpresaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_empresa_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Empresa"
        return ctx

class EmpresaDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("SUPERADMIN",)
    model = Empresa
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_empresa_list")


# -----------------------
# Administración: Unidades, Puestos, Turnos (RRHH CRUD; others read-only list)
# -----------------------
class UnidadList(TTLoginRequiredMixin, ListView):
    model = UnidadOrganizacional
    template_name = "talenttrack/unidad_list.html"
    context_object_name = "unidades"

    def get_queryset(self):
        qs = UnidadOrganizacional.objects.select_related("empresa", "padre")
        return _apply_empresa_scope(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH")
        ctx["readonly"] = not ctx["can_create"]
        return ctx

class UnidadCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH",)
    model = UnidadOrganizacional
    form_class = UnidadOrganizacionalForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_unidad_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva Unidad Organizacional"
        return ctx

class UnidadUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH",)
    model = UnidadOrganizacional
    form_class = UnidadOrganizacionalForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_unidad_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Unidad Organizacional"
        return ctx

class UnidadDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH",)
    model = UnidadOrganizacional
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_unidad_list")


class PuestoList(TTLoginRequiredMixin, ListView):
    model = Puesto
    template_name = "talenttrack/puesto_list.html"
    context_object_name = "puestos"

    def get_queryset(self):
        qs = Puesto.objects.select_related("empresa", "unidad")
        return _apply_empresa_scope(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH")
        ctx["readonly"] = not ctx["can_create"]
        return ctx

class PuestoCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH",)
    model = Puesto
    form_class = PuestoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_puesto_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Puesto"
        return ctx

class PuestoUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH",)
    model = Puesto
    form_class = PuestoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_puesto_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Puesto"
        return ctx

class PuestoDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH",)
    model = Puesto
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_puesto_list")


class TurnoList(TTLoginRequiredMixin, ListView):
    model = Turno
    template_name = "talenttrack/turno_list.html"
    context_object_name = "turnos"

    def get_queryset(self):
        qs = Turno.objects.select_related("empresa")
        return _apply_empresa_scope(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH")
        ctx["readonly"] = not ctx["can_create"]
        return ctx

class TurnoCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH",)
    model = Turno
    form_class = TurnoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_turno_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Turno"
        return ctx

class TurnoUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH",)
    model = Turno
    form_class = TurnoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_turno_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Turno"
        return ctx

class TurnoDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH",)
    model = Turno
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_turno_list")


# -----------------------
# Empleados (RRHH CRUD; others read-only; Manager sees team; Empleado sees self)
# -----------------------
class EmpleadoList(TTLoginRequiredMixin, ListView):
    model = Empleado
    template_name = "talenttrack/empleado_list.html"
    context_object_name = "empleados"

    def get_queryset(self):
        qs = Empleado.objects.select_related("empresa", "unidad", "puesto", "manager")
        # Company scope
        qs = _apply_empresa_scope(qs, self.request)
        # Role scope
        if self.request.user.has_role("MANAGER") and self.request.user.empleado_id:
            # team = direct reports
            qs = qs.filter(manager_id=self.request.user.empleado_id)
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            qs = qs.filter(id=self.request.user.empleado_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH")
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "empleados")
        return ctx

class EmpleadoDetail(TTLoginRequiredMixin, DetailView):
    model = Empleado
    template_name = "talenttrack/empleado_detail.html"
    context_object_name = "empleado"

    def get_queryset(self):
        qs = Empleado.objects.select_related("empresa", "unidad", "puesto", "manager")
        qs = _apply_empresa_scope(qs, self.request)
        # employee can only view self
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            qs = qs.filter(id=self.request.user.empleado_id)
        # manager can view team + self
        if self.request.user.has_role("MANAGER") and self.request.user.empleado_id:
            qs = qs.filter(id__in=Empleado.objects.filter(manager_id=self.request.user.empleado_id).values("id")) | qs.filter(id=self.request.user.empleado_id)
        return qs

class EmpleadoCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH",)
    model = Empleado
    form_class = EmpleadoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_empleado_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Empleado"
        return ctx

class EmpleadoUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH",)
    model = Empleado
    form_class = EmpleadoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_empleado_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Empleado"
        return ctx

class EmpleadoDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH",)
    model = Empleado
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_empleado_list")


# -----------------------
# Asistencia (Empleado puede registrar lo suyo; RRHH puede registrar de su empresa)
# -----------------------
class AsistenciaList(TTLoginRequiredMixin, ListView):
    model = EventoAsistencia
    template_name = "talenttrack/asistencia_list.html"
    context_object_name = "eventos"

    def get_queryset(self):
        qs = EventoAsistencia.objects.select_related("empresa", "empleado")
        qs = _apply_empresa_scope(qs, self.request)

        # date filters
        desde = _parse_date(self.request.GET.get("desde"))
        hasta = _parse_date(self.request.GET.get("hasta"))
        qs = _date_range_filter(qs, "registrado_el", desde, hasta, is_datetime=True)

        # employee only self
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            qs = qs.filter(empleado_id=self.request.user.empleado_id)
        # manager only team
        if self.request.user.has_role("MANAGER") and self.request.user.empleado_id:
            team_ids = Empleado.objects.filter(manager_id=self.request.user.empleado_id).values_list("id", flat=True)
            qs = qs.filter(empleado_id__in=list(team_ids))
        return qs.order_by("-registrado_el")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH") or self.request.user.has_role("EMPLEADO")
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "asistencia")
        return ctx

class AsistenciaCreate(TTLoginRequiredMixin, CreateView):
    model = EventoAsistencia
    form_class = EventoAsistenciaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_asistencia_list")

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.has_role("ADMIN_RRHH") or request.user.has_role("EMPLEADO")):
            return _forbid()
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Lock down employee scope for EMPLEADO role
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            form.fields["empresa"].queryset = Empresa.objects.filter(id=self.request.user.empresa_id)
            form.fields["empleado"].queryset = Empleado.objects.filter(id=self.request.user.empleado_id)
            form.fields["empresa"].initial = self.request.user.empresa_id
            form.fields["empleado"].initial = self.request.user.empleado_id
        return form

    def form_valid(self, form):
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            form.instance.empresa_id = self.request.user.empresa_id
            form.instance.empleado_id = self.request.user.empleado_id
        form.instance.registrado_el = timezone.now()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Evento de Asistencia"
        return ctx


# -----------------------
# Ausencias (Empleado solicita; RRHH gestiona en su empresa; Auditor exporta)
# -----------------------
class AusenciaList(TTLoginRequiredMixin, ListView):
    model = SolicitudAusencia
    template_name = "talenttrack/ausencia_list.html"
    context_object_name = "solicitudes"

    def get_queryset(self):
        qs = SolicitudAusencia.objects.select_related("empresa", "empleado", "tipo_ausencia", "estado")
        qs = _apply_empresa_scope(qs, self.request)

        desde = _parse_date(self.request.GET.get("desde"))
        hasta = _parse_date(self.request.GET.get("hasta"))
        # date range over fecha_inicio/fecha_fin (overlap)
        if desde:
            qs = qs.filter(fecha_fin__gte=desde)
        if hasta:
            qs = qs.filter(fecha_inicio__lte=hasta)

        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            qs = qs.filter(empleado_id=self.request.user.empleado_id)
        if self.request.user.has_role("MANAGER") and self.request.user.empleado_id:
            team_ids = Empleado.objects.filter(manager_id=self.request.user.empleado_id).values_list("id", flat=True)
            qs = qs.filter(empleado_id__in=list(team_ids))
        return qs.order_by("-creada_el")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH") or self.request.user.has_role("EMPLEADO")
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "ausencias")
        return ctx

class AusenciaCreate(TTLoginRequiredMixin, CreateView):
    model = SolicitudAusencia
    form_class = SolicitudAusenciaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_ausencia_list")

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.has_role("ADMIN_RRHH") or request.user.has_role("EMPLEADO")):
            return _forbid()
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            form.fields["empresa"].queryset = Empresa.objects.filter(id=self.request.user.empresa_id)
            form.fields["empleado"].queryset = Empleado.objects.filter(id=self.request.user.empleado_id)
            form.fields["empresa"].initial = self.request.user.empresa_id
            form.fields["empleado"].initial = self.request.user.empleado_id
        return form

    def form_valid(self, form):
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            form.instance.empresa_id = self.request.user.empresa_id
            form.instance.empleado_id = self.request.user.empleado_id
        # Estado inicial: pendiente
        if not getattr(form.instance, "estado_id", None):
            pend_id = _estado_solicitud_id("pendiente")
            if pend_id:
                form.instance.estado_id = pend_id
        form.instance.creada_el = timezone.now()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva Solicitud de Ausencia"
        return ctx

class AusenciaCancel(TTLoginRequiredMixin, View):
    """Cancela una solicitud cambiando su estado a 'cancelado' (NO elimina)."""

    def post(self, request, pk):
        try:
            obj = SolicitudAusencia.objects.select_related("estado").get(pk=pk)
        except SolicitudAusencia.DoesNotExist:
            messages.error(request, "La solicitud no existe.")
            return redirect("tt_ausencia_list")

        # Permisos: RRHH (su empresa) o EMPLEADO (propia)
        if request.user.has_role("ADMIN_RRHH"):
            if (not request.user.is_superadmin) and str(obj.empresa_id) != str(request.user.empresa_id):
                return _forbid()
        elif request.user.has_role("EMPLEADO") and request.user.empleado_id:
            if str(obj.empleado_id) != str(request.user.empleado_id):
                return _forbid()
        else:
            return _forbid()

        # Regla de negocio: solo se puede cancelar si está pendiente
        if obj.estado and obj.estado.codigo != "pendiente":
            messages.error(request, "Solo puedes cancelar solicitudes en estado Pendiente.")
            return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")

        cancel_id = _estado_solicitud_id("cancelado")
        if not cancel_id:
            messages.error(request, "No existe el estado 'cancelado' en config.estado_solicitud.")
            return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")

        obj.estado_id = cancel_id
        obj.save(update_fields=["estado"])
        messages.success(request, "Solicitud cancelada.")
        return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")


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
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH")
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "kpis")
        return ctx

class KPICreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH",)
    model = KPI
    form_class = KPIForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_kpi_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo KPI"
        return ctx

class KPIUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH",)
    model = KPI
    form_class = KPIForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_kpi_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar KPI"
        return ctx

class KPIDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH",)
    model = KPI
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_kpi_list")


# -----------------------
# Seguridad (SUPERADMIN only)
# -----------------------
class UsuarioList(RoleRequiredMixin, ListView):
    required_roles = ("SUPERADMIN",)
    model = Usuario
    template_name = "talenttrack/usuario_list.html"
    context_object_name = "usuarios"

class UsuarioCreate(RoleRequiredMixin, CreateView):
    required_roles = ("SUPERADMIN",)
    model = Usuario
    form_class = UsuarioForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_usuario_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Usuario"
        return ctx

class UsuarioUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("SUPERADMIN",)
    model = Usuario
    form_class = UsuarioForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_usuario_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Usuario"
        return ctx

class UsuarioDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("SUPERADMIN",)
    model = Usuario
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_usuario_list")


class RolList(RoleRequiredMixin, ListView):
    required_roles = ("SUPERADMIN",)
    model = Rol
    template_name = "talenttrack/rol_list.html"
    context_object_name = "roles"

class RolCreate(RoleRequiredMixin, CreateView):
    required_roles = ("SUPERADMIN",)
    model = Rol
    form_class = RolForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_rol_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Rol"
        return ctx

class RolUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("SUPERADMIN",)
    model = Rol
    form_class = RolForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_rol_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Rol"
        return ctx

class RolDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("SUPERADMIN",)
    model = Rol
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_rol_list")


class UsuarioRolList(RoleRequiredMixin, ListView):
    required_roles = ("SUPERADMIN",)
    model = UsuarioRol
    template_name = "talenttrack/usuariorol_list.html"
    context_object_name = "asignaciones"

    def get_queryset(self):
        return UsuarioRol.objects.select_related("usuario", "rol").all()

class UsuarioRolCreate(RoleRequiredMixin, CreateView):
    required_roles = ("SUPERADMIN",)
    model = UsuarioRol
    form_class = UsuarioRolForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_usuariorol_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Asignar Rol a Usuario"
        return ctx

class UsuarioRolDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("SUPERADMIN",)
    model = UsuarioRol
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_usuariorol_list")


# -----------------------
# Export CSV (with date filters)
# -----------------------
class ExportEmpleadosCSV(TTLoginRequiredMixin, View):
    def get(self, request):
        if not _can_export(request.user, "empleados"):
            return _forbid()
        qs = Empleado.objects.select_related("empresa", "unidad", "puesto", "manager")
        qs = _apply_empresa_scope(qs, request)
        # optional created_at date range
        desde = _parse_date(request.GET.get("desde"))
        hasta = _parse_date(request.GET.get("hasta"))
        qs = _date_range_filter(qs, "created_at", desde, hasta, is_datetime=True)

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="empleados.csv"'
        w = csv.writer(resp)
        w.writerow(["empresa", "apellidos", "nombres", "documento", "email", "telefono", "unidad", "puesto", "manager", "fecha_ingreso", "created_at"])
        for e in qs.order_by("apellidos", "nombres"):
            w.writerow([
                str(e.empresa),
                e.apellidos,
                e.nombres,
                e.documento or "",
                e.email or "",
                e.telefono or "",
                str(e.unidad) if e.unidad_id else "",
                str(e.puesto) if e.puesto_id else "",
                str(e.manager) if e.manager_id else "",
                e.fecha_ingreso.isoformat() if e.fecha_ingreso else "",
                e.created_at.isoformat() if e.created_at else "",
            ])
        return resp


class ExportAsistenciaCSV(TTLoginRequiredMixin, View):
    def get(self, request):
        if not _can_export(request.user, "asistencia"):
            return _forbid()
        qs = EventoAsistencia.objects.select_related("empresa", "empleado")
        qs = _apply_empresa_scope(qs, request)

        desde = _parse_date(request.GET.get("desde"))
        hasta = _parse_date(request.GET.get("hasta"))
        qs = _date_range_filter(qs, "registrado_el", desde, hasta, is_datetime=True)

        # employee scope
        if request.user.has_role("EMPLEADO") and request.user.empleado_id:
            qs = qs.filter(empleado_id=request.user.empleado_id)
        if request.user.has_role("MANAGER") and request.user.empleado_id:
            team_ids = Empleado.objects.filter(manager_id=request.user.empleado_id).values_list("id", flat=True)
            qs = qs.filter(empleado_id__in=list(team_ids))

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="asistencia.csv"'
        w = csv.writer(resp)
        w.writerow(["empresa", "empleado", "registrado_el", "tipo", "fuente", "gps_lat", "gps_lng", "dentro_geocerca", "foto_url", "ip", "observacion"])
        for ev in qs.order_by("-registrado_el"):
            w.writerow([
                str(ev.empresa),
                str(ev.empleado),
                ev.registrado_el.isoformat() if ev.registrado_el else "",
                str(ev.tipo) if ev.tipo else "",
                str(ev.fuente) if ev.fuente else "",
                str(ev.gps_lat) if ev.gps_lat is not None else "",
                str(ev.gps_lng) if ev.gps_lng is not None else "",
                str(ev.dentro_geocerca) if ev.dentro_geocerca is not None else "",
                ev.foto_url or "",
                ev.ip or "",
                ev.observacion or "",
            ])
        return resp


class ExportAusenciasCSV(TTLoginRequiredMixin, View):
    def get(self, request):
        if not _can_export(request.user, "ausencias"):
            return _forbid()
        qs = SolicitudAusencia.objects.select_related("empresa", "empleado", "tipo_ausencia", "estado")
        qs = _apply_empresa_scope(qs, request)

        desde = _parse_date(request.GET.get("desde"))
        hasta = _parse_date(request.GET.get("hasta"))
        if desde:
            qs = qs.filter(fecha_fin__gte=desde)
        if hasta:
            qs = qs.filter(fecha_inicio__lte=hasta)

        if request.user.has_role("EMPLEADO") and request.user.empleado_id:
            qs = qs.filter(empleado_id=request.user.empleado_id)
        if request.user.has_role("MANAGER") and request.user.empleado_id:
            team_ids = Empleado.objects.filter(manager_id=request.user.empleado_id).values_list("id", flat=True)
            qs = qs.filter(empleado_id__in=list(team_ids))

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="ausencias.csv"'
        w = csv.writer(resp)
        w.writerow(["empresa", "empleado", "tipo_ausencia", "fecha_inicio", "fecha_fin", "dias_habiles", "motivo", "estado_codigo", "estado_descripcion", "flujo_actual", "creada_el", "adjunto_url"])
        for s in qs.order_by("-creada_el"):
            w.writerow([
                str(s.empresa),
                str(s.empleado),
                str(s.tipo_ausencia),
                s.fecha_inicio.isoformat(),
                s.fecha_fin.isoformat(),
                str(s.dias_habiles) if s.dias_habiles is not None else "",
                s.motivo or "",
                (s.estado.codigo if s.estado else ""),
                (s.estado.descripcion if s.estado else ""),
                s.flujo_actual if s.flujo_actual is not None else "",
                s.creada_el.isoformat() if s.creada_el else "",
                s.adjunto_url or "",
            ])
        return resp


class ExportKPIsCSV(TTLoginRequiredMixin, View):
    def get(self, request):
        if not _can_export(request.user, "kpis"):
            return _forbid()
        qs = KPI.objects.select_related("empresa")
        qs = _apply_empresa_scope(qs, request)
        desde = _parse_date(request.GET.get("desde"))
        hasta = _parse_date(request.GET.get("hasta"))
        qs = _date_range_filter(qs, "creado_el", desde, hasta, is_datetime=True)

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="kpis.csv"'
        w = csv.writer(resp)
        w.writerow(["empresa", "codigo", "nombre", "descripcion", "origen_datos", "activo", "creado_el"])
        for k in qs.order_by("codigo"):
            w.writerow([
                str(k.empresa),
                k.codigo,
                k.nombre,
                (k.descripcion or "").replace("\n", " ").strip(),
                k.origen_datos or "",
                str(k.activo) if k.activo is not None else "",
                k.creado_el.isoformat() if k.creado_el else "",
            ])
        return resp
