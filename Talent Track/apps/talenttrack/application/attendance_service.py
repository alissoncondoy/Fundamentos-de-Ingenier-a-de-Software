"""Attendance application service (use-cases).

Why this exists:
- Keep views thin (MVT).
- Keep attendance rules in one place (anti-trampa).

This module does NOT create or alter DB tables.
"""

from __future__ import annotations

import ipaddress
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional, Tuple, List

from django.conf import settings
from django.utils import timezone

from ..models import EventoAsistencia, DispositivoEmpleado
from ..utils import (
    _active_turno_for,
    _regla_asistencia_for,
    _tipo_evento_asistencia_id,
    _fuente_marcacion_id,
    _eval_geocerca,
    _save_attendance_photo,
    _rebuild_jornada,
)


@dataclass
class AttendanceState:
    next_code: Optional[str]
    next_label: str
    done: bool
    reason: Optional[str]
    btn_class: str
    requires_gps: bool
    requires_photo: bool
    first_in_iso: str


class AttendanceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _get_client_ip(request) -> str:
    ip = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    if not ip:
        ip = (request.META.get("REMOTE_ADDR") or "").strip()
    return ip[:100]


def _ip_allowed(client_ip: str, allowed: Any) -> bool:
    """allowed can be None, list[str], or str.

    Supports:
    - exact IP: "200.1.2.3"
    - CIDR: "192.168.1.0/24"
    """
    if not allowed:
        return True

    if isinstance(allowed, str):
        allowed_list = [allowed]
    elif isinstance(allowed, list):
        allowed_list = allowed
    else:
        return True

    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except Exception:
        return False

    for item in allowed_list:
        if not item:
            continue
        s = str(item).strip()
        try:
            if "/" in s:
                if ip_obj in ipaddress.ip_network(s, strict=False):
                    return True
            else:
                if ip_obj == ipaddress.ip_address(s):
                    return True
        except Exception:
            # ignore malformed allow item
            continue

    return False


def get_state(empresa_id, empleado_id, today: Optional[date] = None, strict_daily_pair: bool = True) -> AttendanceState:
    """Computes the next action for the employee today."""
    hoy = today or timezone.localdate()

    turno = _active_turno_for(empresa_id, empleado_id, hoy)

    check_in_id = _tipo_evento_asistencia_id("check_in")
    check_out_id = _tipo_evento_asistencia_id("check_out")

    events = list(
        EventoAsistencia.objects
        .filter(empresa_id=empresa_id, empleado_id=empleado_id, registrado_el__date=hoy)
        .order_by("registrado_el")
    )

    requires_gps = bool(getattr(turno, "requiere_gps", False)) if turno else False
    requires_photo = bool(getattr(turno, "requiere_foto", False)) if turno else False

    # strict: max 2 events/day (IN + OUT)
    if strict_daily_pair and len(events) >= 2:
        return AttendanceState(
            next_code=None,
            next_label="Jornada completada",
            done=True,
            reason="Ya registraste entrada y salida hoy.",
            btn_class="bg-gradient-secondary",
            requires_gps=requires_gps,
            requires_photo=requires_photo,
            first_in_iso=(events[0].registrado_el.isoformat() if events and events[0].registrado_el else ""),
        )

    next_code = "check_in"
    if len(events) == 0:
        next_code = "check_in"
    elif len(events) == 1:
        if str(events[0].tipo) != str(check_in_id):
            # inconsistent day
            return AttendanceState(
                next_code=None,
                next_label="No disponible",
                done=True,
                reason="Se detectó una marcación inconsistente. Contacta a RRHH.",
                btn_class="bg-gradient-secondary",
                requires_gps=requires_gps,
                requires_photo=requires_photo,
                first_in_iso="",
            )
        next_code = "check_out"

    first_in = None
    for ev in events:
        if str(ev.tipo) == str(check_in_id):
            first_in = ev
            break

    return AttendanceState(
        next_code=next_code,
        next_label=("Registrar Entrada" if next_code == "check_in" else "Registrar Salida"),
        done=False,
        reason=None,
        btn_class=("bg-gradient-danger" if next_code == "check_in" else "bg-gradient-success"),
        requires_gps=requires_gps,
        requires_photo=requires_photo,
        first_in_iso=(first_in.registrado_el.isoformat() if first_in and first_in.registrado_el else ""),
    )


