import json

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, ListView

from ...mixins import TTLoginRequiredMixin
from ...models import EventoAsistencia, JornadaCalculada, Empleado, TipoEventoAsistencia
from ...utils import *  # noqa
from ...application.attendance_service import get_state, create_mark, AttendanceError

# -----------------------
# Asistencia (Empleado puede registrar lo suyo; RRHH puede registrar de su empresa)
# -----------------------
class AsistenciaHoy(TTLoginRequiredMixin, TemplateView):
    """Pantalla de marcación rápida (estilo app) para el usuario logueado."""

    template_name = "talenttrack/asistencia_hoy.html"

    def dispatch(self, request, *args, **kwargs):
        # Normal: each user marks their own attendance (employee-linked user).
        # Exception: SUPERADMIN / ADMIN_RRHH can temporarily select an employee to mark (still via button flow).
        if not request.user.empleado_id and not (request.user.is_superadmin or request.user.has_role("ADMIN_RRHH")):
            messages.warning(request, "Tu usuario no tiene un empleado asociado. Pide a RRHH que lo configure.")
            return redirect("tt_asistencia_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = timezone.localdate()

        # Target employee selection (only for SUPERADMIN / ADMIN_RRHH when their user has no empleado_id)
        selected_empleado_id = self.request.user.empleado_id
        selected_empleado = None
        can_select_empleado = (not self.request.user.empleado_id) and (self.request.user.is_superadmin or self.request.user.has_role("ADMIN_RRHH"))

        if can_select_empleado:
            selected_empleado_id = self.request.GET.get("empleado") or None
            if selected_empleado_id:
                try:
                    selected_empleado = Empleado.objects.only("id", "empresa_id", "nombres", "apellidos").get(id=selected_empleado_id)
                except Empleado.DoesNotExist:
                    selected_empleado_id = None
                    selected_empleado = None

        # Resolve empresa/empleado to compute state
        empresa_id = self.request.user.empresa_id
        empleado_id = selected_empleado_id
        if selected_empleado:
            empresa_id = selected_empleado.empresa_id

        # Build employee options for selector
        empleado_options = None
        if can_select_empleado:
            qs = Empleado.objects.all().order_by("apellidos", "nombres")
            qs = _apply_empresa_scope(qs, self.request)
            empleado_options = qs

        turno = _active_turno_for(empresa_id, empleado_id, hoy)
        regla = _regla_asistencia_for(empresa_id)

        state = None
        in_progress = False
        days_worked = 0
        total_minutes = 0
        punctuality = 100

        if empleado_id:
            state = get_state(empresa_id, empleado_id, today=hoy, strict_daily_pair=True)

            # Para el contador (si el empleado está "dentro")
            in_progress = (state.next_code == "check_out") and bool(state.first_in_iso)

            # Resumen mensual (por jornadas calculadas)
            month_start = hoy.replace(day=1)
            jc_qs = JornadaCalculada.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, fecha__gte=month_start, fecha__lte=hoy)
            days_worked = jc_qs.exclude(minutos_trabajados=0).count()
            total_minutes = sum(j.minutos_trabajados or 0 for j in jc_qs)
            punctual_days = sum(1 for j in jc_qs if (j.minutos_trabajados or 0) > 0 and (j.minutos_tardanza or 0) == 0)
            punctuality = round((punctual_days / days_worked) * 100) if days_worked else 100

        if not empleado_id:
            # Nothing selected yet
            ctx.update({
                "hoy": hoy,
                "turno": None,
                "regla": None,
                "geocerca": None,
                "next_code": None,
                "next_label": "Selecciona un empleado",
                "btn_class": "bg-gradient-secondary",
                "mark_done": True,
                "mark_reason": "Selecciona un empleado para habilitar la marcación.",
                "in_progress": False,
                "first_in_iso": "",
                "requiere_gps": False,
                "requiere_foto": False,
                "resumen_puntualidad": 100,
                "resumen_dias": 0,
                "resumen_horas": 0,
                "can_select_empleado": can_select_empleado,
                "empleado_options": empleado_options,
                "empleado_selected_id": selected_empleado_id,
                "empleado_selected": selected_empleado,
            })
            return ctx

        ctx.update({
            "hoy": hoy,
            "turno": turno,
            "regla": regla,
            "geocerca": getattr(regla, "geocerca", None) if regla else None,
            "next_code": state.next_code,
            "next_label": state.next_label,
            "btn_class": state.btn_class,
            "mark_done": state.done,
            "mark_reason": state.reason,
            "in_progress": in_progress,
            "first_in_iso": state.first_in_iso,
            "requiere_gps": state.requires_gps,
            "requiere_foto": state.requires_photo,
            "resumen_puntualidad": punctuality,
            "resumen_dias": days_worked,
            "resumen_horas": round(total_minutes / 60) if total_minutes else 0,
            "can_select_empleado": can_select_empleado,
            "empleado_options": empleado_options,
            "empleado_selected_id": selected_empleado_id,
            "empleado_selected": selected_empleado,
        })
        return ctx


