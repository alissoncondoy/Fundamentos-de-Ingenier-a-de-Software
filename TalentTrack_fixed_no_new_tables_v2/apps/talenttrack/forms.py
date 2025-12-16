import json
from django import forms
from .models import (
    Empresa, UnidadOrganizacional, Puesto, Turno,
    Empleado, EventoAsistencia, TipoAusencia, SolicitudAusencia,
    KPI, Usuario, Rol, UsuarioRol
)


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ["razon_social", "nombre_comercial", "ruc_nit", "pais", "moneda", "logo_url"]


class UnidadOrganizacionalForm(forms.ModelForm):
    class Meta:
        model = UnidadOrganizacional
        fields = ["empresa", "nombre", "padre", "ubicacion"]


class PuestoForm(forms.ModelForm):
    class Meta:
        model = Puesto
        fields = ["empresa", "nombre", "descripcion", "unidad", "nivel", "salario_referencial"]


class TurnoForm(forms.ModelForm):
    dias_semana = forms.CharField(
        required=False,
        help_text="JSON tipo lista. Ejemplo: [1,2,3,4,5] (1=Lun, 7=Dom).",
        widget=forms.TextInput(attrs={"placeholder": "[1,2,3,4,5]"})
    )

    class Meta:
        model = Turno
        fields = ["empresa", "nombre", "hora_inicio", "hora_fin", "dias_semana",
                  "tolerancia_minutos", "requiere_gps", "requiere_foto"]

        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean_dias_semana(self):
        raw = self.cleaned_data.get("dias_semana")
        if raw in (None, "", []):
            return None
        try:
            val = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            raise forms.ValidationError("Formato inválido. Usa JSON, ejemplo: [1,2,3,4,5].")
        if not isinstance(val, list) or any((not isinstance(x, int)) for x in val):
            raise forms.ValidationError("Debe ser una lista de enteros. Ejemplo: [1,2,3,4,5].")
        for x in val:
            if x < 1 or x > 7:
                raise forms.ValidationError("Los días deben estar entre 1 y 7.")
        return val

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show JSON list as string
        if self.instance and self.instance.dias_semana is not None and "dias_semana" in self.fields:
            self.fields["dias_semana"].initial = json.dumps(self.instance.dias_semana)


class EmpleadoForm(forms.ModelForm):
    class Meta:
        model = Empleado
        fields = [
            "empresa", "nombres", "apellidos", "documento", "email", "telefono",
            "direccion", "fecha_nacimiento", "fecha_ingreso", "unidad", "puesto", "manager", "foto_url"
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "fecha_ingreso": forms.DateInput(attrs={"type": "date"}),
        }


class EventoAsistenciaForm(forms.ModelForm):
    class Meta:
        model = EventoAsistencia
        fields = ["empresa", "empleado", "tipo", "fuente", "gps_lat", "gps_lng", "foto_url", "observacion"]


class TipoAusenciaForm(forms.ModelForm):
    class Meta:
        model = TipoAusencia
        fields = ["empresa", "nombre", "afecta_sueldo", "requiere_soporte", "descripcion"]


class SolicitudAusenciaForm(forms.ModelForm):
    class Meta:
        model = SolicitudAusencia
        fields = ["empresa", "empleado", "tipo_ausencia", "fecha_inicio", "fecha_fin", "motivo", "adjunto_url"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }


class KPIForm(forms.ModelForm):
    class Meta:
        model = KPI
        fields = ["empresa", "codigo", "nombre", "descripcion", "origen_datos", "formula", "activo"]


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput(), help_text="Opcional: establece/actualiza contraseña.")

    class Meta:
        model = Usuario
        fields = ["empresa", "email", "phone", "empleado", "mfa_habilitado"]

    def save(self, commit=True):
        from .tt_security import make_password_if_needed
        user = super().save(commit=False)
        pw = self.cleaned_data.get("password")
        if pw:
            user.hash_password = make_password_if_needed(pw)
        if commit:
            user.save()
        return user


class RolForm(forms.ModelForm):
    class Meta:
        model = Rol
        fields = ["empresa_id", "nombre", "descripcion"]


class UsuarioRolForm(forms.ModelForm):
    class Meta:
        model = UsuarioRol
        fields = ["usuario", "rol"]
