import csv
import base64
import json
import os
from decimal import Decimal
from datetime import datetime, date, time, timedelta
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView, FormView

from .mixins import TTLoginRequiredMixin, RoleRequiredMixin
from .tt_auth import COOKIE_NAME, build_cookie_for_user, authenticate_login
from .models import (
    Empresa, UnidadOrganizacional, Puesto, Turno,
    Empleado, EventoAsistencia, JornadaCalculada,
    TipoEventoAsistencia, FuenteMarcacion,
    AsignacionTurno, ReglaAsistencia, Geocerca,
    TipoAusencia, SolicitudAusencia, EstadoSolicitud,
    KPI, EvaluacionDesempeno, Usuario, Rol, UsuarioRol
)
from .forms import (
    EmpresaForm, UnidadOrganizacionalForm, PuestoForm, TurnoForm,
    EmpleadoForm, EventoAsistenciaForm, TipoAusenciaForm, SolicitudAusenciaForm,
    KPIForm, UsuarioForm, UsuarioCreateWithRolForm, EmpleadoUsuarioAltaForm, RolForm, UsuarioRolForm
)

from .services.dashboard_factory import DashboardFactory


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
_ESTADO_JORNADA_CACHE: dict[str, str] = {}


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


def _estado_jornada_id(codigo: str):
    """Devuelve el UUID (string) del catálogo config.estado_jornada por código."""
    if not codigo:
        return None
    if codigo in _ESTADO_JORNADA_CACHE:
        return _ESTADO_JORNADA_CACHE[codigo]
    try:
        estado_id = str(EstadoJornada.objects.only("id").get(codigo=codigo).id)
    except EstadoJornada.DoesNotExist:
        return None
    _ESTADO_JORNADA_CACHE[codigo] = estado_id
    return estado_id


# Cache simple para IDs de catálogos (evita hits repetidos)
_TIPO_EVENTO_ASISTENCIA_CACHE: dict[str, str] = {}
_FUENTE_MARCACION_CACHE: dict[str, str] = {}


def _tipo_evento_asistencia_id(codigo: str):
    """Devuelve el UUID (string) del catálogo config.tipo_evento_asistencia por código."""
    if not codigo:
        return None
    if codigo in _TIPO_EVENTO_ASISTENCIA_CACHE:
        return _TIPO_EVENTO_ASISTENCIA_CACHE[codigo]
    try:
        tipo_id = str(TipoEventoAsistencia.objects.only("id").get(codigo=codigo).id)
    except TipoEventoAsistencia.DoesNotExist:
        return None
    _TIPO_EVENTO_ASISTENCIA_CACHE[codigo] = tipo_id
    return tipo_id


def _fuente_marcacion_id(codigo: str):
    """Devuelve el UUID (string) del catálogo config.fuente_marcacion por código."""
    if not codigo:
        return None
    if codigo in _FUENTE_MARCACION_CACHE:
        return _FUENTE_MARCACION_CACHE[codigo]
    try:
        fuente_id = str(FuenteMarcacion.objects.only("id").get(codigo=codigo).id)
    except FuenteMarcacion.DoesNotExist:
        return None
    _FUENTE_MARCACION_CACHE[codigo] = fuente_id
    return fuente_id


def _active_turno_for(empresa_id, empleado_id, hoy: date):
    """Obtiene el turno activo del empleado para la fecha dada (si existe)."""
    asign = (
        AsignacionTurno.objects
        .select_related("turno")
        .filter(empresa_id=empresa_id, empleado_id=empleado_id, es_activo=True, fecha_inicio__lte=hoy)
        .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))
        .order_by("-fecha_inicio")
        .first()
    )
    return asign.turno if asign else None


