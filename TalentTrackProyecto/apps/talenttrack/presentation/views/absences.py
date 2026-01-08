from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView

from ...mixins import TTLoginRequiredMixin
from ...models import SolicitudAusencia, Empleado, Empresa
from ...forms import SolicitudAusenciaForm
from ...utils import *  # noqa

# -----------------------
# Ausencias (Empleado solicita; RRHH gestiona en su empresa; Auditor exporta)
# -----------------------
class AusenciaList(TTLoginRequiredMixin, ListView):
    model = SolicitudAusencia
    template_name = "talenttrack/ausencia_list.html"
    context_object_name = "solicitudes"

    def _scoped_queryset(self):
        """Query base: aplica scope por empresa/rol, filtros por fecha/empresa y búsqueda.

        Nota: NO aplica filtro por estado; eso se aplica en get_queryset().
        """
        qs = SolicitudAusencia.objects.select_related("empresa", "empleado", "tipo_ausencia", "estado")
        qs = _apply_empresa_scope(qs, self.request)

        # --- filtros ---
        desde = _parse_date(self.request.GET.get("desde"))
        hasta = _parse_date(self.request.GET.get("hasta"))
        q = (self.request.GET.get("q") or "").strip()

        # date range over fecha_inicio/fecha_fin (overlap)
        if desde:
            qs = qs.filter(fecha_fin__gte=desde)
        if hasta:
            qs = qs.filter(fecha_inicio__lte=hasta)

        if q:
            qs = qs.filter(
                Q(empleado__nombres__icontains=q)
                | Q(empleado__apellidos__icontains=q)
                | Q(empleado__email__icontains=q)
                | Q(tipo_ausencia__nombre__icontains=q)
            )

        # --- scope por rol ---
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            qs = qs.filter(empleado_id=self.request.user.empleado_id)
        if self.request.user.has_role("MANAGER") and self.request.user.empleado_id:
            team_ids = Empleado.objects.filter(manager_id=self.request.user.empleado_id).values_list("id", flat=True)
            qs = qs.filter(empleado_id__in=list(team_ids))
        return qs

    def get_queryset(self):
        qs = self._scoped_queryset()

        estado = (self.request.GET.get("estado") or "").strip().lower()
        if estado:
            qs = qs.filter(estado__codigo__iexact=estado)

        return qs.order_by("-creada_el")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_common_filters(self.request))

        # --- bandeja / tabs por estado ---
        qs_base = self._scoped_queryset()
        counts = {
            "pendiente": qs_base.filter(estado__codigo__iexact="pendiente").count(),
            "aprobado": qs_base.filter(estado__codigo__iexact="aprobado").count(),
            "rechazado": qs_base.filter(estado__codigo__iexact="rechazado").count(),
            "cancelado": qs_base.filter(estado__codigo__iexact="cancelado").count(),
            "total": qs_base.count(),
        }

        estado_filter = (self.request.GET.get("estado") or "").strip().lower()
        ctx["estado_filter"] = estado_filter
        ctx["q"] = (self.request.GET.get("q") or "").strip()

        ctx["estado_tabs"] = [
            {"code": "", "label": "Todas", "count": counts["total"], "active": estado_filter == ""},
            {"code": "pendiente", "label": "Pendientes", "count": counts["pendiente"], "active": estado_filter == "pendiente"},
            {"code": "aprobado", "label": "Aprobadas", "count": counts["aprobado"], "active": estado_filter == "aprobado"},
            {"code": "rechazado", "label": "Rechazadas", "count": counts["rechazado"], "active": estado_filter == "rechazado"},
            {"code": "cancelado", "label": "Canceladas", "count": counts["cancelado"], "active": estado_filter == "cancelado"},
        ]

                # Crear solicitud: solo EMPLEADO (propia). Superadmin/RRHH gestionan pero no solicitan.
        ctx["can_create"] = bool(self.request.user.empleado_id) and self.request.user.has_role("EMPLEADO")

        ctx["can_decide"] = self.request.user.has_role("MANAGER") or self.request.user.has_role("ADMIN_RRHH") or self.request.user.is_superadmin
        ctx["can_mark"] = bool(self.request.user.empleado_id)
        ctx["readonly"] = False
        ctx["can_export"] = _can_export(self.request.user, "ausencias")
        return ctx

class AusenciaCreate(TTLoginRequiredMixin, CreateView):
    model = SolicitudAusencia
    form_class = SolicitudAusenciaForm
    template_name = "talenttrack/form.html"
    success_url = reverse_lazy("tt_ausencia_list")

    def dispatch(self, request, *args, **kwargs):
        # Permisos: EMPLEADO (su propia solicitud), MANAGER (solo para gestionar), RRHH y SUPERADMIN.
        if request.user.has_role("EMPLEADO"):
            if not request.user.empleado_id:
                messages.warning(request, "Tu usuario no tiene empleado asociado. Pide a RRHH que lo configure.")
                return redirect("tt_ausencia_list")
            return super().dispatch(request, *args, **kwargs)
        if request.user.is_superadmin:
            return _forbid()
        if request.user.has_role("ADMIN_RRHH"):
            return super().dispatch(request, *args, **kwargs)
        return _forbid()

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            form.fields["empresa"].queryset = Empresa.objects.filter(id=self.request.user.empresa_id)
            form.fields["empleado"].queryset = Empleado.objects.filter(id=self.request.user.empleado_id)
            form.fields["empresa"].initial = self.request.user.empresa_id
            form.fields["empleado"].initial = self.request.user.empleado_id
        return form

    def form_valid(self, form):
        if self.request.user.has_role("EMPLEADO") and self.request.user.empleado_id:
            form.instance.empresa_id = self.request.user.empresa_id
            form.instance.empleado_id = self.request.user.empleado_id
        # Estado inicial: pendiente
        if not getattr(form.instance, "estado_id", None):
            pend_id = _estado_solicitud_id("pendiente")
            if pend_id:
                form.instance.estado_id = pend_id
        form.instance.creada_el = timezone.now()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Nueva Solicitud de Ausencia"
        return ctx

