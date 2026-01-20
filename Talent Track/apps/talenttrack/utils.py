"""Shared helpers used across TalentTrack views.

This module centralizes reusable logic (company scoping, date filters, attendance rules,
geo-fence evaluation, jornada rebuild, exports permissions).

Keeping this logic outside the view modules helps maintain a clean MVT structure.
"""

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


# ------------------------------------------------------------
# Export helpers for `import *` usage across view modules
#
# Python's `from module import *` will NOT import names that start with
# an underscore unless `__all__` is defined. Many of our helpers are
# intentionally prefixed with `_` but are still used by presentation
# views.
#
# We export all non-dunder globals to keep imports simple and avoid
# NameError at runtime.
__all__ = [name for name in globals().keys() if not name.startswith("__")]
