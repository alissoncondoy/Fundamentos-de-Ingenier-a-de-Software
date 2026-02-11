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
    EmpresaForm,
    UnidadOrganizacionalForm,
    PuestoForm,
    TurnoForm,
    EmpleadoForm,
    EmpleadoSelfProfileForm,
    EventoAsistenciaForm,
    TipoAusenciaForm,
    SolicitudAusenciaForm,
    KPIForm,
    UsuarioForm,
    UsuarioCreateWithRolForm,
    EmpleadoUsuarioAltaForm,
    RolForm,
    UsuarioRolForm,
    TTPasswordChangeForm,
)

# shared helpers
from ...utils import *  # noqa: F401,F403

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.utils import timezone
from django.utils import timezone
from django.http import Http404

# -----------------------
# Empleados (RRHH CRUD; others read-only; Manager sees team; Empleado sees self)
# -----------------------
class EmpleadoList(TTLoginRequiredMixin, ListView):
    model = Empleado
    template_name = "talenttrack/empleado_list.html"
    context_object_name = "empleados"

    def dispatch(self, request, *args, **kwargs):
        """Si el usuario es solo EMPLEADO, no debe ver el listado completo."""
        if (
            request.user.has_role("EMPLEADO")
            and request.user.empleado_id
            and not (
                getattr(request.user, "is_superadmin", False)
                or request.user.has_role("SUPERADMIN")
                or request.user.has_role("ADMIN_RRHH")
                or request.user.has_role("MANAGER")
                or request.user.has_role("AUDITOR")
            )
        ):
            return redirect("tt_empleado_detail", pk=request.user.empleado_id)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Empleado.objects.select_related("empresa", "unidad", "puesto", "manager")
        # Company scope
        qs = _apply_empresa_scope(qs, self.request)
        # Role scope
        if self.request.user.has_role("MANAGER") and self.request.user.empleado_id:
            qs = qs.filter(manager_id=self.request.user.empleado_id)
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            qs = qs.filter(id=self.request.user.empleado_id)
        return qs.order_by("apellidos", "nombres")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))

        is_sa = getattr(self.request.user, "is_superadmin", False) or self.request.user.has_role("SUPERADMIN")
        can_manage = is_sa or self.request.user.has_role("ADMIN_RRHH")

        ctx["can_create"] = can_manage
        ctx["create_url"] = reverse_lazy("tt_empleado_usuario_alta") if can_manage else reverse_lazy("tt_empleado_create")
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = not can_manage
        ctx["can_export"] = _can_export(self.request.user, "empleados")

        # --- UI enrich: turno actual + controles (GPS/FOTO) + última marcación ---
        hoy = timezone.localdate()
        empleados = list(ctx.get("empleados") or [])
        emp_ids = [e.id for e in empleados]

        # Active turno assignment per employee (best-effort)
        asig_qs = (
            AsignacionTurno.objects
            .select_related("turno")
            .filter(empleado_id__in=emp_ids)
            .filter(fecha_inicio__lte=hoy)
            .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))
            .order_by("empleado_id", "-fecha_inicio")
        )

        asig_by_emp = {}
        for a in asig_qs:
            if a.empleado_id not in asig_by_emp:
                asig_by_emp[a.empleado_id] = a

        # Last attendance event per employee
        last_ev_by_emp = {}
        ev_qs = (
            EventoAsistencia.objects
            .filter(empleado_id__in=emp_ids)
            .only("id", "empleado_id", "registrado_el", "tipo", "gps_lat", "gps_lng", "foto_url", "dentro_geocerca")
            .order_by("empleado_id", "-registrado_el")
        )
        for ev in ev_qs:
            if ev.empleado_id not in last_ev_by_emp:
                last_ev_by_emp[ev.empleado_id] = ev

        # Map tipo UUID -> code (Entrada/Salida)
        tipo_map = {t.id: (t.codigo or "") for t in TipoEventoAsistencia.objects.all()}

        for e in empleados:
            a = asig_by_emp.get(e.id)
            turno = getattr(a, "turno", None) if a else None
            last_ev = last_ev_by_emp.get(e.id)

            # attach attributes to the instance for template usage
            e.tt_asignacion_turno = a
            e.tt_turno = turno
            e.tt_turno_horario = ""
            if turno and turno.hora_inicio and turno.hora_fin:
                e.tt_turno_horario = f"{turno.hora_inicio.strftime('%H:%M')}–{turno.hora_fin.strftime('%H:%M')}"

            e.tt_requires_gps = bool(getattr(turno, "requiere_gps", False)) if turno else False
            e.tt_requires_foto = bool(getattr(turno, "requiere_foto", False)) if turno else False

            e.tt_last_event = last_ev
            e.tt_last_event_label = ""
            if last_ev:
                code = (tipo_map.get(last_ev.tipo) or "").lower()
                if code == "check_in":
                    e.tt_last_event_label = "Entrada"
                elif code == "check_out":
                    e.tt_last_event_label = "Salida"
                else:
                    e.tt_last_event_label = "Marcación"

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

    def get_context_data(self, **kwargs):
        """Extiende el contexto con el usuario asociado y turno vigente.

        Importante: Empleado no tiene atributo `user`. La relación Usuario→Empleado
        existe en seguridad.usuario.empleado_id.
        """
        ctx = super().get_context_data(**kwargs)
        empleado = ctx.get("empleado")
        if not empleado:
            return ctx

        # Usuario asociado (si existe)
        usuario = Usuario.objects.filter(empleado_id=empleado.id).first()
        ctx["usuario_account"] = usuario

        if usuario:
            roles_qs = UsuarioRol.objects.select_related("rol").filter(usuario_id=usuario.id)
            ctx["usuario_roles"] = [ur.rol.nombre for ur in roles_qs]
        else:
            ctx["usuario_roles"] = []

        # Turno actual: asignación activa dentro del rango de fechas
        hoy = timezone.localdate()
        asign = (
            AsignacionTurno.objects.select_related("turno")
            .filter(empleado_id=empleado.id)
            .filter(fecha_inicio__lte=hoy)
            .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))
            .order_by("-fecha_inicio")
            .first()
        )
        ctx["turno_actual"] = asign.turno if asign else None
        ctx["asignacion_turno"] = asign
        return ctx