class AsistenciaMarcar(TTLoginRequiredMixin, View):
    """Endpoint de marcación rápida (POST JSON)."""

    def post(self, request, *args, **kwargs):
        # payload
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            payload = {}

        try:
            ev, next_code = create_mark(request, payload, strict_daily_pair=True)
        except AttendanceError as e:
            return JsonResponse({"ok": False, "error": e.message}, status=e.status)
        except Exception as e:
            # Para depuración en ambiente de desarrollo, devolvemos el error real.
            # En producción conviene ocultarlo y registrar el traceback.
            if getattr(settings, "DEBUG", False):
                return JsonResponse({"ok": False, "error": f"Error interno: {e}"}, status=500)
            return JsonResponse({"ok": False, "error": "No se pudo registrar. Intenta nuevamente."}, status=500)

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

        # text search (employee)
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(empleado__nombres__icontains=q)
                | Q(empleado__apellidos__icontains=q)
                | Q(empleado__documento__icontains=q)
                | Q(empleado__email__icontains=q)
            )

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
        ctx["q"] = self.request.GET.get("q", "")
        # Por diseño: NO hay creación manual de asistencia.
        # La marcación se hace únicamente con el flujo de botón (Entrada/Salida).
        ctx["can_create"] = False
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = True
        ctx["can_export"] = _can_export(self.request.user, "asistencia")

        # --- UI enrich (better readability for employees) ---
        eventos = list(ctx.get("eventos") or [])
        tipo_map = {t.id: (t.codigo or "") for t in TipoEventoAsistencia.objects.all()}
        for ev in eventos:
            code = (tipo_map.get(ev.tipo) or "").lower()
            if code == "check_in":
                ev.tt_label = "Entrada"
                ev.tt_badge = "success"
            elif code == "check_out":
                ev.tt_label = "Salida"
                ev.tt_badge = "dark"
            else:
                ev.tt_label = "Marcación"
                ev.tt_badge = "secondary"

            ev.tt_has_gps = bool(ev.gps_lat and ev.gps_lng)
            ev.tt_has_photo = bool(getattr(ev, "foto_url", None))
            # mask coords for nicer UI (keep full only in modal if needed)
            if ev.tt_has_gps:
                try:
                    ev.tt_gps_masked = f"{float(ev.gps_lat):.4f}, {float(ev.gps_lng):.4f}"
                except Exception:
                    ev.tt_gps_masked = "Capturado"
            else:
                ev.tt_gps_masked = "—"

        # employee dashboard strip: recent jornadas + turno hoy
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            hoy = timezone.localdate()
            empresa_id = self.request.user.empresa_id
            empleado_id = self.request.user.empleado_id
            ctx["turno_hoy"] = _active_turno_for(empresa_id, empleado_id, hoy)

            from datetime import timedelta
            start = hoy - timedelta(days=6)
            ctx["jornadas_recent"] = (
                JornadaCalculada.objects
                .filter(empresa_id=empresa_id, empleado_id=empleado_id, fecha__gte=start, fecha__lte=hoy)
                .order_by("-fecha")
            )
            ctx["eventos_recent"] = eventos[:10]

        return ctx