def _regla_asistencia_for(empresa_id):
    """Obtiene la regla de asistencia más reciente de la empresa."""
    return ReglaAsistencia.objects.select_related("geocerca").filter(empresa_id=empresa_id).order_by("-creado_el").first()


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distancia en metros entre dos coordenadas (aprox)."""
    from math import radians, sin, cos, sqrt, asin
    R = 6371000.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dl/2)**2
    return 2 * R * asin(sqrt(a))


def _point_in_polygon(lat: float, lng: float, points: list[dict]) -> bool:
    """Ray casting para punto en polígono. points=[{'lat':..,'lng':..}, ...]"""
    x = lng
    y = lat
    n = len(points)
    inside = False
    for i in range(n):
        j = (i - 1) % n
        xi, yi = points[i]["lng"], points[i]["lat"]
        xj, yj = points[j]["lng"], points[j]["lat"]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi)
        if intersect:
            inside = not inside
    return inside


def _eval_geocerca(geocerca: Geocerca | None, lat: float | None, lng: float | None) -> bool | None:
    """Retorna True/False si se puede evaluar, o None si no hay data."""
    if not geocerca or lat is None or lng is None:
        return None
    coords = geocerca.coordenadas or {}
    # Caso 1: círculo {center:{lat,lng}, radius_m}
    if isinstance(coords, dict) and "center" in coords and "radius_m" in coords:
        c = coords.get("center") or {}
        try:
            d = _haversine_m(float(lat), float(lng), float(c.get("lat")), float(c.get("lng")))
            return d <= float(coords.get("radius_m"))
        except Exception:
            return None
    # Caso 2: polígono {points:[{lat,lng},...]}
    if isinstance(coords, dict) and "points" in coords and isinstance(coords["points"], list) and len(coords["points"]) >= 3:
        try:
            return _point_in_polygon(float(lat), float(lng), coords["points"])
        except Exception:
            return None
    return None


def _save_attendance_photo(base64_data: str, empresa_id, empleado_id) -> str | None:
    """Guarda una foto base64 en MEDIA y retorna la URL relativa."""
    if not base64_data:
        return None
    # base64_data puede venir como "data:image/jpeg;base64,...."
    if "," in base64_data:
        header, b64 = base64_data.split(",", 1)
        ext = "jpg"
        if "image/png" in header:
            ext = "png"
    else:
        b64 = base64_data
        ext = "jpg"
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return None

    folder = os.path.join("attendance", str(empresa_id), str(empleado_id))
    abs_dir = os.path.join(settings.MEDIA_ROOT, folder)
    os.makedirs(abs_dir, exist_ok=True)

    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}.{ext}"
    abs_path = os.path.join(abs_dir, filename)
    with open(abs_path, "wb") as f:
        f.write(raw)

    return settings.MEDIA_URL + f"{folder}/{filename}"


def _rebuild_jornada(empresa_id, empleado_id, fecha: date, turno: Turno | None, regla: ReglaAsistencia | None):
    """Recalcula (y upsertea) asistencia.jornada_calculada para el día.

    Regla general:
    - minutos_trabajados: suma de intervalos check_in -> check_out.
    - tardanza: según hora_inicio + tolerancia + umbral de regla (si existe).
    - extra: según hora_fin.
    """
    check_in_id = _tipo_evento_asistencia_id("check_in")
    check_out_id = _tipo_evento_asistencia_id("check_out")

    eventos = list(
        EventoAsistencia.objects
        .filter(empresa_id=empresa_id, empleado_id=empleado_id, registrado_el__date=fecha)
        .order_by("registrado_el")
    )

    first_in = None
    last_out = None
    minutos_trabajados = 0

    # suma de pares (check_in -> check_out)
    open_in = None
    for ev in eventos:
        if str(ev.tipo) == str(check_in_id):
            if open_in is None:
                open_in = ev.registrado_el
                if first_in is None:
                    first_in = ev.registrado_el
        elif str(ev.tipo) == str(check_out_id):
            if open_in is not None and ev.registrado_el and ev.registrado_el > open_in:
                delta = ev.registrado_el - open_in
                minutos_trabajados += int(delta.total_seconds() // 60)
                open_in = None
            last_out = ev.registrado_el

    # si quedó abierto (sin salida), contamos hasta ahora SOLO para UI (no para cierre definitivo)
    if open_in is not None:
        now = timezone.now()
        if now > open_in:
            minutos_trabajados += int((now - open_in).total_seconds() // 60)

    # tardanza / extra
    minutos_tardanza = 0
    minutos_extra = 0

    if turno and first_in and turno.hora_inicio:
        start_dt = timezone.make_aware(datetime.combine(fecha, turno.hora_inicio))
        toler = int(turno.tolerancia_minutos or 0)
        allowed = start_dt + timedelta(minutes=toler)
        diff_min = int((first_in - allowed).total_seconds() // 60)
        if diff_min > 0:
            # umbral global (si existe)
            umbral = int((regla.considera_tardanza_desde_min or 0) if regla else 0)
            minutos_tardanza = diff_min if diff_min >= umbral else 0

    if turno and last_out and turno.hora_fin:
        end_dt = timezone.make_aware(datetime.combine(fecha, turno.hora_fin))
        diff_min = int((last_out - end_dt).total_seconds() // 60)
        if diff_min > 0:
            minutos_extra = diff_min

    # estado jornada
    if first_in and last_out:
        estado_code = "completo"
    elif first_in and not last_out:
        estado_code = "incompleto"
    else:
        estado_code = "sin_registros"

    estado_id = _estado_jornada_id(estado_code)

    # upsert (si ya existe, actualiza)
    jc = JornadaCalculada.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, fecha=fecha).first()
    if jc:
        jc.hora_primera_entrada = first_in
        jc.hora_ultima_salida = last_out
        jc.minutos_trabajados = minutos_trabajados
        jc.minutos_tardanza = minutos_tardanza
        jc.minutos_extra = minutos_extra
        if estado_id:
            jc.estado_id = estado_id
        jc.calculado_el = timezone.now()
        jc.save(update_fields=[
            "hora_primera_entrada", "hora_ultima_salida",
            "minutos_trabajados", "minutos_tardanza", "minutos_extra",
            "estado", "calculado_el"
        ])
    else:
        # ojo: managed=False, pero se puede insertar si la tabla existe
        JornadaCalculada.objects.create(
            empresa_id=empresa_id,
            empleado_id=empleado_id,
            fecha=fecha,
            hora_primera_entrada=first_in,
            hora_ultima_salida=last_out,
            minutos_trabajados=minutos_trabajados,
            minutos_tardanza=minutos_tardanza,
            minutos_extra=minutos_extra,
            estado_id=estado_id,
            calculado_el=timezone.now(),
        )


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



# -----------------------
# AJAX options (dependent dropdowns)
# -----------------------
class _AjaxOptionsBase(RoleRequiredMixin, View):
    required_roles = ("SUPERADMIN", "ADMIN_RRHH")

    def _empresa_id(self, request):
        # SUPERADMIN puede consultar cualquier empresa
        if request.user.has_role("SUPERADMIN") or getattr(request.user, "is_superadmin", False):
            return request.GET.get("empresa") or None
        # RRHH queda acotado a su empresa
        return getattr(request.user, "empresa_id", None)

    def _json(self, rows):
        from django.http import JsonResponse
        return JsonResponse({"results": rows})


class AjaxUnidades(_AjaxOptionsBase):
    def get(self, request):
        empresa_id = self._empresa_id(request)
        qs = UnidadOrganizacional.objects.all()
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        rows = [{"id": str(x.id), "text": x.nombre} for x in qs.order_by("nombre")[:1000]]
        return self._json(rows)


class AjaxPuestos(_AjaxOptionsBase):
    def get(self, request):
        empresa_id = self._empresa_id(request)
        qs = Puesto.objects.all()
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        rows = [{"id": str(x.id), "text": x.nombre} for x in qs.order_by("nombre")[:1000]]
        return self._json(rows)


class AjaxEmpleados(_AjaxOptionsBase):
    def get(self, request):
        empresa_id = self._empresa_id(request)
        qs = Empleado.objects.all()
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        q = (request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(nombres__icontains=q) | Q(apellidos__icontains=q) | Q(documento__icontains=q) | Q(email__icontains=q))
        # Optimización: si no hay búsqueda, devolvemos pocos (para combos con autocompletado tipo Select2)
        limit = 50 if not q else 1000
        qs = qs.order_by("apellidos", "nombres")[:limit]
        rows = [{"id": str(x.id), "text": f"{x.apellidos} {x.nombres}"} for x in qs]
        return self._json(rows)


class AjaxManagers(_AjaxOptionsBase):
    """Opciones de Manager.

    Regla de negocio aplicada (simple y estable):
    - Un Manager debe ser un empleado que tenga usuario con rol MANAGER.
    - Se filtra por empresa y por búsqueda (q).

    Nota: No crea tablas nuevas; utiliza las relaciones existentes (Usuario -> Empleado, UsuarioRol -> Rol).
    """

    def get(self, request):
        empresa_id = self._empresa_id(request)
        qs = Empleado.objects.all()
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)

        q = (request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(nombres__icontains=q) | Q(apellidos__icontains=q) | Q(documento__icontains=q) | Q(email__icontains=q))

        # Solo empleados con usuario rol MANAGER
        qs = qs.filter(usuario__usuariorol__rol__nombre="MANAGER").distinct()
        limit = 50 if not q else 1000
        qs = qs.order_by("apellidos", "nombres")[:limit]
        rows = [{"id": str(x.id), "text": f"{x.apellidos} {x.nombres}"} for x in qs]
        return self._json(rows)


class AjaxRoles(_AjaxOptionsBase):
    def get(self, request):
        empresa_id = self._empresa_id(request)
        qs = Rol.objects.all()
        if empresa_id:
            qs = qs.filter(Q(empresa_id__isnull=True) | Q(empresa_id=empresa_id))
        rows = [{"id": str(x.id), "text": x.nombre} for x in qs.order_by("nombre")[:1000]]
        return self._json(rows)


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
        is_sa = getattr(self.request.user, "is_superadmin", False) or self.request.user.has_role("SUPERADMIN")
        ctx["can_create"] = is_sa or self.request.user.has_role("ADMIN_RRHH")
        ctx["create_url"] = reverse_lazy("tt_empleado_usuario_alta") if is_sa else reverse_lazy("tt_empleado_create")
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
        is_sa = getattr(self.request.user, "is_superadmin", False) or self.request.user.has_role("SUPERADMIN")
        ctx["can_create"] = is_sa or self.request.user.has_role("ADMIN_RRHH")
        ctx["create_url"] = reverse_lazy("tt_empleado_usuario_alta") if is_sa else reverse_lazy("tt_empleado_create")
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
        is_sa = getattr(self.request.user, "is_superadmin", False) or self.request.user.has_role("SUPERADMIN")
        ctx["can_create"] = is_sa or self.request.user.has_role("ADMIN_RRHH")
        ctx["create_url"] = reverse_lazy("tt_empleado_usuario_alta") if is_sa else reverse_lazy("tt_empleado_create")
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
        is_sa = getattr(self.request.user, "is_superadmin", False) or self.request.user.has_role("SUPERADMIN")
        ctx["can_create"] = is_sa or self.request.user.has_role("ADMIN_RRHH")
        ctx["create_url"] = reverse_lazy("tt_empleado_usuario_alta") if is_sa else reverse_lazy("tt_empleado_create")
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "empleados")
        return ctx




class EmpleadoUsuarioAltaCreate(RoleRequiredMixin, FormView):
    """SUPERADMIN: alta de Empleado + Usuario + Rol en un solo paso.

    - La empresa se elige primero.
    - Unidad/Puesto/Manager/Rol se filtran por empresa (AJAX + server-side).
    - Se crea todo en una sola transacción (ver forms.EmpleadoUsuarioAltaForm.save()).
    """

    required_roles = ("SUPERADMIN",)
    form_class = EmpleadoUsuarioAltaForm
    template_name = "talenttrack/onboarding_empleado_usuario.html"
    success_url = reverse_lazy("tt_usuario_list")

    def get_initial(self):
        initial = super().get_initial()
        empresa_id = self.request.GET.get("empresa")
        if empresa_id:
            initial["empresa"] = empresa_id
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        empresa_id = self.request.POST.get("empresa") or self.request.GET.get("empresa")
        # Siempre mostramos empresas ordenadas
        form.fields["empresa"].queryset = Empresa.objects.all().order_by("razon_social")

        if empresa_id:
            form.fields["unidad"].queryset = UnidadOrganizacional.objects.filter(empresa_id=empresa_id).order_by("nombre")
            form.fields["puesto"].queryset = Puesto.objects.filter(empresa_id=empresa_id).order_by("nombre")
            form.fields["manager"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")
            # Roles globales (empresa_id NULL) + roles por empresa
            form.fields["rol"].queryset = Rol.objects.all().order_by("nombre")
        else:
            # Si aún no hay empresa, dejamos combos vacíos para forzar la selección primero (más pro)
            form.fields["unidad"].queryset = UnidadOrganizacional.objects.none()
            form.fields["puesto"].queryset = Puesto.objects.none()
            form.fields["manager"].queryset = Empleado.objects.none()
            form.fields["rol"].queryset = Rol.objects.all().order_by("nombre")

        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["title"] = "Alta de empleado + usuario"
        ctx["subtitle"] = "Crea el empleado, su usuario y el rol (obligatorio) en un solo formulario."
        ctx["enable_dependent_selects"] = True
        return ctx

    def form_valid(self, form):
        from django import forms as dj_forms
        try:
            empleado, usuario = form.save()
        except dj_forms.ValidationError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except Exception as exc:
            form.add_error(None, "No se pudo completar el alta. " + str(exc))
            return self.form_invalid(form)

        messages.success(self.request, f"Alta realizada: {empleado} / {usuario.email}")
        return super().form_valid(form)


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
class AsistenciaHoy(TTLoginRequiredMixin, TemplateView):
    """Pantalla de marcación rápida (estilo app) para el usuario logueado."""

    template_name = "talenttrack/asistencia_hoy.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.empleado_id:
            messages.warning(request, "Tu usuario no tiene un empleado asociado. Pide a RRHH que lo configure.")
            return redirect("tt_asistencia_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        empresa_id = self.request.user.empresa_id
        empleado_id = self.request.user.empleado_id

        turno = _active_turno_for(empresa_id, empleado_id, hoy)
        regla = _regla_asistencia_for(empresa_id)

        check_in_id = _tipo_evento_asistencia_id("check_in")
        check_out_id = _tipo_evento_asistencia_id("check_out")

        last_ev = (
            EventoAsistencia.objects
            .filter(empresa_id=empresa_id, empleado_id=empleado_id, registrado_el__date=hoy)
            .order_by("-registrado_el")
            .first()
        )
        next_code = "check_in"
        if last_ev and str(last_ev.tipo) == str(check_in_id):
            next_code = "check_out"
        elif last_ev and str(last_ev.tipo) == str(check_out_id):
            next_code = "check_in"

        # Para el contador (si el empleado está "dentro")
        first_in = (
            EventoAsistencia.objects
            .filter(empresa_id=empresa_id, empleado_id=empleado_id, registrado_el__date=hoy, tipo=check_in_id)
            .order_by("registrado_el")
            .first()
        )
        in_progress = (next_code == "check_out") and bool(first_in)

        # Resumen mensual (por jornadas calculadas)
        month_start = hoy.replace(day=1)
        jc_qs = JornadaCalculada.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, fecha__gte=month_start, fecha__lte=hoy)
        days_worked = jc_qs.exclude(minutos_trabajados=0).count()
        total_minutes = sum(j.minutos_trabajados or 0 for j in jc_qs)
        punctual_days = sum(1 for j in jc_qs if (j.minutos_trabajados or 0) > 0 and (j.minutos_tardanza or 0) == 0)
        punctuality = round((punctual_days / days_worked) * 100) if days_worked else 100

        ctx.update({
            "hoy": hoy,
            "turno": turno,
            "regla": regla,
            "geocerca": getattr(regla, "geocerca", None) if regla else None,
            "next_code": next_code,
            "next_label": "Registrar Entrada" if next_code == "check_in" else "Registrar Salida",
            "btn_class": "bg-gradient-danger" if next_code == "check_in" else "bg-gradient-success",
            "in_progress": in_progress,
            "first_in_iso": first_in.registrado_el.isoformat() if first_in and first_in.registrado_el else "",
            "requiere_gps": bool(turno.requiere_gps) if turno else False,
            "requiere_foto": bool(turno.requiere_foto) if turno else False,
            "resumen_puntualidad": punctuality,
            "resumen_dias": days_worked,
            "resumen_horas": round(total_minutes / 60) if total_minutes else 0,
        })
        return ctx


class AsistenciaMarcar(TTLoginRequiredMixin, View):
    """Endpoint de marcación rápida (POST JSON)."""

    def post(self, request, *args, **kwargs):
        if not request.user.empleado_id:
            return JsonResponse({"ok": False, "error": "Tu usuario no tiene empleado asociado."}, status=400)

        empresa_id = request.user.empresa_id
        empleado_id = request.user.empleado_id
        hoy = timezone.localdate()

        # payload
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            payload = {}

        lat = payload.get("lat")
        lng = payload.get("lng")
        photo = payload.get("photo")

        # turno / reglas
        turno = _active_turno_for(empresa_id, empleado_id, hoy)
        regla = _regla_asistencia_for(empresa_id)

        if turno and turno.requiere_gps and (lat is None or lng is None):
            return JsonResponse({"ok": False, "error": "Este turno requiere GPS para registrar asistencia."}, status=400)
        if turno and turno.requiere_foto and not photo:
            return JsonResponse({"ok": False, "error": "Este turno requiere fotografía para registrar asistencia."}, status=400)

        # normaliza coords
        dlat = Decimal(str(lat)) if lat is not None else None
        dlng = Decimal(str(lng)) if lng is not None else None

        # dentro geocerca (si aplica)
        dentro = None
        geocerca = getattr(regla, "geocerca", None) if regla else None
        if geocerca:
            dentro = _eval_geocerca(geocerca, float(dlat) if dlat is not None else None, float(dlng) if dlng is not None else None)

        # decide tipo (check_in/check_out) según último evento del día
        check_in_id = _tipo_evento_asistencia_id("check_in")
        check_out_id = _tipo_evento_asistencia_id("check_out")
        fuente_web_id = _fuente_marcacion_id("web")

        last_ev = (
            EventoAsistencia.objects
            .filter(empresa_id=empresa_id, empleado_id=empleado_id, registrado_el__date=hoy)
            .order_by("-registrado_el")
            .first()
        )
        next_code = "check_in"
        if last_ev and str(last_ev.tipo) == str(check_in_id):
            next_code = "check_out"

        tipo_id = check_in_id if next_code == "check_in" else check_out_id

        foto_url = _save_attendance_photo(photo, empresa_id, empleado_id) if photo else None

        ev = EventoAsistencia.objects.create(
            empresa_id=empresa_id,
            empleado_id=empleado_id,
            tipo=tipo_id,
            fuente=fuente_web_id,
            registrado_el=timezone.now(),
            gps_lat=dlat,
            gps_lng=dlng,
            dentro_geocerca=dentro,
            foto_url=foto_url,
            ip=(request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "")[:100],
            metadata={
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "requires_gps": bool(turno.requiere_gps) if turno else False,
                "requires_photo": bool(turno.requiere_foto) if turno else False,
            },
        )

        # recalcula jornada (para que el resumen/alertas se actualicen)
        _rebuild_jornada(empresa_id, empleado_id, hoy, turno, regla)

        # respuesta para modal UI
        msg = "Entrada registrada exitosamente" if next_code == "check_in" else "Salida registrada exitosamente"
        return JsonResponse({
            "ok": True,
            "message": msg,
            "tipo": next_code,
            "registrado_el": ev.registrado_el.isoformat() if ev.registrado_el else "",
            "gps": {"lat": str(ev.gps_lat) if ev.gps_lat else None, "lng": str(ev.gps_lng) if ev.gps_lng else None},
            "dentro_geocerca": ev.dentro_geocerca,
            "foto_url": ev.foto_url,
        })

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
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH") or self.request.user.is_superadmin
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "asistencia")
        return ctx

class AsistenciaCreate(TTLoginRequiredMixin, CreateView):
    model = EventoAsistencia
    form_class = EventoAsistenciaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_asistencia_list")

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.has_role("ADMIN_RRHH") or request.user.is_superadmin):
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
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH") or self.request.user.is_superadmin
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "ausencias")
        return ctx

class AusenciaCreate(TTLoginRequiredMixin, CreateView):
    model = SolicitudAusencia
    form_class = SolicitudAusenciaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_ausencia_list")

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.has_role("ADMIN_RRHH") or request.user.is_superadmin):
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
        is_sa = getattr(self.request.user, "is_superadmin", False) or self.request.user.has_role("SUPERADMIN")
        ctx["can_create"] = is_sa or self.request.user.has_role("ADMIN_RRHH")
        ctx["create_url"] = reverse_lazy("tt_empleado_usuario_alta") if is_sa else reverse_lazy("tt_empleado_create")
        ctx["can_mark"] = bool(self.request.user.empleado_id)
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
    form_class = UsuarioCreateWithRolForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_usuario_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        empresa_id = self.request.POST.get("empresa") or self.request.GET.get("empresa")
        if empresa_id:
            form.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")
            form.fields["rol"].queryset = Rol.objects.all().order_by("nombre")
        else:
            form.fields["empleado"].queryset = Empleado.objects.none()
            form.fields["rol"].queryset = Rol.objects.all().order_by("nombre")
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Usuario"
        ctx["enable_dependent_selects_usuario"] = True
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