# -----------------------
# Mi perfil (self-service)
# -----------------------

class MiPerfil(TTLoginRequiredMixin, DetailView):
    """Perfil del usuario logueado.

    Permite ver el perfil completo y, para el rol EMPLEADO, editar
    únicamente: dirección y foto. La contraseña se cambia en una vista aparte.
    """

    model = Empleado
    template_name = "talenttrack/profile_detail.html"
    context_object_name = "empleado"

    def get_object(self, queryset=None):
        if not self.request.user.empleado_id:
            raise Http404("El usuario no tiene un empleado asociado.")
        qs = Empleado.objects.select_related("empresa", "unidad", "puesto", "manager")
        qs = _apply_empresa_scope(qs, self.request)
        return qs.get(id=self.request.user.empleado_id)


class MiPerfilEdit(TTLoginRequiredMixin, UpdateView):
    """Edición limitada del perfil para el propio empleado."""

    model = Empleado
    form_class = EmpleadoSelfProfileForm
    template_name = "talenttrack/profile_edit.html"
    success_url = reverse_lazy("tt_profile")

    def get_object(self, queryset=None):
        if not self.request.user.empleado_id:
            raise Http404("El usuario no tiene un empleado asociado.")
        qs = Empleado.objects.select_related("empresa")
        qs = _apply_empresa_scope(qs, self.request)
        return qs.get(id=self.request.user.empleado_id)

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Perfil actualizado.")
        return resp

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # TTModelForm expects user
        kwargs["user"] = self.request.user
        return kwargs


class MiPerfilPassword(TTLoginRequiredMixin, FormView):
    """Cambio de contraseña para el usuario logueado."""

    form_class = TTPasswordChangeForm
    template_name = "talenttrack/profile_password.html"
    success_url = reverse_lazy("tt_profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tt_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Contraseña actualizada.")
        return super().form_valid(form)

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


