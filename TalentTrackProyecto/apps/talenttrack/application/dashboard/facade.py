from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from ...models import (
    Empresa,
    Empleado,
    EventoAsistencia,
    JornadaCalculada,
    ResultadoKPI,
    SolicitudAusencia,
)
from ..catalog_cache import CatalogCache


@dataclass(frozen=True)
class DashboardScope:
    empresa_id: str | None
    empleado_ids: list[str]
    label: str


class ManagerDashboardFacade:
    """Construye datos del dashboard para rol MANAGER.

    Patrón aplicado: **Facade**.
    - Encapsula queries y cálculos, entregando un payload listo para la view/template.
    """

    def __init__(self):
        self.cache = CatalogCache()

    def scope_for_user(self, user) -> DashboardScope:
        if not user.empleado_id:
            return DashboardScope(empresa_id=user.empresa_id, empleado_ids=[], label="Mi equipo")

        qs = Empleado.objects.filter(empresa_id=user.empresa_id, manager_id=user.empleado_id)
        ids = [str(x) for x in qs.values_list("id", flat=True)]

        # Incluimos al manager en el panel para que no quede vacío.
        if str(user.empleado_id) not in ids:
            ids = [str(user.empleado_id)] + ids

        return DashboardScope(empresa_id=user.empresa_id, empleado_ids=ids, label="Mi equipo")

    def build(self, user, days: int = 14) -> dict:
        scope = self.scope_for_user(user)
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)

        # ------------------
        # Cards (hoy)
        # ------------------
        team_size = len(scope.empleado_ids)
        j_today = JornadaCalculada.objects.filter(
            empresa_id=scope.empresa_id,
            empleado_id__in=scope.empleado_ids,
            fecha=today,
        ).select_related("estado")

        presentes_hoy = j_today.filter(estado__codigo__in=["completo", "incompleto"]).count()
        tardanzas_hoy = j_today.filter(minutos_tardanza__gt=0).count()
        incompletas_hoy = j_today.filter(Q(estado__codigo="incompleto") | Q(hora_ultima_salida__isnull=True)).count()
        horas_extra_hoy = (j_today.aggregate(s=Sum("minutos_extra"))["s"] or 0) / 60.0

        ev_today = EventoAsistencia.objects.filter(
            empresa_id=scope.empresa_id,
            empleado_id__in=scope.empleado_ids,
            registrado_el__date=today,
        )
        geocerca_fuera = ev_today.filter(dentro_geocerca=False).count()

        pendientes = SolicitudAusencia.objects.filter(
            empresa_id=scope.empresa_id,
            empleado_id__in=scope.empleado_ids,
            estado__codigo="pendiente",
        ).count()

        periodo = today.strftime("%Y-%m")
        kpi_rojo = ResultadoKPI.objects.filter(
            empresa_id=scope.empresa_id,
            empleado_id__in=scope.empleado_ids,
            periodo=periodo,
            clasificacion__codigo="rojo",
        ).count()

        cards = {
            "team_size": team_size,
            "presentes_hoy": presentes_hoy,
            "tardanzas_hoy": tardanzas_hoy,
            "incompletas_hoy": incompletas_hoy,
            "pendientes_ausencia": pendientes,
            "kpi_rojo": kpi_rojo,
            "geocerca_fuera": geocerca_fuera,
            "horas_extra_hoy": round(horas_extra_hoy, 2),
        }

        # ------------------
        # Charts (series)
        # ------------------
        j_range = JornadaCalculada.objects.filter(
            empresa_id=scope.empresa_id,
            empleado_id__in=scope.empleado_ids,
            fecha__range=(start, today),
        )

        by_day = (
            j_range.values("fecha")
            .annotate(
                presentes=Count("id", filter=Q(estado__codigo__in=["completo", "incompleto"])),
                tardanzas=Count("id", filter=Q(minutos_tardanza__gt=0)),
                minutos_trabajados=Sum("minutos_trabajados"),
                minutos_extra=Sum("minutos_extra"),
            )
            .order_by("fecha")
        )

        labels, presentes, tardanzas, horas, extra = [], [], [], [], []
        for row in by_day:
            labels.append(row["fecha"].strftime("%d-%b"))
            presentes.append(int(row.get("presentes") or 0))
            tardanzas.append(int(row.get("tardanzas") or 0))
            horas.append(round((row.get("minutos_trabajados") or 0) / 60.0, 2))
            extra.append(round((row.get("minutos_extra") or 0) / 60.0, 2))

        sem = (
            ResultadoKPI.objects.filter(
                empresa_id=scope.empresa_id,
                empleado_id__in=scope.empleado_ids,
                periodo=periodo,
            )
            .values("clasificacion__codigo")
            .annotate(c=Count("id"))
        )
        sem_map = {r["clasificacion__codigo"] or "": int(r["c"]) for r in sem}
        kpi_sem = {
            "verde": sem_map.get("verde", 0),
            "amarillo": sem_map.get("amarillo", 0),
            "rojo": sem_map.get("rojo", 0),
        }

        charts = {
            "labels": labels,
            "presentes": presentes,
            "tardanzas": tardanzas,
            "horas": horas,
            "horas_extra": extra,
            "kpi_semaforo": kpi_sem,
            "periodo": periodo,
        }

        # ------------------
        # Alertas (tablas)
        # ------------------
        w_start = today - timedelta(days=6)
        tardy_rows = (
            JornadaCalculada.objects.filter(
                empresa_id=scope.empresa_id,
                empleado_id__in=scope.empleado_ids,
                fecha__range=(w_start, today),
                minutos_tardanza__gt=0,
            )
            .select_related("empleado")
            .order_by("-minutos_tardanza")[:7]
        )
        top_tardanzas = [
            {
                "empleado": r.empleado.nombre_completo,
                "fecha": r.fecha.strftime("%Y-%m-%d"),
                "min": int(r.minutos_tardanza or 0),
            }
            for r in tardy_rows
        ]

        abs_rows = (
            SolicitudAusencia.objects.filter(
                empresa_id=scope.empresa_id,
                empleado_id__in=scope.empleado_ids,
                estado__codigo="pendiente",
            )
            .select_related("empleado", "tipo_ausencia")
            .order_by("fecha_inicio")[:8]
        )
        pendientes_rows = [
            {
                "empleado": r.empleado.nombre_completo,
                "tipo": str(r.tipo_ausencia),
                "desde": r.fecha_inicio.strftime("%Y-%m-%d"),
                "hasta": r.fecha_fin.strftime("%Y-%m-%d"),
            }
            for r in abs_rows
        ]

        inc_rows = (
            j_today.filter(Q(estado__codigo="incompleto") | Q(hora_ultima_salida__isnull=True))
            .select_related("empleado")
            .order_by("empleado__apellidos")[:10]
        )
        incompletas_rows = [
            {
                "empleado": r.empleado.nombre_completo,
                "entrada": r.hora_primera_entrada.strftime("%H:%M") if r.hora_primera_entrada else "—",
                "salida": r.hora_ultima_salida.strftime("%H:%M") if r.hora_ultima_salida else "—",
            }
            for r in inc_rows
        ]

        kpi_rows = (
            ResultadoKPI.objects.filter(
                empresa_id=scope.empresa_id,
                empleado_id__in=scope.empleado_ids,
                periodo=periodo,
                clasificacion__codigo="rojo",
            )
            .select_related("empleado", "kpi", "clasificacion")
            .order_by("-cumplimiento_pct")[:10]
        )
        kpis_rojo_rows = [
            {
                "empleado": r.empleado.nombre_completo,
                "kpi": f"{r.kpi.codigo} - {r.kpi.nombre}",
                "valor": float(r.valor) if r.valor is not None else None,
                "pct": float(r.cumplimiento_pct) if r.cumplimiento_pct is not None else None,
            }
            for r in kpi_rows
        ]

        alerts = {
            "top_tardanzas": top_tardanzas,
            "pendientes_ausencia": pendientes_rows,
            "incompletas_hoy": incompletas_rows,
            "kpis_rojo": kpis_rojo_rows,
        }

        return {
            "scope": {"label": scope.label, "days": days, "today": today.strftime("%Y-%m-%d")},
            "cards": cards,
            "charts": charts,
            "alerts": alerts,
        }


