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

from django.contrib import messages
from django.db.models import Q

# -----------------------
# Empleados (RRHH CRUD; others read-only; Manager sees team; Empleado sees self)
# -----------------------
class EmpleadoList(TTLoginRequiredMixin, ListView):
    model = Empleado
    template_name = "talenttrack/empleado_list.html"
    context_object_name = "empleados"

    def get_queryset(self):
        qs = Empleado.objects.select_related("empresa", "unidad", "puesto", "manager")
        # Company scope
        qs = _apply_empresa_scope(qs, self.request)
        # Role scope
        if self.request.user.has_role("MANAGER") and self.request.user.empleado_id:
            # team = direct reports
            qs = qs.filter(manager_id=self.request.user.empleado_id)
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            qs = qs.filter(id=self.request.user.empleado_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        is_sa = getattr(self.request.user, "is_superadmin", False) or self.request.user.has_role("SUPERADMIN")
        ctx["can_create"] = is_sa or self.request.user.has_role("ADMIN_RRHH")
        ctx["create_url"] = reverse_lazy("tt_empleado_usuario_alta") if (is_sa or self.request.user.has_role("ADMIN_RRHH")) else reverse_lazy("tt_empleado_create")
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = not ctx["can_create"]
        ctx["can_export"] = _can_export(self.request.user, "empleados")
        return ctx




class EmpleadoUsuarioAltaCreate(RoleRequiredMixin, FormView):
    """SUPERADMIN: alta de Empleado + Usuario + Rol en un solo paso.

    - La empresa se elige primero.
    - Unidad/Puesto/Manager/Rol se filtran por empresa (AJAX + server-side).
    - Se crea todo en una sola transacción (ver forms.EmpleadoUsuarioAltaForm.save()).
    """

    required_roles = ("SUPERADMIN", "ADMIN_RRHH")
    form_class = EmpleadoUsuarioAltaForm
    template_name = "talenttrack/onboarding_empleado_usuario.html"
    success_url = reverse_lazy("tt_usuario_list")

    def get_initial(self):
        initial = super().get_initial()
        # ADMIN_RRHH works within their empresa
        if self.request.user.has_role("ADMIN_RRHH") and not self.request.user.has_role("SUPERADMIN"):
            initial["empresa"] = self.request.user.empresa_id
            return initial

        empresa_id = self.request.GET.get("empresa")
        if empresa_id:
            initial["empresa"] = empresa_id
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        empresa_id = self.request.POST.get("empresa") or self.request.GET.get("empresa")
        # ADMIN_RRHH: lock empresa to the user's empresa
        if self.request.user.has_role("ADMIN_RRHH") and not self.request.user.has_role("SUPERADMIN"):
            form.fields["empresa"].queryset = Empresa.objects.filter(id=self.request.user.empresa_id)
            form.fields["empresa"].initial = self.request.user.empresa_id
            form.fields["empresa"].disabled = True
            empresa_id = self.request.user.empresa_id
        else:
            # Siempre mostramos empresas ordenadas
            form.fields["empresa"].queryset = Empresa.objects.all().order_by("razon_social")


        if empresa_id:
            form.fields["unidad"].queryset = UnidadOrganizacional.objects.filter(empresa_id=empresa_id).order_by("nombre")
            form.fields["puesto"].queryset = Puesto.objects.filter(empresa_id=empresa_id).order_by("nombre")
            form.fields["manager"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")
            # Roles globales (empresa_id NULL) + roles por empresa
            form.fields["rol"].queryset = Rol.objects.all().order_by("nombre")
        else:
            # Si aún no hay empresa, dejamos combos vacíos para forzar la selección primero (más pro)
            form.fields["unidad"].queryset = UnidadOrganizacional.objects.none()
            form.fields["puesto"].queryset = Puesto.objects.none()
            form.fields["manager"].queryset = Empleado.objects.none()
            form.fields["rol"].queryset = Rol.objects.all().order_by("nombre")

        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))
        ctx["title"] = "Alta de empleado + usuario"
        ctx["subtitle"] = "Crea el empleado, su usuario y el rol (obligatorio) en un solo formulario."
        ctx["enable_dependent_selects"] = True
        ctx["lock_empresa"] = self.request.user.has_role("ADMIN_RRHH") and not self.request.user.has_role("SUPERADMIN")
        return ctx

    def form_valid(self, form):
        from django import forms as dj_forms
        try:
            empleado, usuario = form.save()
        except dj_forms.ValidationError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except Exception as exc:
            form.add_error(None, "No se pudo completar el alta. " + str(exc))
            return self.form_invalid(form)

        messages.success(self.request, f"Alta realizada: {empleado} / {usuario.email}")
        return super().form_valid(form)


class EmpleadoDetail(TTLoginRequiredMixin, DetailView):
    model = Empleado
    template_name = "talenttrack/empleado_detail.html"
    context_object_name = "empleado"

    def get_queryset(self):
        qs = Empleado.objects.select_related("empresa", "unidad", "puesto", "manager")
        qs = _apply_empresa_scope(qs, self.request)
        # employee can only view self
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            qs = qs.filter(id=self.request.user.empleado_id)
        # manager can view team + self
        if self.request.user.has_role("MANAGER") and self.request.user.empleado_id:
            qs = qs.filter(id__in=Empleado.objects.filter(manager_id=self.request.user.empleado_id).values("id")) | qs.filter(id=self.request.user.empleado_id)
        return qs

class EmpleadoCreate(RoleRequiredMixin, CreateView):
    required_roles = ("ADMIN_RRHH",)
    model = Empleado
    form_class = EmpleadoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_empleado_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Empleado"
        return ctx

class EmpleadoUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("ADMIN_RRHH",)
    model = Empleado
    form_class = EmpleadoForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_empleado_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Empleado"
        return ctx

class EmpleadoDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("ADMIN_RRHH",)
    model = Empleado
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_empleado_list")