def _validate_time_window(turno, next_code: str, now_local: datetime, hoy: date) -> None:
    """Simple anti-trampa time window.

    - For check_in: allowed from (start-180min) to (start+180min)
    - For check_out: allowed from (end-240min) to (end+480min)

    If turno has no start/end, it won't block.
    """
    if not turno:
        return

    # Turno times can be null
    start_t = getattr(turno, "hora_inicio", None)
    end_t = getattr(turno, "hora_fin", None)

    if next_code == "check_in" and start_t:
        start_dt = timezone.make_aware(datetime.combine(hoy, start_t))
        if now_local < start_dt - timedelta(minutes=180) or now_local > start_dt + timedelta(minutes=180):
            raise AttendanceError("Fuera de la ventana de marcación para ENTRADA.")

    if next_code == "check_out" and end_t:
        end_dt = timezone.make_aware(datetime.combine(hoy, end_t))
        if now_local < end_dt - timedelta(minutes=240) or now_local > end_dt + timedelta(minutes=480):
            raise AttendanceError("Fuera de la ventana de marcación para SALIDA.")


def create_mark(request, payload: dict, strict_daily_pair: bool = True) -> Tuple[EventoAsistencia, str]:
    """Validates and creates an attendance event.

    Returns (event, next_code_that_was_saved)
    """
    # Optional: RRHH/SUPERADMIN can mark for a selected employee (still button-only, no manual time).
    # NOTE: The UI may send empleado_id even for the logged-in employee. We only treat it as
    # an override ("mark for another employee") when it differs from request.user.empleado_id.
    target_empleado_id = payload.get("empleado_id")

    empresa_id = request.user.empresa_id
    empleado_id = request.user.empleado_id
    hoy = timezone.localdate()

    # If the payload includes the same empleado_id as the logged-in user, just ignore the override.
    same_as_logged_in = bool(target_empleado_id) and str(target_empleado_id) == str(getattr(request.user, "empleado_id", ""))

    if target_empleado_id and not same_as_logged_in:
        if not (
            getattr(request.user, "is_superadmin", False)
            or request.user.has_role("SUPERADMIN")
            or request.user.has_role("ADMIN_RRHH")
        ):
            raise AttendanceError("No tienes permisos para marcar asistencia para otro empleado.", status=403)

        from ..models import Empleado  # local import to avoid cycles

        try:
            target_emp = Empleado.objects.only("id", "empresa_id").get(id=target_empleado_id)
        except Empleado.DoesNotExist:
            raise AttendanceError("Empleado no encontrado.")

        # Scope: ADMIN_RRHH only within own empresa
        if not (getattr(request.user, "is_superadmin", False) or request.user.has_role("SUPERADMIN")):
            if str(target_emp.empresa_id) != str(request.user.empresa_id):
                raise AttendanceError("No puedes marcar asistencia para empleados de otra empresa.", status=403)

        empresa_id = target_emp.empresa_id
        empleado_id = target_emp.id
    else:
        if not request.user.empleado_id:
            raise AttendanceError("Tu usuario no tiene empleado asociado.")

    # normalize payload
    # Algunas UIs pueden enviar strings vacíos/"null". Normalizamos para evitar errores de conversión.
    lat = payload.get("lat")
    lng = payload.get("lng")
    if isinstance(lat, str) and lat.strip().lower() in ("", "null", "none", "nan"):
        lat = None
    if isinstance(lng, str) and lng.strip().lower() in ("", "null", "none", "nan"):
        lng = None

    photo = payload.get("photo")
    device_id = payload.get("device_id")

    # current context
    turno = _active_turno_for(empresa_id, empleado_id, hoy)
    regla = _regla_asistencia_for(empresa_id)

    # IP allowlist
    client_ip = _get_client_ip(request)
    if regla and not _ip_allowed(client_ip, regla.ip_permitidas):
        raise AttendanceError("Tu red/IP no está autorizada para marcar asistencia desde aquí.")

    # Determine next action (strict)
    state = get_state(empresa_id, empleado_id, today=hoy, strict_daily_pair=strict_daily_pair)
    if state.done or not state.next_code:
        raise AttendanceError(state.reason or "No puedes marcar asistencia en este momento.")

    next_code = state.next_code

    # anti-double-click: block if last event < 30s
    last_ev = (
        EventoAsistencia.objects
        .filter(empresa_id=empresa_id, empleado_id=empleado_id)
        .order_by("-registrado_el")
        .first()
    )
    if last_ev and last_ev.registrado_el:
        if timezone.now() - last_ev.registrado_el < timedelta(seconds=30):
            raise AttendanceError("Espera unos segundos antes de volver a marcar.")

    # requirements
    if turno and getattr(turno, "requiere_gps", False) and (lat is None or lng is None):
        raise AttendanceError("Este turno requiere GPS para registrar asistencia.")
    if turno and getattr(turno, "requiere_foto", False) and not photo:
        raise AttendanceError("Este turno requiere fotografía para registrar asistencia.")

    # time window
    now_local = timezone.localtime(timezone.now())
    _validate_time_window(turno, next_code, now_local, hoy)

    # normalize coords
    try:
        dlat = Decimal(str(lat)) if lat is not None else None
        dlng = Decimal(str(lng)) if lng is not None else None
    except Exception:
        raise AttendanceError("Coordenadas inválidas. Intenta nuevamente habilitando ubicación.")

    # geofence
    # NOTE: temporal flag to allow testing marking without blocking by geofence.
    # Set ATTENDANCE_ENFORCE_GEOFENCE=True in settings.py to re-enable enforcement.
    enforce_geofence = bool(getattr(settings, "ATTENDANCE_ENFORCE_GEOFENCE", False))

    dentro = None
    geocerca = getattr(regla, "geocerca", None) if regla else None
    if geocerca:
        dentro = _eval_geocerca(
            geocerca,
            float(dlat) if dlat is not None else None,
            float(dlng) if dlng is not None else None,
        )
        # If geofence exists and gps is provided, optionally block outside.
        if enforce_geofence and dentro is False:
            raise AttendanceError("Estás fuera de la geocerca autorizada. No se puede marcar.")

    check_in_id = _tipo_evento_asistencia_id("check_in")
    check_out_id = _tipo_evento_asistencia_id("check_out")
    fuente_web_id = _fuente_marcacion_id("web")

    tipo_id = check_in_id if next_code == "check_in" else check_out_id

    foto_url = None
    if photo:
        try:
            foto_url = _save_attendance_photo(photo, empresa_id, empleado_id)
        except Exception:
            raise AttendanceError("No se pudo guardar la foto. Intenta nuevamente.")

    # device uuid (FK a asistencia.dispositivo_empleado)
    # Si el front manda un UUID que no existe en la tabla, Postgres revienta con FK.
    # Para permitir pruebas (y evitar bloqueos), solo guardamos dispositivo_id si
    # existe y pertenece al mismo empleado/empresa; caso contrario lo ignoramos.
    raw_device_uuid = None
    device_uuid = None
    if device_id:
        try:
            raw_device_uuid = uuid.UUID(str(device_id))
        except Exception:
            raw_device_uuid = None

    if raw_device_uuid:
        if DispositivoEmpleado.objects.filter(
            id=raw_device_uuid,
            empresa_id=empresa_id,
            empleado_id=empleado_id,
        ).exists():
            device_uuid = raw_device_uuid
        else:
            device_uuid = None

    # metadata base (agregamos rastros útiles para debug)
    meta = {
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "requires_gps": bool(getattr(turno, "requiere_gps", False)) if turno else False,
        "requires_photo": bool(getattr(turno, "requiere_foto", False)) if turno else False,
    }
    if raw_device_uuid and device_uuid is None:
        meta["device_id_unregistered"] = str(raw_device_uuid)

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
        ip=client_ip,
        dispositivo_id=device_uuid,
        metadata=meta,
    )

    # recompute jornada (best-effort). Si falla el recálculo, NO bloqueamos la marcación.
    try:
        _rebuild_jornada(empresa_id, empleado_id, hoy, turno, regla)
    except Exception as e:
        try:
            meta = dict(ev.metadata or {})
            meta["jornada_rebuild_error"] = str(e)
            ev.metadata = meta
            ev.save(update_fields=["metadata"])
        except Exception:
            pass

    return ev, next_code