class RRHHDashboardFacade:
    """Dashboard para ADMIN_RRHH.

    - Alcance: toda la empresa del usuario.
    - Enfoque: operación + gestión (pendientes, anomalías, cobertura).

    Patrón aplicado: **Facade**.
    """

    def __init__(self):
        self.cache = CatalogCache()

    def build(self, user, days: int = 14) -> dict:
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)

        empresa_id = getattr(user, "empresa_id", None)
        if not empresa_id:
            return {"scope": {}, "cards": {}, "charts": {}, "alerts": {}}

        # --- Cards ---
        empleados_total = Empleado.objects.filter(empresa_id=empresa_id).count()

        j_today = JornadaCalculada.objects.filter(empresa_id=empresa_id, fecha=today).select_related("estado", "empleado")
        presentes_hoy = j_today.filter(estado__codigo__in=["completo", "incompleto"]).count()
        tardanzas_hoy = j_today.filter(minutos_tardanza__gt=0).count()
        incompletas_hoy = j_today.filter(Q(estado__codigo="incompleto") | Q(hora_ultima_salida__isnull=True)).count()
        horas_extra_hoy = (j_today.aggregate(s=Sum("minutos_extra"))["s"] or 0) / 60.0

        ev_today = EventoAsistencia.objects.filter(empresa_id=empresa_id, registrado_el__date=today)
        geocerca_fuera = ev_today.filter(dentro_geocerca=False).count()

        pendientes_abs = SolicitudAusencia.objects.filter(empresa_id=empresa_id, estado__codigo="pendiente").count()

        periodo = today.strftime("%Y-%m")
        kpi_rojo = ResultadoKPI.objects.filter(empresa_id=empresa_id, periodo=periodo, clasificacion__codigo="rojo").count()

        nuevos_ingresos_30d = Empleado.objects.filter(empresa_id=empresa_id, fecha_ingreso__gte=today - timedelta(days=30)).count()
        empleados_sin_usuario = Empleado.objects.filter(empresa_id=empresa_id, usuario__isnull=True).count()

        cards = {
            "empleados_total": empleados_total,
            "presentes_hoy": presentes_hoy,
            "tardanzas_hoy": tardanzas_hoy,
            "incompletas_hoy": incompletas_hoy,
            "pendientes_ausencia": pendientes_abs,
            "kpi_rojo": kpi_rojo,
            "geocerca_fuera": geocerca_fuera,
            "horas_extra_hoy": round(horas_extra_hoy, 2),
            "nuevos_ingresos_30d": nuevos_ingresos_30d,
            "empleados_sin_usuario": empleados_sin_usuario,
        }

        # --- Charts ---
        j_range = JornadaCalculada.objects.filter(empresa_id=empresa_id, fecha__range=(start, today))
        by_day = (
            j_range.values("fecha")
            .annotate(
                presentes=Count("id", filter=Q(estado__codigo__in=["completo", "incompleto"])),
                tardanzas=Count("id", filter=Q(minutos_tardanza__gt=0)),
                minutos_trabajados=Sum("minutos_trabajados"),
                minutos_extra=Sum("minutos_extra"),
            )
            .order_by("fecha")
        )

        labels, presentes, tardanzas, horas, extra = [], [], [], [], []
        for row in by_day:
            labels.append(row["fecha"].strftime("%d-%b"))
            presentes.append(int(row.get("presentes") or 0))
            tardanzas.append(int(row.get("tardanzas") or 0))
            horas.append(round((row.get("minutos_trabajados") or 0) / 60.0, 2))
            extra.append(round((row.get("minutos_extra") or 0) / 60.0, 2))

        sem = (
            ResultadoKPI.objects.filter(empresa_id=empresa_id, periodo=periodo)
            .values("clasificacion__codigo")
            .annotate(c=Count("id"))
        )
        sem_map = {r["clasificacion__codigo"] or "": int(r["c"]) for r in sem}
        kpi_sem = {"verde": sem_map.get("verde", 0), "amarillo": sem_map.get("amarillo", 0), "rojo": sem_map.get("rojo", 0)}

        abs_by_estado = (
            SolicitudAusencia.objects.filter(empresa_id=empresa_id, fecha_inicio__lte=today, fecha_fin__gte=start)
            .values("estado__codigo")
            .annotate(c=Count("id"))
        )
        abs_map = {r["estado__codigo"] or "": int(r["c"]) for r in abs_by_estado}

        charts = {
            "labels": labels,
            "presentes": presentes,
            "tardanzas": tardanzas,
            "horas": horas,
            "horas_extra": extra,
            "kpi_semaforo": kpi_sem,
            "periodo": periodo,
            "ausencias_estado": {
                "pendiente": abs_map.get("pendiente", 0),
                "aprobado": abs_map.get("aprobado", 0),
                "rechazado": abs_map.get("rechazado", 0),
            },
        }

        # --- Alerts ---
        w_start = today - timedelta(days=6)
        tardy_rows = (
            JornadaCalculada.objects.filter(empresa_id=empresa_id, fecha__range=(w_start, today), minutos_tardanza__gt=0)
            .select_related("empleado")
            .order_by("-minutos_tardanza")[:7]
        )
        top_tardanzas = [{"empleado": r.empleado.nombre_completo, "fecha": r.fecha.strftime("%Y-%m-%d"), "min": int(r.minutos_tardanza or 0)} for r in tardy_rows]

        abs_rows = (
            SolicitudAusencia.objects.filter(empresa_id=empresa_id, estado__codigo="pendiente")
            .select_related("empleado", "tipo_ausencia")
            .order_by("fecha_inicio")[:8]
        )
        pendientes_rows = [{"empleado": r.empleado.nombre_completo, "tipo": str(r.tipo_ausencia), "desde": r.fecha_inicio.strftime("%Y-%m-%d"), "hasta": r.fecha_fin.strftime("%Y-%m-%d")} for r in abs_rows]

        inc_rows = (
            j_today.filter(Q(estado__codigo="incompleto") | Q(hora_ultima_salida__isnull=True))
            .select_related("empleado")
            .order_by("empleado__apellidos")[:10]
        )
        incompletas_rows = [{"empleado": r.empleado.nombre_completo, "entrada": r.hora_primera_entrada.strftime("%H:%M") if r.hora_primera_entrada else "—", "salida": r.hora_ultima_salida.strftime("%H:%M") if r.hora_ultima_salida else "—"} for r in inc_rows]

        sin_user_rows = (
            Empleado.objects.filter(empresa_id=empresa_id, usuario__isnull=True)
            .order_by("apellidos", "nombres")[:10]
        )
        sin_usuario = [{"empleado": r.nombre_completo, "documento": r.documento or "—", "email": r.email or "—"} for r in sin_user_rows]

        alerts = {
            "top_tardanzas": top_tardanzas,
            "pendientes_ausencia": pendientes_rows,
            "incompletas_hoy": incompletas_rows,
            "sin_usuario": sin_usuario,
        }

        return {
            "scope": {"label": "Mi empresa", "days": days, "today": today.strftime("%Y-%m-%d")},
            "cards": cards,
            "charts": charts,
            "alerts": alerts,
        }


