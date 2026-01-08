from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView, FormView
)

from ...mixins import TTLoginRequiredMixin, RoleRequiredMixin
from ...models import (
    Empresa, UnidadOrganizacional, Puesto, Turno,
    Empleado, EventoAsistencia, JornadaCalculada,
    TipoEventoAsistencia, FuenteMarcacion,
    AsignacionTurno, ReglaAsistencia, Geocerca,
    TipoAusencia, SolicitudAusencia, EstadoSolicitud,
    KPI, EvaluacionDesempeno, Usuario, Rol, UsuarioRol
)
from ...forms import (
    EmpresaForm, UnidadOrganizacionalForm, PuestoForm, TurnoForm,
    EmpleadoForm, EventoAsistenciaForm, TipoAusenciaForm, SolicitudAusenciaForm,
    KPIForm, UsuarioForm, UsuarioCreateWithRolForm, EmpleadoUsuarioAltaForm, RolForm, UsuarioRolForm
)

# shared helpers
from ...utils import *  # noqa: F401,F403

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

