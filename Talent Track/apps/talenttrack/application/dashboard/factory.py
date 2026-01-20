from __future__ import annotations

from dataclasses import dataclass

from .facade import (
    AuditorDashboardFacade,
    EmployeeDashboardFacade,
    ManagerDashboardFacade,
    RRHHDashboardFacade,
    SuperAdminDashboardFacade,
)


@dataclass(frozen=True)
class DashboardResult:
    template: str
    payload: dict


class DashboardFactory:
    """Selecciona el dashboard según rol (Factory Method)."""

    @staticmethod
    def build_for(user, days: int = 14, empresa_id: str | None = None) -> DashboardResult:
        if getattr(user, "is_superadmin", False) or user.has_role("SUPERADMIN"):
            payload = SuperAdminDashboardFacade().build(user, days=days, empresa_id=empresa_id)
            return DashboardResult(template="talenttrack/dashboard_superadmin.html", payload=payload)

        if user.has_role("MANAGER"):
            payload = ManagerDashboardFacade().build(user, days=days)
            return DashboardResult(template="talenttrack/dashboard_manager.html", payload=payload)

        if user.has_role("ADMIN_RRHH"):
            payload = RRHHDashboardFacade().build(user, days=days)
            return DashboardResult(template="talenttrack/dashboard_rrhh.html", payload=payload)

        if user.has_role("AUDITOR"):
            payload = AuditorDashboardFacade().build(user, days=days)
            return DashboardResult(template="talenttrack/dashboard_auditor.html", payload=payload)

        if user.has_role("EMPLEADO"):
            payload = EmployeeDashboardFacade().build(user, days=days)
            return DashboardResult(template="talenttrack/dashboard_empleado.html", payload=payload)

        # Fallback para otros roles (mantiene el dashboard actual)
        return DashboardResult(
            template="talenttrack/dashboard.html",
            payload={"scope": {}, "cards": {}, "charts": {}, "alerts": {}},
        )
