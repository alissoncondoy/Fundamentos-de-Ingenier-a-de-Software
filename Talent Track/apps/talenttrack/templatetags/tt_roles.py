from __future__ import annotations

from django import template

register = template.Library()


def _roles_of(user):
    roles = getattr(user, "roles", None)
    if roles is None:
        return []
    # roles may come as list/tuple/set or a comma-separated string
    if isinstance(roles, str):
        return [r.strip() for r in roles.split(",") if r.strip()]
    try:
        return list(roles)
    except TypeError:
        return []


@register.filter
def has_role(user, role_name: str) -> bool:
    """True if the current request user has the given role."""
    return role_name in _roles_of(user)


@register.filter
def has_any_role(user, role_names: str) -> bool:
    """True if the user has ANY role from a comma-separated list."""
    wanted = [r.strip() for r in (role_names or "").split(",") if r.strip()]
    roles = set(_roles_of(user))
    return any(r in roles for r in wanted)


@register.filter
def is_employee_only(user) -> bool:
    """True if user is only EMPLEADO (not superadmin and no other elevated roles)."""
    roles = set(_roles_of(user))
    if getattr(user, "is_superadmin", False):
        return False
    if "EMPLEADO" not in roles:
        return False
    elevated = {"ADMIN_RRHH", "MANAGER", "AUDITOR"}
    return roles.isdisjoint(elevated)


@register.filter
def url_in(url_name: str, csv_names: str) -> bool:
    """True si el url_name está dentro de una lista separada por coma."""
    if not url_name:
        return False
    wanted = [x.strip() for x in (csv_names or "").split(",") if x.strip()]
    return url_name in wanted
