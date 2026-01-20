import csv

from django.http import HttpResponse
from django.views import View

from ...mixins import TTLoginRequiredMixin
from ...models import Empleado, EventoAsistencia, SolicitudAusencia, KPI
from ...utils import *  # noqa

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