class EmployeeDashboardFacade:
    """Dashboard para EMPLEADO.

    - Alcance: el propio empleado.
    - Enfoque: mi asistencia, mis incidencias, mi desempeño.
    """

    def __init__(self):
        self.cache = CatalogCache()

    def build(self, user, days: int = 14) -> dict:
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)

        empresa_id = getattr(user, "empresa_id", None)
        empleado_id = getattr(user, "empleado_id", None)
        if not empresa_id or not empleado_id:
            return {"scope": {}, "cards": {}, "charts": {}, "alerts": {}}

        j_today = JornadaCalculada.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, fecha=today).select_related("estado").first()
        estado_hoy = j_today.estado.codigo if (j_today and j_today.estado_id) else "sin_registro"
        horas_hoy = round(((j_today.minutos_trabajados or 0) / 60.0), 2) if j_today else 0
        tardanza_hoy = int(j_today.minutos_tardanza or 0) if j_today else 0
        incompleta_hoy = bool(j_today and (estado_hoy == "incompleto" or j_today.hora_ultima_salida is None))

        # Semana (7 días)
        w_start = today - timedelta(days=6)
        j_week = JornadaCalculada.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, fecha__range=(w_start, today))
        horas_semana = round(((j_week.aggregate(s=Sum("minutos_trabajados"))["s"] or 0) / 60.0), 2)
        horas_extra_semana = round(((j_week.aggregate(s=Sum("minutos_extra"))["s"] or 0) / 60.0), 2)

        pendientes_abs = SolicitudAusencia.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, estado__codigo="pendiente").count()

        periodo = today.strftime("%Y-%m")
        sem = (
            ResultadoKPI.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, periodo=periodo)
            .values("clasificacion__codigo")
            .annotate(c=Count("id"))
        )
        sem_map = {r["clasificacion__codigo"] or "": int(r["c"]) for r in sem}
        kpi_sem = {"verde": sem_map.get("verde", 0), "amarillo": sem_map.get("amarillo", 0), "rojo": sem_map.get("rojo", 0)}
        kpi_rojo = kpi_sem.get("rojo", 0)

        geocerca_fuera_7d = EventoAsistencia.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, registrado_el__date__range=(w_start, today), dentro_geocerca=False).count()

        cards = {
            "estado_hoy": estado_hoy,
            "horas_hoy": horas_hoy,
            "tardanza_hoy": tardanza_hoy,
            "incompleta_hoy": incompleta_hoy,
            "horas_semana": horas_semana,
            "horas_extra_semana": horas_extra_semana,
            "pendientes_ausencia": pendientes_abs,
            "kpi_rojo": kpi_rojo,
            "geocerca_fuera_7d": geocerca_fuera_7d,
        }

        j_range = JornadaCalculada.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, fecha__range=(start, today))
        by_day = (
            j_range.values("fecha")
            .annotate(
                minutos_trabajados=Sum("minutos_trabajados"),
                minutos_extra=Sum("minutos_extra"),
                minutos_tardanza=Sum("minutos_tardanza"),
            )
            .order_by("fecha")
        )
        labels, horas, extra, tardanza = [], [], [], []
        for row in by_day:
            labels.append(row["fecha"].strftime("%d-%b"))
            horas.append(round((row.get("minutos_trabajados") or 0) / 60.0, 2))
            extra.append(round((row.get("minutos_extra") or 0) / 60.0, 2))
            tardanza.append(int(row.get("minutos_tardanza") or 0))

        charts = {
            "labels": labels,
            "horas": horas,
            "horas_extra": extra,
            "tardanza": tardanza,
            "kpi_semaforo": kpi_sem,
            "periodo": periodo,
        }

        # Alerts
        abs_rows = (
            SolicitudAusencia.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id)
            .select_related("tipo_ausencia", "estado")
            .order_by("-creada_el")[:8]
        )
        mis_ausencias = [{"tipo": str(r.tipo_ausencia), "estado": r.estado.codigo if r.estado_id else "—", "desde": r.fecha_inicio.strftime("%Y-%m-%d"), "hasta": r.fecha_fin.strftime("%Y-%m-%d")} for r in abs_rows]

        inc_rows = (
            JornadaCalculada.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, fecha__range=(w_start, today))
            .filter(Q(estado__codigo="incompleto") | Q(hora_ultima_salida__isnull=True))
            .order_by("-fecha")[:7]
        )
        incompletas = [{"fecha": r.fecha.strftime("%Y-%m-%d"), "entrada": r.hora_primera_entrada.strftime("%H:%M") if r.hora_primera_entrada else "—", "salida": r.hora_ultima_salida.strftime("%H:%M") if r.hora_ultima_salida else "—"} for r in inc_rows]

        kpi_rows = (
            ResultadoKPI.objects.filter(empresa_id=empresa_id, empleado_id=empleado_id, periodo=periodo, clasificacion__codigo="rojo")
            .select_related("kpi", "clasificacion")
            .order_by("cumplimiento_pct")[:10]
        )
        kpis_rojo_rows = [{"kpi": f"{r.kpi.codigo} - {r.kpi.nombre}", "pct": float(r.cumplimiento_pct) if r.cumplimiento_pct is not None else None} for r in kpi_rows]

        alerts = {"mis_ausencias": mis_ausencias, "incompletas": incompletas, "kpis_rojo": kpis_rojo_rows}

        return {
            "scope": {"label": "Mi panel", "days": days, "today": today.strftime("%Y-%m-%d")},
            "cards": cards,
            "charts": charts,
            "alerts": alerts,
        }


