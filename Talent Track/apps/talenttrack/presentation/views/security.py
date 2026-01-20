from django.db.models import Q

from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

from ...mixins import RoleRequiredMixin
from ...models import Usuario, Rol, UsuarioRol, Empleado, Empresa
from ...forms import UsuarioForm, UsuarioCreateWithRolForm, RolForm, UsuarioRolForm
from ...utils import *  # noqa

# -----------------------
# Seguridad (SUPERADMIN only)
# -----------------------
class UsuarioList(RoleRequiredMixin, ListView):
    required_roles = ("SUPERADMIN", "ADMIN_RRHH")
    model = Usuario
    template_name = "talenttrack/usuario_list.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        qs = Usuario.objects.select_related("empresa", "empleado")
        qs = _apply_empresa_scope(qs, self.request)
        return qs.order_by("email")



class UsuarioCreate(RoleRequiredMixin, CreateView):
    required_roles = ("SUPERADMIN", "ADMIN_RRHH")
    model = Usuario
    form_class = UsuarioCreateWithRolForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_usuario_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        empresa_id = self.request.POST.get("empresa") or self.request.GET.get("empresa")

        # ADMIN_RRHH: lock empresa to the user's empresa
        if self.request.user.has_role("ADMIN_RRHH") and not self.request.user.has_role("SUPERADMIN"):
            form.fields["empresa"].queryset = form.fields["empresa"].queryset.filter(id=self.request.user.empresa_id)
            form.fields["empresa"].initial = self.request.user.empresa_id
            form.fields["empresa"].disabled = True
            empresa_id = self.request.user.empresa_id
        if empresa_id:
            form.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")
            form.fields["rol"].queryset = Rol.objects.all().order_by("nombre")
        else:
            form.fields["empleado"].queryset = Empleado.objects.none()
            form.fields["rol"].queryset = Rol.objects.all().order_by("nombre")
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Usuario"
        ctx["enable_dependent_selects_usuario"] = True
        return ctx


class UsuarioUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("SUPERADMIN", "ADMIN_RRHH")
    model = Usuario
    form_class = UsuarioForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_usuario_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.has_role("ADMIN_RRHH") and not self.request.user.has_role("SUPERADMIN"):
            form.fields["empresa"].queryset = form.fields["empresa"].queryset.filter(id=self.request.user.empresa_id)
            form.fields["empresa"].disabled = True
            # Employee choices restricted to empresa
            form.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=self.request.user.empresa_id).order_by("apellidos", "nombres")
        return form

    def get_queryset(self):
        qs = Usuario.objects.select_related("empresa", "empleado")
        return _apply_empresa_scope(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Usuario"
        return ctx

class UsuarioDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("SUPERADMIN", "ADMIN_RRHH")
    model = Usuario
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_usuario_list")

    def get_queryset(self):
        qs = Usuario.objects.select_related("empresa", "empleado")
        return _apply_empresa_scope(qs, self.request)


class RolList(RoleRequiredMixin, ListView):
    required_roles = ("SUPERADMIN",)
    model = Rol
    template_name = "talenttrack/rol_list.html"
    context_object_name = "roles"

    def get_queryset(self):
        """Show human-friendly empresa instead of raw UUID (avoid exposing keys)."""
        qs = Rol.objects.all()
        # Resolve empresa names for roles scoped to a company (empresa_id is a UUID field, not FK)
        empresa_ids = [r.empresa_id for r in qs if r.empresa_id]
        empresas = Empresa.objects.in_bulk(empresa_ids) if empresa_ids else {}
        for r in qs:
            if not r.empresa_id:
                r.empresa_nombre = "Global"
            else:
                r.empresa_nombre = str(empresas.get(r.empresa_id)) if empresas.get(r.empresa_id) else "—"
        return qs

class RolCreate(RoleRequiredMixin, CreateView):
    required_roles = ("SUPERADMIN",)
    model = Rol
    form_class = RolForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_rol_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nuevo Rol"
        return ctx

class RolUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("SUPERADMIN",)
    model = Rol
    form_class = RolForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_rol_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Rol"
        return ctx

class RolDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("SUPERADMIN",)
    model = Rol
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_rol_list")


class UsuarioRolList(RoleRequiredMixin, ListView):
    required_roles = ("SUPERADMIN",)
    model = UsuarioRol
    template_name = "talenttrack/usuariorol_list.html"
    context_object_name = "asignaciones"

    def get_queryset(self):
        return UsuarioRol.objects.select_related("usuario", "rol").all()

class UsuarioRolCreate(RoleRequiredMixin, CreateView):
    required_roles = ("SUPERADMIN",)
    model = UsuarioRol
    form_class = UsuarioRolForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_usuariorol_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Asignar Rol a Usuario"
        return ctx

class UsuarioRolDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("SUPERADMIN",)
    model = UsuarioRol
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_usuariorol_list")

