from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from ...mixins import TTLoginRequiredMixin, RoleRequiredMixin
from ...models import Geocerca, ReglaAsistencia, AsignacionTurno
from ...forms import GeocercaForm, ReglaAsistenciaForm, AsignacionTurnoForm

from ...utils import _apply_empresa_scope, _ctx_common_filters


# -----------------------------------------------------------------------------
# Configuración de asistencia (RRHH / SUPERADMIN)
# -----------------------------------------------------------------------------


class GeocercaList(TTLoginRequiredMixin, ListView):
    model = Geocerca
    template_name = "talenttrack/geocerca_list.html"
    context_object_name = "geocercas"

    def get_queryset(self):
        qs = Geocerca.objects.select_related("empresa").order_by("-creado_el", "nombre")
        return _apply_empresa_scope(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH") or self.request.user.has_role("SUPERADMIN")
        return ctx


class GeocercaCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = Geocerca
    form_class = GeocercaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_geocerca_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva Geocerca"
        return ctx


class GeocercaUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = Geocerca
    form_class = GeocercaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_geocerca_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Geocerca"
        return ctx


class GeocercaDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = Geocerca
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_geocerca_list")


class ReglaAsistenciaList(TTLoginRequiredMixin, ListView):
    model = ReglaAsistencia
    template_name = "talenttrack/regla_asistencia_list.html"
    context_object_name = "reglas"

    def get_queryset(self):
        qs = ReglaAsistencia.objects.select_related("empresa", "geocerca").order_by("-creado_el")
        return _apply_empresa_scope(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH") or self.request.user.has_role("SUPERADMIN")
        return ctx


class ReglaAsistenciaCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = ReglaAsistencia
    form_class = ReglaAsistenciaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_regla_asistencia_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva Regla de Asistencia"
        return ctx


class ReglaAsistenciaUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = ReglaAsistencia
    form_class = ReglaAsistenciaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_regla_asistencia_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Regla de Asistencia"
        return ctx


class ReglaAsistenciaDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = ReglaAsistencia
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_regla_asistencia_list")


class AsignacionTurnoList(TTLoginRequiredMixin, ListView):
    model = AsignacionTurno
    template_name = "talenttrack/asignacion_turno_list.html"
    context_object_name = "asignaciones"

    def get_queryset(self):
        qs = (
            AsignacionTurno.objects
            .select_related("empresa", "empleado", "turno")
            .order_by("-fecha_inicio")
        )
        return _apply_empresa_scope(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["can_create"] = self.request.user.has_role("ADMIN_RRHH") or self.request.user.has_role("SUPERADMIN")
        return ctx


class AsignacionTurnoCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = AsignacionTurno
    form_class = AsignacionTurnoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_asignacion_turno_list")

    def get_initial(self):
        """Permite prellenar desde la lista de empleados.

        Ej: /asignaciones/nueva/?empleado=<uuid>&empresa=<uuid>
        """
        initial = super().get_initial()
        empleado_id = self.request.GET.get("empleado")
        empresa_id = self.request.GET.get("empresa")
        if empleado_id:
            initial["empleado"] = empleado_id
        if empresa_id:
            initial["empresa"] = empresa_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva Asignación de Turno"
        return ctx


class AsignacionTurnoUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = AsignacionTurno
    form_class = AsignacionTurnoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_asignacion_turno_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Asignación de Turno"
        return ctx


class AsignacionTurnoDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH", "SUPERADMIN")
    model = AsignacionTurno
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_asignacion_turno_list")