class AuditorDashboardFacade:
    """Dashboard para AUDITOR.

    - Alcance: la empresa.
    - Enfoque: control + cumplimiento + anomalías.
    """

    def __init__(self):
        self.cache = CatalogCache()

    def build(self, user, days: int = 14) -> dict:
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)
        empresa_id = getattr(user, "empresa_id", None)
        if not empresa_id:
            return {"scope": {}, "cards": {}, "charts": {}, "alerts": {}}

        # Ventana de auditoría: 7 días para anomalías operativas
        w_start = today - timedelta(days=6)

        ev_week = EventoAsistencia.objects.filter(empresa_id=empresa_id, registrado_el__date__range=(w_start, today))
        fuera_geocerca = ev_week.filter(dentro_geocerca=False).count()
        sin_gps = ev_week.filter(Q(gps_lat__isnull=True) | Q(gps_lng__isnull=True)).count()
        sin_ip = ev_week.filter(Q(ip__isnull=True) | Q(ip="")).count()

        # Solicitudes que requieren soporte pero no adjuntan
        abs_sin_soporte = SolicitudAusencia.objects.filter(
            empresa_id=empresa_id,
            estado__codigo="pendiente",
            tipo_ausencia__requiere_soporte=True,
        ).filter(Q(adjunto_url__isnull=True) | Q(adjunto_url="")).count()

        from ...models import Usuario
        usuarios_sin_mfa = Usuario.objects.filter(empresa_id=empresa_id, mfa_habilitado=False).count()
        usuarios_total = Usuario.objects.filter(empresa_id=empresa_id).count()

        cards = {
            "fuera_geocerca_7d": fuera_geocerca,
            "sin_gps_7d": sin_gps,
            "sin_ip_7d": sin_ip,
            "abs_sin_soporte": abs_sin_soporte,
            "usuarios_total": usuarios_total,
            "usuarios_sin_mfa": usuarios_sin_mfa,
        }

        # Charts: anomalías por día
        ev_by_day = (
            ev_week.values("registrado_el__date")
            .annotate(
                fuera=Count("id", filter=Q(dentro_geocerca=False)),
                sin_gps=Count("id", filter=Q(Q(gps_lat__isnull=True) | Q(gps_lng__isnull=True))),
            )
            .order_by("registrado_el__date")
        )
        labels, fuera, no_gps = [], [], []
        for r in ev_by_day:
            d = r["registrado_el__date"]
            labels.append(d.strftime("%d-%b"))
            fuera.append(int(r.get("fuera") or 0))
            no_gps.append(int(r.get("sin_gps") or 0))

        mfa_on = max(usuarios_total - usuarios_sin_mfa, 0)
        charts = {
            "labels": labels,
            "fuera_geocerca": fuera,
            "sin_gps": no_gps,
            "mfa": {"on": mfa_on, "off": usuarios_sin_mfa},
        }

        # Alerts
        top_fuera = (
            ev_week.filter(dentro_geocerca=False)
            .values("empleado__apellidos", "empleado__nombres")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )
        top_fuera_rows = [{"empleado": f"{r['empleado__apellidos']} {r['empleado__nombres']}", "eventos": int(r["c"])} for r in top_fuera]

        abs_rows = (
            SolicitudAusencia.objects.filter(empresa_id=empresa_id, estado__codigo="pendiente", tipo_ausencia__requiere_soporte=True)
            .filter(Q(adjunto_url__isnull=True) | Q(adjunto_url=""))
            .select_related("empleado", "tipo_ausencia")
            .order_by("fecha_inicio")[:10]
        )
        abs_sin_soporte_rows = [{"empleado": r.empleado.nombre_completo, "tipo": str(r.tipo_ausencia), "desde": r.fecha_inicio.strftime("%Y-%m-%d"), "hasta": r.fecha_fin.strftime("%Y-%m-%d")} for r in abs_rows]

        ev_sin_gps_rows_qs = (
            ev_week.filter(Q(gps_lat__isnull=True) | Q(gps_lng__isnull=True))
            .select_related("empleado")
            .order_by("-registrado_el")[:10]
        )
        ev_sin_gps_rows = [{"empleado": r.empleado.nombre_completo, "fecha": r.registrado_el.strftime("%Y-%m-%d %H:%M") if r.registrado_el else "—", "tipo": str(r.tipo) if r.tipo else "—"} for r in ev_sin_gps_rows_qs]

        alerts = {
            "top_fuera_geocerca": top_fuera_rows,
            "abs_sin_soporte": abs_sin_soporte_rows,
            "eventos_sin_gps": ev_sin_gps_rows,
        }

        return {
            "scope": {"label": "Auditoría", "days": days, "today": today.strftime("%Y-%m-%d")},
            "cards": cards,
            "charts": charts,
            "alerts": alerts,
        }


