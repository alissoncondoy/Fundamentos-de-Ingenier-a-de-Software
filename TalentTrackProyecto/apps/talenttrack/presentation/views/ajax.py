from django.db.models import Q
from django.views import View

from ...mixins import RoleRequiredMixin
from ...models import UnidadOrganizacional, Puesto, Empleado, Rol
from ...utils import *  # noqa

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