class AusenciaCancel(TTLoginRequiredMixin, View):
    """Cancela una solicitud cambiando su estado a 'cancelado' (NO elimina)."""

    def post(self, request, pk):
        try:
            obj = SolicitudAusencia.objects.select_related("estado").get(pk=pk)
        except SolicitudAusencia.DoesNotExist:
            messages.error(request, "La solicitud no existe.")
            return redirect("tt_ausencia_list")

        # Permisos: RRHH (su empresa) o EMPLEADO (propia)
        if request.user.has_role("ADMIN_RRHH"):
            if (not request.user.is_superadmin) and str(obj.empresa_id) != str(request.user.empresa_id):
                return _forbid()
        elif request.user.has_role("EMPLEADO") and request.user.empleado_id:
            if str(obj.empleado_id) != str(request.user.empleado_id):
                return _forbid()
        else:
            return _forbid()

        # Regla de negocio: solo se puede cancelar si está pendiente
        if obj.estado and obj.estado.codigo != "pendiente":
            messages.error(request, "Solo puedes cancelar solicitudes en estado Pendiente.")
            return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")

        cancel_id = _estado_solicitud_id("cancelado")
        if not cancel_id:
            messages.error(request, "No existe el estado 'cancelado' en config.estado_solicitud.")
            return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")

        obj.estado_id = cancel_id
        obj.save(update_fields=["estado"])
        messages.success(request, "Solicitud cancelada.")
        return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")



class AusenciaApprove(TTLoginRequiredMixin, View):
    """Aprueba una solicitud pendiente (MANAGER / RRHH / SUPERADMIN)."""

    def post(self, request, pk):
        try:
            obj = SolicitudAusencia.objects.select_related("estado").get(pk=pk)
        except SolicitudAusencia.DoesNotExist:
            messages.error(request, "La solicitud no existe.")
            return redirect("tt_ausencia_list")

        if request.user.has_role("ADMIN_RRHH"):
            if (not request.user.is_superadmin) and str(obj.empresa_id) != str(request.user.empresa_id):
                return _forbid()
        elif request.user.has_role("MANAGER") and request.user.empleado_id:
            # Solo su equipo
            team_ids = set(Empleado.objects.filter(manager_id=request.user.empleado_id).values_list("id", flat=True))
            if obj.empleado_id not in team_ids:
                return _forbid()
        elif request.user.is_superadmin:
            pass
        else:
            return _forbid()

        if obj.estado and obj.estado.codigo != "pendiente":
            messages.error(request, "Solo puedes aprobar solicitudes en estado Pendiente.")
            return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")

        aprob_id = _estado_solicitud_id("aprobado")
        if not aprob_id:
            messages.error(request, "No existe el estado 'aprobado' en config.estado_solicitud.")
            return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")

        obj.estado_id = aprob_id
        obj.save(update_fields=["estado"])
        messages.success(request, "Solicitud aprobada.")
        return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")


class AusenciaReject(TTLoginRequiredMixin, View):
    """Rechaza una solicitud pendiente (MANAGER / RRHH / SUPERADMIN)."""

    def post(self, request, pk):
        try:
            obj = SolicitudAusencia.objects.select_related("estado").get(pk=pk)
        except SolicitudAusencia.DoesNotExist:
            messages.error(request, "La solicitud no existe.")
            return redirect("tt_ausencia_list")

        if request.user.has_role("ADMIN_RRHH"):
            if (not request.user.is_superadmin) and str(obj.empresa_id) != str(request.user.empresa_id):
                return _forbid()
        elif request.user.has_role("MANAGER") and request.user.empleado_id:
            team_ids = set(Empleado.objects.filter(manager_id=request.user.empleado_id).values_list("id", flat=True))
            if obj.empleado_id not in team_ids:
                return _forbid()
        elif request.user.is_superadmin:
            pass
        else:
            return _forbid()

        if obj.estado and obj.estado.codigo != "pendiente":
            messages.error(request, "Solo puedes rechazar solicitudes en estado Pendiente.")
            return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")

        rech_id = _estado_solicitud_id("rechazado")
        if not rech_id:
            messages.error(request, "No existe el estado 'rechazado' en config.estado_solicitud.")
            return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")

        obj.estado_id = rech_id
        obj.save(update_fields=["estado"])
        messages.success(request, "Solicitud rechazada.")
        return redirect(request.META.get("HTTP_REFERER") or "tt_ausencia_list")