class SuperAdminDashboardFacade:
    """Dashboard para SUPERADMIN (multiempresa + comparativas).

    Patrón aplicado: **Facade**.
    - Consolida métricas globales (todas las empresas) o por empresa seleccionada.
    """

    def __init__(self):
        self.cache = CatalogCache()

    def build(self, user, days: int = 14, empresa_id: str | None = None) -> dict:
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)

        empresas_qs = Empresa.objects.all().order_by("razon_social")
        empresa_obj = None
        if empresa_id:
            empresa_obj = empresas_qs.filter(id=empresa_id).first()
            if empresa_obj:
                empresas_qs = empresas_qs.filter(id=empresa_obj.id)
            else:
                # Si llega un ID inválido, vuelve a global.
                empresa_id = None

        empresa_ids = list(empresas_qs.values_list("id", flat=True))

        # ------------------
        # Cards (hoy)
        # ------------------
        j_today = JornadaCalculada.objects.filter(
            empresa_id__in=empresa_ids,
            fecha=today,
        ).select_related("estado")

        presentes_hoy = j_today.filter(estado__codigo__in=["completo", "incompleto"]).count()
        tardanzas_hoy = j_today.filter(minutos_tardanza__gt=0).count()
        incompletas_hoy = j_today.filter(Q(estado__codigo="incompleto") | Q(hora_ultima_salida__isnull=True)).count()
        horas_extra_hoy = (j_today.aggregate(s=Sum("minutos_extra"))["s"] or 0) / 60.0

        ev_today = EventoAsistencia.objects.filter(
            empresa_id__in=empresa_ids,
            registrado_el__date=today,
        )
        geocerca_fuera = ev_today.filter(dentro_geocerca=False).count()

        pendientes = SolicitudAusencia.objects.filter(
            empresa_id__in=empresa_ids,
            estado__codigo="pendiente",
        ).count()

        periodo = today.strftime("%Y-%m")
        kpi_rojo = ResultadoKPI.objects.filter(
            empresa_id__in=empresa_ids,
            periodo=periodo,
            clasificacion__codigo="rojo",
        ).count()

        empleados_total = Empleado.objects.filter(empresa_id__in=empresa_ids).count()

        cards = {
            "empresas": len(empresa_ids),
            "empleados": empleados_total,
            "presentes_hoy": presentes_hoy,
            "tardanzas_hoy": tardanzas_hoy,
            "incompletas_hoy": incompletas_hoy,
            "pendientes_ausencia": pendientes,
            "kpi_rojo": kpi_rojo,
            "geocerca_fuera": geocerca_fuera,
            "horas_extra_hoy": round(horas_extra_hoy, 2),
        }

        # ------------------
        # Comparativa por empresa (hoy)
        # ------------------
        emp_by_emp = {
            str(r["empresa_id"]): int(r["c"])
            for r in Empleado.objects.filter(empresa_id__in=empresa_ids)
            .values("empresa_id")
            .annotate(c=Count("id"))
        }

        presentes_by_emp = {
            str(r["empresa_id"]): int(r["c"])
            for r in j_today.filter(estado__codigo__in=["completo", "incompleto"])
            .values("empresa_id")
            .annotate(c=Count("id"))
        }

        tardy_by_emp = {
            str(r["empresa_id"]): int(r["c"])
            for r in j_today.filter(minutos_tardanza__gt=0)
            .values("empresa_id")
            .annotate(c=Count("id"))
        }

        pendientes_by_emp = {
            str(r["empresa_id"]): int(r["c"])
            for r in SolicitudAusencia.objects.filter(
                empresa_id__in=empresa_ids,
                estado__codigo="pendiente",
            )
            .values("empresa_id")
            .annotate(c=Count("id"))
        }

        kpi_rojo_by_emp = {
            str(r["empresa_id"]): int(r["c"])
            for r in ResultadoKPI.objects.filter(
                empresa_id__in=empresa_ids,
                periodo=periodo,
                clasificacion__codigo="rojo",
            )
            .values("empresa_id")
            .annotate(c=Count("id"))
        }

        empresas_rows = []
        for e in empresas_qs:
            eid = str(e.id)
            emp_cnt = emp_by_emp.get(eid, 0)
            pres = presentes_by_emp.get(eid, 0)
            tard = tardy_by_emp.get(eid, 0)
            pend = pendientes_by_emp.get(eid, 0)
            kroj = kpi_rojo_by_emp.get(eid, 0)
            tasa_pres = round((pres / emp_cnt * 100.0), 2) if emp_cnt else 0.0
            empresas_rows.append(
                {
                    "empresa_id": eid,
                    "empresa": str(e),
                    "empleados": emp_cnt,
                    "presentes": pres,
                    "tardanzas": tard,
                    "tasa_presentismo": tasa_pres,
                    "pendientes_ausencia": pend,
                    "kpi_rojo": kroj,
                }
            )

        # ------------------
        # Charts
        # ------------------
        j_range = JornadaCalculada.objects.filter(
            empresa_id__in=empresa_ids,
            fecha__range=(start, today),
        )

        by_day = (
            j_range.values("fecha")
            .annotate(
                presentes=Count("id", filter=Q(estado__codigo__in=["completo", "incompleto"])),
                tardanzas=Count("id", filter=Q(minutos_tardanza__gt=0)),
                minutos_trabajados=Sum("minutos_trabajados"),
                minutos_extra=Sum("minutos_extra"),
            )
            .order_by("fecha")
        )

        labels, presentes, tardanzas, horas, extra = [], [], [], [], []
        for row in by_day:
            labels.append(row["fecha"].strftime("%d-%b"))
            presentes.append(int(row.get("presentes") or 0))
            tardanzas.append(int(row.get("tardanzas") or 0))
            horas.append(round((row.get("minutos_trabajados") or 0) / 60.0, 2))
            extra.append(round((row.get("minutos_extra") or 0) / 60.0, 2))

        sem = (
            ResultadoKPI.objects.filter(
                empresa_id__in=empresa_ids,
                periodo=periodo,
            )
            .values("clasificacion__codigo")
            .annotate(c=Count("id"))
        )
        sem_map = {r["clasificacion__codigo"] or "": int(r["c"]) for r in sem}
        kpi_sem = {
            "verde": sem_map.get("verde", 0),
            "amarillo": sem_map.get("amarillo", 0),
            "rojo": sem_map.get("rojo", 0),
        }

        # Top empresas por tardanzas (hoy)
        top_emp = sorted(empresas_rows, key=lambda r: r.get("tardanzas", 0), reverse=True)[:8]
        bar_emp_labels = [r["empresa"][:24] for r in top_emp]
        bar_emp_tard = [r["tardanzas"] for r in top_emp]
        bar_emp_pres = [r["presentes"] for r in top_emp]

        charts = {
            "labels": labels,
            "presentes": presentes,
            "tardanzas": tardanzas,
            "horas": horas,
            "horas_extra": extra,
            "kpi_semaforo": kpi_sem,
            "periodo": periodo,
            "empresas_bar": {
                "labels": bar_emp_labels,
                "tardanzas": bar_emp_tard,
                "presentes": bar_emp_pres,
            },
        }

        # ------------------
        # Alertas
        # ------------------
        w_start = today - timedelta(days=6)
        tardy_rows = (
            JornadaCalculada.objects.filter(
                empresa_id__in=empresa_ids,
                fecha__range=(w_start, today),
                minutos_tardanza__gt=0,
            )
            .select_related("empleado", "empresa")
            .order_by("-minutos_tardanza")[:10]
        )
        top_tardanzas = [
            {
                "empresa": str(r.empresa),
                "empleado": r.empleado.nombre_completo,
                "fecha": r.fecha.strftime("%Y-%m-%d"),
                "min": int(r.minutos_tardanza or 0),
            }
            for r in tardy_rows
        ]

        abs_rows = (
            SolicitudAusencia.objects.filter(
                empresa_id__in=empresa_ids,
                estado__codigo="pendiente",
            )
            .select_related("empresa", "empleado", "tipo_ausencia")
            .order_by("fecha_inicio")[:10]
        )
        pendientes_rows = [
            {
                "empresa": str(r.empresa),
                "empleado": r.empleado.nombre_completo,
                "tipo": str(r.tipo_ausencia),
                "desde": r.fecha_inicio.strftime("%Y-%m-%d"),
                "hasta": r.fecha_fin.strftime("%Y-%m-%d"),
            }
            for r in abs_rows
        ]

        inc_rows = (
            j_today.filter(Q(estado__codigo="incompleto") | Q(hora_ultima_salida__isnull=True))
            .select_related("empresa", "empleado")
            .order_by("empresa__razon_social", "empleado__apellidos")[:10]
        )
        incompletas_rows = [
            {
                "empresa": str(r.empresa),
                "empleado": r.empleado.nombre_completo,
                "entrada": r.hora_primera_entrada.strftime("%H:%M") if r.hora_primera_entrada else "—",
                "salida": r.hora_ultima_salida.strftime("%H:%M") if r.hora_ultima_salida else "—",
            }
            for r in inc_rows
        ]

        kpi_rows = (
            ResultadoKPI.objects.filter(
                empresa_id__in=empresa_ids,
                periodo=periodo,
                clasificacion__codigo="rojo",
            )
            .select_related("empresa", "empleado", "kpi", "clasificacion")
            .order_by("-cumplimiento_pct")[:10]
        )
        kpis_rojo_rows = [
            {
                "empresa": str(r.empresa),
                "empleado": r.empleado.nombre_completo,
                "kpi": f"{r.kpi.codigo} - {r.kpi.nombre}",
                "pct": float(r.cumplimiento_pct) if r.cumplimiento_pct is not None else None,
            }
            for r in kpi_rows
        ]

        # Alertas de empresa (reglas rápidas para manager global)
        alertas_empresa = []
        for r in empresas_rows:
            if r["empleados"] >= 5 and r["tasa_presentismo"] < 70:
                alertas_empresa.append(
                    {
                        "nivel": "warning",
                        "titulo": "Presentismo bajo",
                        "detalle": f"{r['empresa']}: {r['tasa_presentismo']}% (hoy)",
                    }
                )
            if r["tardanzas"] >= 10:
                alertas_empresa.append(
                    {
                        "nivel": "danger",
                        "titulo": "Muchas tardanzas",
                        "detalle": f"{r['empresa']}: {r['tardanzas']} tardanzas (hoy)",
                    }
                )

        alerts = {
            "top_tardanzas": top_tardanzas,
            "pendientes_ausencia": pendientes_rows,
            "incompletas_hoy": incompletas_rows,
            "kpis_rojo": kpis_rojo_rows,
            "alertas_empresa": alertas_empresa[:8],
        }

        scope = {
            "label": str(empresa_obj) if empresa_obj else "Todas las empresas",
            "days": days,
            "today": today.strftime("%Y-%m-%d"),
            "empresa_id": str(empresa_obj.id) if empresa_obj else "",
            "empresas": [{"id": str(e.id), "nombre": str(e)} for e in Empresa.objects.all().order_by("razon_social")],
        }

        return {
            "scope": scope,
            "cards": cards,
            "charts": charts,
            "alerts": alerts,
            "empresas_rows": empresas_rows,
        }
