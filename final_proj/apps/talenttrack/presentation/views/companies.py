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
# Empresas (SUPERADMIN only)
# -----------------------
class EmpresaList(RoleRequiredMixin, ListView):
    required_roles = ("SUPERADMIN",)
    model = Empresa
    template_name = "talenttrack/empresa_list.html"
    context_object_name = "empresas"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cards = []
        for e in ctx.get("empresas", []):
            empleados = Empleado.objects.filter(empresa_id=e.id).count()
            turnos = Turno.objects.filter(empresa_id=e.id).count()
            regla = ReglaAsistencia.objects.filter(empresa_id=e.id).first()
            has_geocerca = bool(regla and getattr(regla, "geocerca_id", None))
            cards.append({
                "empresa": e,
                "empleados": empleados,
                "turnos": turnos,
                "has_geocerca": has_geocerca,
            })
        ctx["cards"] = cards
        ctx["title"] = "Empresas"
        return ctx

class EmpresaCreate(RoleRequiredMixin, CreateView):
    required_roles = ("SUPERADMIN",)
    model = Empresa
    form_class = EmpresaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_empresa_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva Empresa"
        return ctx

class EmpresaUpdate(RoleRequiredMixin, UpdateView):
    required_roles = ("SUPERADMIN",)
    model = Empresa
    form_class = EmpresaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_empresa_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Editar Empresa"
        return ctx

class EmpresaDelete(RoleRequiredMixin, DeleteView):
    required_roles = ("SUPERADMIN",)
    model = Empresa
    template_name = "talenttrack/confirm_delete.html"
    success_url = reverse_lazy("tt_empresa_list")

