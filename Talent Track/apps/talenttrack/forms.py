from __future__ import annotations

import json
import os
import uuid

from django import forms
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q

from .tt_security import make_password_if_needed

from .models import (
    Empresa,
    UnidadOrganizacional,
    Puesto,
    Turno,
    Empleado,
    Contrato,
    DocumentoEmpleado,
    EventoAsistencia,
    Geocerca,
    ReglaAsistencia,
    AsignacionTurno,
    TipoAusencia,
    SolicitudAusencia,
    KPI,
    UnidadKPI,
    Usuario,
    Rol,
    UsuarioRol,
    EstadoGenerico,
    EstadoEmpleado,
    TipoContrato,
    TipoUnidad,
    TipoTurno,
)


# -----------------------------------------------------------------------------
# Helpers de estilos / archivos / alcance por empresa
# -----------------------------------------------------------------------------


def _is_sa(user) -> bool:
    return bool(getattr(user, "is_superadmin", False) or (hasattr(user, "has_role") and user.has_role("SUPERADMIN")))


def _add_css_class(widget, class_name: str) -> None:
    current = widget.attrs.get("class", "")
    if class_name not in current.split():
        widget.attrs["class"] = (current + " " + class_name).strip()


def _style_form(form: forms.BaseForm) -> None:
    """Aplica clases Bootstrap de forma consistente (sin depender de JS)."""

    for name, field in form.fields.items():
        widget = field.widget

        # No tocamos widgets hidden
        if isinstance(widget, forms.HiddenInput):
            continue

        if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            _add_css_class(widget, "form-check-input")
            continue

        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            _add_css_class(widget, "form-select")
        else:
            _add_css_class(widget, "form-control")


def _save_upload(*, upload, prefix: str) -> str:
    """Guarda un archivo en MEDIA_ROOT y devuelve la URL pública (/media/...)."""

    if not upload:
        return ""

    _, ext = os.path.splitext(upload.name)
    ext = (ext or "").lower()
    fname = f"{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join("uploads", prefix, fname).replace("\\", "/")
    saved = default_storage.save(rel_path, upload)
    return f"{settings.MEDIA_URL}{saved}"  # ej: /media/uploads/...


class TTBaseForm(forms.Form):
    """Form base (no ModelForm) con:
    - soporte de user en kwargs
    - estilos consistentes

    Se usa para formularios compuestos que crean/actualizan múltiples modelos
    (por ejemplo, crear Usuario + asignar Rol).
    """

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        _style_form(self)


class TTModelForm(forms.ModelForm):
    """ModelForm base con:
    - soporte de user en kwargs
    - estilos consistentes
    - utilidades para bloquear empresa/empleado
    """

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        _style_form(self)

    def _lock_field(self, field_name: str, value):
        """Deja el campo no editable (hidden) y fija su valor."""
        if field_name in self.fields:
            self.fields[field_name].initial = value
            self.fields[field_name].disabled = True
            # Para evitar que Choices/Select no permitan disabled con valor vacío
            self.fields[field_name].widget = forms.HiddenInput()

    def _scope_empresa_field(self, *, field_name: str = "empresa"):
        """Si no es SUPERADMIN, oculta empresa y la fija a request.user.empresa_id."""
        if not self.user or _is_sa(self.user):
            return

        empresa_id = getattr(self.user, "empresa_id", None)
        if empresa_id:
            self._lock_field(field_name, empresa_id)


# -----------------------------------------------------------------------------
# Empresas / Organización
# -----------------------------------------------------------------------------


class EmpresaForm(TTModelForm):
    logo_archivo = forms.FileField(
        required=False,
        label="Logo (archivo)",
        help_text="PNG/JPG recomendado. Si subes un archivo, se reemplaza el logo actual.",
    )

    estado = forms.ModelChoiceField(
        queryset=EstadoGenerico.objects.all().order_by("codigo"),
        required=False,
        label="Estado",
    )

    class Meta:
        model = Empresa
        fields = [
            "razon_social",
            "nombre_comercial",
            "ruc_nit",
            "pais",
            "moneda",
            "estado",
            "logo_archivo",
        ]

        labels = {
            "razon_social": "Razón social",
            "nombre_comercial": "Nombre comercial",
            "ruc_nit": "RUC/NIT",
            "pais": "País",
            "moneda": "Moneda",
        }

    def clean_estado(self):
        obj = self.cleaned_data.get("estado")
        return obj.id if obj else None

    def save(self, commit=True):
        instance: Empresa = super().save(commit=False)

        upload = self.cleaned_data.get("logo_archivo")
        if upload:
            instance.logo_url = _save_upload(upload=upload, prefix=f"empresa/{instance.id or 'nuevo'}")

        if commit:
            instance.save()
        return instance


class UnidadOrganizacionalForm(TTModelForm):
    tipo = forms.ModelChoiceField(
        queryset=TipoUnidad.objects.all().order_by("codigo"),
        required=False,
        label="Tipo de unidad",
    )
    estado = forms.ModelChoiceField(
        queryset=EstadoGenerico.objects.all().order_by("codigo"),
        required=False,
        label="Estado",
    )

    class Meta:
        model = UnidadOrganizacional
        fields = ["empresa", "nombre", "tipo", "padre", "ubicacion", "estado"]
        labels = {
            "empresa": "Empresa",
            "nombre": "Nombre",
            "padre": "Unidad padre",
            "ubicacion": "Ubicación",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar unidades por empresa (para padre)
        empresa_id = None
        if self.user and getattr(self.user, "empresa_id", None) and not _is_sa(self.user):
            empresa_id = self.user.empresa_id
        else:
            # si superadmin, intenta inferir empresa del instance/initial
            empresa_id = getattr(getattr(self.instance, "empresa", None), "id", None) or self.initial.get("empresa")

        if empresa_id and "padre" in self.fields:
            qs = UnidadOrganizacional.objects.filter(empresa_id=empresa_id).order_by("nombre")
            if getattr(self.instance, "id", None):
                qs = qs.exclude(id=self.instance.id)
            self.fields["padre"].queryset = qs

    def clean_tipo(self):
        obj = self.cleaned_data.get("tipo")
        return obj.id if obj else None

    def clean_estado(self):
        obj = self.cleaned_data.get("estado")
        return obj.id if obj else None


class PuestoForm(TTModelForm):
    class Meta:
        model = Puesto
        fields = ["empresa", "nombre", "descripcion", "unidad", "nivel", "salario_referencial"]
        labels = {
            "empresa": "Empresa",
            "nombre": "Nombre del puesto",
            "descripcion": "Descripción",
            "unidad": "Unidad organizacional",
            "nivel": "Nivel",
            "salario_referencial": "Salario referencial",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Unidad: filtrar por empresa
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if not empresa_id:
            empresa_id = getattr(getattr(self.instance, "empresa", None), "id", None) or self.initial.get("empresa")
        if empresa_id and "unidad" in self.fields:
            self.fields["unidad"].queryset = UnidadOrganizacional.objects.filter(empresa_id=empresa_id).order_by("nombre")


class TurnoForm(TTModelForm):

    dias_semana = forms.CharField(
        required=False,
        label="Días de la semana",
        help_text="Formato JSON. Ejemplo: [1,2,3,4,5] (1=Lun, 7=Dom).",
        widget=forms.TextInput(attrs={"placeholder": "[1,2,3,4,5]"}),
    )

    class Meta:
        model = Turno
        fields = [
            "empresa",
            "nombre",
            "hora_inicio",
            "hora_fin",
            "dias_semana",
            "tolerancia_minutos",
            "requiere_gps",
            "requiere_foto",
        ]

        labels = {
            "empresa": "Empresa",
            "nombre": "Nombre del turno",
            "hora_inicio": "Hora de inicio",
            "hora_fin": "Hora de fin",
            "tolerancia_minutos": "Tolerancia (minutos)",
            "requiere_gps": "Requiere GPS",
            "requiere_foto": "Requiere foto",
        }

        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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


# -----------------------------------------------------------------------------
# Configuración de asistencia (Geocercas / Reglas / Asignaciones de turno)
# -----------------------------------------------------------------------------


GEOCERCA_TIPOS = (
    ("CIRCULO", "Círculo (radio)"),
    ("POLIGONO", "Polígono"),
)


class GeocercaForm(TTModelForm):
    """Formulario amigable para asistencia.geocerca.

    En BD, `coordenadas` es JSON. Para mantenerlo usable:
    - Círculo: {center:{lat,lng}, radius_m}
    - Polígono: {points:[{lat,lng},...]}
    """

    fieldsets = [
        ("Identificación", ["empresa", "nombre", "tipo_ui", "activo"]),
        ("Círculo", ["centro_lat", "centro_lng", "radio_m"]),
        ("Polígono", ["puntos_json"]),
    ]

    tipo_ui = forms.ChoiceField(choices=GEOCERCA_TIPOS, label="Tipo")
    centro_lat = forms.DecimalField(required=False, label="Centro (lat)", max_digits=10, decimal_places=7)
    centro_lng = forms.DecimalField(required=False, label="Centro (lng)", max_digits=10, decimal_places=7)
    radio_m = forms.IntegerField(required=False, label="Radio (m)", min_value=1)
    puntos = forms.CharField(
        required=False,
        label="Puntos (JSON)",
        help_text='Solo para polígono. Ej: {"points":[{"lat":-3.99,"lng":-79.20}, ...]}',
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    class Meta:
        model = Geocerca
        fields = ["empresa", "nombre", "tipo_ui", "centro_lat", "centro_lng", "radio_m", "puntos", "activo"]
        labels = {
            "empresa": "Empresa",
            "nombre": "Nombre",
            "activo": "Activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Precarga desde coordenadas JSON
        coords = (getattr(self.instance, "coordenadas", None) or {}) if getattr(self.instance, "id", None) else {}
        if isinstance(coords, dict) and coords.get("center") and coords.get("radius_m"):
            self.fields["tipo_ui"].initial = "CIRCULO"
            self.fields["centro_lat"].initial = coords.get("center", {}).get("lat")
            self.fields["centro_lng"].initial = coords.get("center", {}).get("lng")
            self.fields["radio_m"].initial = coords.get("radius_m")
        elif isinstance(coords, dict) and coords.get("points"):
            self.fields["tipo_ui"].initial = "POLIGONO"
            self.fields["puntos"].initial = json.dumps({"points": coords.get("points")}, ensure_ascii=False)

    def clean(self):
        data = super().clean()
        tipo = data.get("tipo_ui")
        if tipo == "CIRCULO":
            if data.get("centro_lat") is None or data.get("centro_lng") is None or data.get("radio_m") is None:
                raise forms.ValidationError("Para una geocerca de tipo Círculo debes indicar centro (lat/lng) y radio.")
        if tipo == "POLIGONO":
            raw = (data.get("puntos") or "").strip()
            if not raw:
                raise forms.ValidationError("Para una geocerca de tipo Polígono debes cargar los puntos en formato JSON.")
            try:
                obj = json.loads(raw)
                points = obj.get("points")
                if not isinstance(points, list) or len(points) < 3:
                    raise ValueError
            except Exception:
                raise forms.ValidationError("El JSON de puntos no es válido. Debe incluir 'points' como lista de 3+ puntos.")
        return data

    def save(self, commit=True):
        instance: Geocerca = super().save(commit=False)

        tipo = self.cleaned_data.get("tipo_ui")
        if tipo == "CIRCULO":
            instance.coordenadas = {
                "center": {
                    "lat": float(self.cleaned_data.get("centro_lat")),
                    "lng": float(self.cleaned_data.get("centro_lng")),
                },
                "radius_m": int(self.cleaned_data.get("radio_m")),
            }
        elif tipo == "POLIGONO":
            obj = json.loads(self.cleaned_data.get("puntos"))
            instance.coordenadas = {"points": obj.get("points")}

        # tipo en BD es UUID (sin FK). Guardamos un UUID determinístico por tipo.
        instance.tipo = uuid.uuid5(uuid.NAMESPACE_URL, f"talenttrack-geocerca-type:{tipo}")

        if commit:
            instance.save()
        return instance


class ReglaAsistenciaForm(TTModelForm):
    fieldsets = [
        ("General", ["empresa", "geocerca", "activo"]),
        ("Controles", ["requiere_gps", "requiere_foto", "ip_permitidas_text"]),
        ("Tolerancias", ["considera_tardanza_desde_min", "considera_salida_anticipada_desde_min"]),
    ]

    ip_permitidas_text = forms.CharField(
        required=False,
        label="IPs permitidas",
        help_text="Opcional. Separa por comas. Ej: 10.0.0.1, 10.0.0.2",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    class Meta:
        model = ReglaAsistencia
        fields = [
            "empresa",
            "considera_tardanza_desde_min",
            "calculo_horas_extra",
            "geocerca",
            "ip_permitidas_text",
        ]
        labels = {
            "empresa": "Empresa",
            "considera_tardanza_desde_min": "Tardanza desde (min)",
            "calculo_horas_extra": "Cálculo horas extra",
            "geocerca": "Geocerca",
        }
        widgets = {
            "calculo_horas_extra": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scope_empresa_field()
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if empresa_id and "geocerca" in self.fields:
            self.fields["geocerca"].queryset = Geocerca.objects.filter(empresa_id=empresa_id, activo=True).order_by("nombre")

        if getattr(self.instance, "ip_permitidas", None):
            if isinstance(self.instance.ip_permitidas, list):
                self.fields["ip_permitidas_text"].initial = ", ".join(self.instance.ip_permitidas)

    def clean_ip_permitidas_text(self):
        raw = (self.cleaned_data.get("ip_permitidas_text") or "").strip()
        if not raw:
            return []
        parts = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
        return parts

    def save(self, commit=True):
        instance: ReglaAsistencia = super().save(commit=False)
        instance.ip_permitidas = self.cleaned_data.get("ip_permitidas_text") or []
        if commit:
            instance.save()
        return instance


class AsignacionTurnoForm(TTModelForm):
    fieldsets = [
        ("Asignación", ["empresa", "empleado", "turno"]),
        ("Vigencia", ["fecha_inicio", "fecha_fin"]),
        ("Opciones", ["es_rotativo", "es_activo"]),
    ]

    class Meta:
        model = AsignacionTurno
        fields = ["empresa", "empleado", "turno", "fecha_inicio", "fecha_fin", "es_rotativo", "es_activo"]
        labels = {
            "empresa": "Empresa",
            "empleado": "Empleado",
            "turno": "Turno",
            "fecha_inicio": "Desde",
            "fecha_fin": "Hasta",
            "es_rotativo": "Rotativo",
            "es_activo": "Activo",
        }
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if not empresa_id:
            empresa_id = getattr(getattr(self.instance, "empresa", None), "id", None) or self.initial.get("empresa")

        if empresa_id:
            if "empleado" in self.fields:
                self.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")
            if "turno" in self.fields:
                self.fields["turno"].queryset = Turno.objects.filter(empresa_id=empresa_id).order_by("nombre")



# -----------------------------------------------------------------------------
# Empleados / Contratos / Documentos
# -----------------------------------------------------------------------------


class EmpleadoForm(TTModelForm):
    fieldsets = [
        ("Datos personales", [
            "nombres", "apellidos", "documento", "email", "telefono", "direccion", "fecha_nacimiento", "foto_archivo",
        ]),
        ("Información laboral", [
            "empresa", "fecha_ingreso", "unidad", "puesto", "manager", "estado",
        ]),
    ]

    foto_archivo = forms.ImageField(
        required=False,
        label="Foto (archivo)",
        help_text="Opcional. JPG/PNG.",
    )

    estado = forms.ModelChoiceField(
        queryset=EstadoEmpleado.objects.all().order_by("codigo"),
        required=False,
        label="Estado del empleado",
    )

    class Meta:
        model = Empleado
        fields = [
            "empresa",
            "nombres",
            "apellidos",
            "documento",
            "email",
            "telefono",
            "direccion",
            "fecha_nacimiento",
            "fecha_ingreso",
            "unidad",
            "puesto",
            "manager",
            "estado",
            "foto_archivo",
        ]

        labels = {
            "empresa": "Empresa",
            "nombres": "Nombres",
            "apellidos": "Apellidos",
            "documento": "Documento (CI/Pasaporte)",
            "telefono": "Teléfono",
            "direccion": "Dirección",
            "fecha_nacimiento": "Fecha de nacimiento",
            "fecha_ingreso": "Fecha de ingreso",
            "unidad": "Unidad organizacional",
            "puesto": "Puesto",
            "manager": "Manager",
        }

        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "fecha_ingreso": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar combos por empresa
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if not empresa_id:
            empresa_id = getattr(getattr(self.instance, "empresa", None), "id", None) or self.initial.get("empresa")

        if empresa_id:
            if "unidad" in self.fields:
                self.fields["unidad"].queryset = UnidadOrganizacional.objects.filter(empresa_id=empresa_id).order_by("nombre")
            if "puesto" in self.fields:
                self.fields["puesto"].queryset = Puesto.objects.filter(empresa_id=empresa_id).order_by("nombre")
            if "manager" in self.fields:
                self.fields["manager"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")

    def clean_estado(self):
        obj = self.cleaned_data.get("estado")
        return obj.id if obj else None

    def save(self, commit=True):
        instance: Empleado = super().save(commit=False)

        upload = self.cleaned_data.get("foto_archivo")
        if upload:
            prefix = f"empleado/{instance.empresa_id or 'sin-empresa'}/{instance.id or 'nuevo'}"
            instance.foto_url = _save_upload(upload=upload, prefix=prefix)

        if commit:
            instance.save()
        return instance


class ContratoForm(TTModelForm):
    fieldsets = [
        ("Identificación", ["empresa", "empleado", "tipo", "estado"]),
        ("Vigencia", ["fecha_inicio", "fecha_fin", "turno_base"]),
        ("Condiciones económicas", ["salario_base", "jornada_semanal_horas"]),
    ]

    tipo = forms.ModelChoiceField(
        queryset=TipoContrato.objects.all().order_by("codigo"),
        required=False,
        label="Tipo de contrato",
    )
    estado = forms.ModelChoiceField(
        queryset=EstadoGenerico.objects.all().order_by("codigo"),
        required=False,
        label="Estado",
    )

    class Meta:
        model = Contrato
        fields = [
            "empresa",
            "empleado",
            "tipo",
            "fecha_inicio",
            "fecha_fin",
            "salario_base",
            "jornada_semanal_horas",
            "turno_base",
            "estado",
        ]
        labels = {
            "empresa": "Empresa",
            "empleado": "Empleado",
            "fecha_inicio": "Fecha de inicio",
            "fecha_fin": "Fecha de fin",
            "salario_base": "Salario base",
            "jornada_semanal_horas": "Horas semanales",
            "turno_base": "Turno base",
        }
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if not empresa_id:
            empresa_id = getattr(getattr(self.instance, "empresa", None), "id", None) or self.initial.get("empresa")

        if empresa_id:
            if "empleado" in self.fields:
                self.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")
            if "turno_base" in self.fields:
                self.fields["turno_base"].queryset = Turno.objects.filter(empresa_id=empresa_id).order_by("nombre")

        # Si viene empleado fijo (desde el detalle), lo bloqueamos
        empleado_id = self.initial.get("empleado")
        if empleado_id:
            self._lock_field("empleado", empleado_id)

    def clean_tipo(self):
        obj = self.cleaned_data.get("tipo")
        return obj.id if obj else None

    def clean_estado(self):
        obj = self.cleaned_data.get("estado")
        return obj.id if obj else None


DOCUMENTO_TIPOS = (
    ("CEDULA", "Cédula"),
    ("CONTRATO", "Contrato"),
    ("CERTIFICADO", "Certificado"),
    ("OTRO", "Otro"),
)


class DocumentoEmpleadoForm(TTModelForm):
    fieldsets = [
        ("Documento", ["empresa", "empleado", "tipo", "archivo", "vigente"]),
        ("Observaciones", ["observaciones"]),
    ]

    tipo = forms.ChoiceField(choices=DOCUMENTO_TIPOS, label="Tipo de documento")
    archivo = forms.FileField(required=True, label="Archivo")

    class Meta:
        model = DocumentoEmpleado
        fields = ["empresa", "empleado", "tipo", "archivo", "observaciones", "vigente"]
        labels = {
            "empresa": "Empresa",
            "empleado": "Empleado",
            "observaciones": "Observaciones",
            "vigente": "Vigente",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if not empresa_id:
            empresa_id = getattr(getattr(self.instance, "empresa", None), "id", None) or self.initial.get("empresa")

        if empresa_id and "empleado" in self.fields:
            self.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")

        empleado_id = self.initial.get("empleado")
        if empleado_id:
            self._lock_field("empleado", empleado_id)

    def clean_tipo(self):
        """El campo DB es UUID y no tiene FK; usamos UUID determinístico por código."""
        code = self.cleaned_data.get("tipo")
        if not code:
            return None
        return uuid.uuid5(uuid.NAMESPACE_URL, f"talenttrack-doc-type:{code}")

    def save(self, commit=True):
        instance: DocumentoEmpleado = super().save(commit=False)

        upload = self.cleaned_data.get("archivo")
        if upload:
            prefix = f"documentos/{instance.empresa_id or 'sin-empresa'}/{instance.empleado_id or 'sin-empleado'}"
            instance.archivo_url = _save_upload(upload=upload, prefix=prefix)

        if commit:
            instance.save()
        return instance


# -----------------------------------------------------------------------------
# Asistencia / Vacaciones
# -----------------------------------------------------------------------------


class EventoAsistenciaForm(TTModelForm):
    class Meta:
        model = EventoAsistencia
        # Nota: el modelo (BD) usa gps_lat/gps_lng y observacion (singular).
        # Mantener nombres fieles al script SQL.
        fields = [
            "empresa",
            "empleado",
            "tipo",
            "fuente",
            "gps_lat",
            "gps_lng",
            "foto_url",
            "observacion",
        ]
        labels = {
            "empresa": "Empresa",
            "empleado": "Empleado",
            "tipo": "Tipo de evento",
            "fuente": "Fuente",
            "gps_lat": "Latitud",
            "gps_lng": "Longitud",
            "foto_url": "Foto (URL)",
            "observacion": "Observación",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Por diseño: no se crea manualmente para evitar manipulaciones.
        for f in ("tipo", "fuente", "gps_lat", "gps_lng", "foto_url", "observacion"):
            if f in self.fields:
                self.fields[f].disabled = True
                self.fields[f].help_text = "Registro automático."


class TipoAusenciaForm(TTModelForm):
    class Meta:
        model = TipoAusencia
        fields = ["empresa", "nombre", "afecta_sueldo", "requiere_soporte", "descripcion"]
        labels = {
            "empresa": "Empresa",
            "nombre": "Nombre",
            "afecta_sueldo": "Afecta sueldo",
            "requiere_soporte": "Requiere soporte",
            "descripcion": "Descripción",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class SolicitudAusenciaForm(TTModelForm):
    fieldsets = [
        ("Solicitud", ["empresa", "empleado", "tipo_ausencia", "fecha_inicio", "fecha_fin"]),
        ("Detalle", ["motivo", "adjunto"]),
    ]

    adjunto = forms.FileField(required=False, label="Adjunto")

    class Meta:
        model = SolicitudAusencia
        fields = [
            "empresa",
            "empleado",
            "tipo_ausencia",
            "fecha_inicio",
            "fecha_fin",
            "motivo",
            "adjunto",
        ]
        labels = {
            "empresa": "Empresa",
            "empleado": "Empleado",
            "tipo_ausencia": "Tipo de permiso/ausencia",
            "fecha_inicio": "Desde",
            "fecha_fin": "Hasta",
            "motivo": "Motivo",
        }
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "motivo": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Empleado no elige empresa ni empleado.
        if self.user and getattr(self.user, "has_role", None) and self.user.has_role("EMPLEADO"):
            if getattr(self.user, "empleado_id", None):
                self._lock_field("empleado", self.user.empleado_id)

        # Filtro de empleados por empresa (para RRHH/Manager)
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if empresa_id and "empleado" in self.fields and not isinstance(self.fields["empleado"].widget, forms.HiddenInput):
            self.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")

        if empresa_id and "tipo_ausencia" in self.fields:
            # En el esquema actual, tipo_ausencia no tiene campo "activo"; filtramos por empresa o global.
            self.fields["tipo_ausencia"].queryset = TipoAusencia.objects.filter(Q(empresa_id=empresa_id) | Q(empresa_id__isnull=True)).order_by("nombre")

    def save(self, commit=True):
        instance: SolicitudAusencia = super().save(commit=False)

        upload = self.cleaned_data.get("adjunto")
        if upload:
            prefix = f"ausencias/{instance.empresa_id or 'sin-empresa'}/{instance.empleado_id or 'sin-empleado'}"
            instance.adjunto_url = _save_upload(upload=upload, prefix=prefix)

        if commit:
            instance.save()
        return instance


# -----------------------------------------------------------------------------
# KPI / Seguridad
# -----------------------------------------------------------------------------


class KPIForm(TTModelForm):
    fieldsets = [
        ("Identificación", ["empresa", "codigo", "nombre", "activo"]),
        ("Definición", ["descripcion", "unidad", "origen_datos", "formula"]),
    ]

    unidad = forms.ModelChoiceField(
        queryset=UnidadKPI.objects.all().order_by("codigo"),
        required=False,
        label="Unidad",
        help_text="Catálogo de unidades (config.unidad_kpi).",
    )

    class Meta:
        model = KPI
        fields = ["empresa", "codigo", "nombre", "descripcion", "unidad", "origen_datos", "formula", "activo"]
        labels = {
            "empresa": "Empresa",
            "codigo": "Código",
            "nombre": "Nombre",
            "descripcion": "Descripción",
            "unidad": "Unidad",
            "origen_datos": "Origen de datos",
            "formula": "Fórmula",
            "activo": "Activo",
        }

        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "formula": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def clean_unidad(self):
        obj = self.cleaned_data.get("unidad")
        return obj.id if obj else None


class UsuarioForm(TTModelForm):
    class Meta:
        model = Usuario
        fields = ["empresa", "email", "phone", "empleado", "estado", "mfa_habilitado"]
        labels = {
            "empresa": "Empresa",
            "email": "Correo electrónico",
            "phone": "Teléfono",
            "empleado": "Empleado asociado",
            "estado": "Estado",
            "mfa_habilitado": "MFA habilitado",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # RRHH trabaja en su empresa
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if empresa_id and "empleado" in self.fields:
            self.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")


class UsuarioCreateWithRolForm(TTBaseForm):
    """Crea un usuario y asigna un rol.

    - SUPERADMIN puede crear usuarios para cualquier empresa.
    - ADMIN_RRHH crea usuarios solo en su empresa.
    """

    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all().order_by("nombre_comercial", "razon_social"), label="Empresa")
    email = forms.EmailField(label="Correo electrónico")
    phone = forms.CharField(required=False, label="Teléfono")
    empleado = forms.ModelChoiceField(queryset=Empleado.objects.none(), required=False, label="Empleado asociado")
    rol = forms.ModelChoiceField(queryset=Rol.objects.all().order_by("nombre"), label="Rol")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(render_value=False))
    estado = forms.ModelChoiceField(queryset=EstadoGenerico.objects.all().order_by("codigo"), required=False, label="Estado")
    mfa_habilitado = forms.BooleanField(required=False, label="MFA habilitado")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ADMIN_RRHH: empresa bloqueada
        if self.user and self.user.has_role("ADMIN_RRHH") and not _is_sa(self.user):
            self.fields["empresa"].queryset = self.fields["empresa"].queryset.filter(id=self.user.empresa_id)
            self.fields["empresa"].initial = self.user.empresa_id
            self.fields["empresa"].disabled = True

        # Población de combos dependiente de empresa
        empresa_id = None
        if self.is_bound:
            empresa_id = self.data.get("empresa")
        if not empresa_id and self.user and not _is_sa(self.user):
            empresa_id = getattr(self.user, "empresa_id", None)

        if empresa_id:
            self.fields["empleado"].queryset = Empleado.objects.filter(empresa_id=empresa_id).order_by("apellidos", "nombres")
            self.fields["rol"].queryset = Rol.objects.all().order_by("nombre")

    @transaction.atomic
    def save(self):
        empresa = self.cleaned_data["empresa"]
        usuario = Usuario.objects.create(
            empresa_id=empresa.id,
            email=self.cleaned_data["email"].lower().strip(),
            phone=(self.cleaned_data.get("phone") or "").strip() or None,
            empleado_id=(self.cleaned_data.get("empleado").id if self.cleaned_data.get("empleado") else None),
            estado=(self.cleaned_data.get("estado").id if self.cleaned_data.get("estado") else None),
            mfa_habilitado=bool(self.cleaned_data.get("mfa_habilitado")),
            hash_password=make_password_if_needed(self.cleaned_data["password"]),
        )

        UsuarioRol.objects.create(
            usuario=usuario,
            rol=self.cleaned_data["rol"],
        )
        return usuario


class RolForm(TTModelForm):
    """Formulario de Roles.

    Nota: En el modelo Rol no existe el campo `empresa`.
    La relación Empresa ↔ Rol se maneja a través de UsuarioRol (asignación de rol por empresa).
    """

    class Meta:
        model = Rol
        fields = ["nombre", "descripcion"]
        labels = {"nombre": "Nombre", "descripcion": "Descripción"}


class UsuarioRolForm(TTModelForm):
    class Meta:
        model = UsuarioRol
        fields = ["usuario", "rol"]
        labels = {"usuario": "Usuario", "rol": "Rol"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        empresa_id = getattr(self.user, "empresa_id", None) if (self.user and not _is_sa(self.user)) else None
        if empresa_id:
            if "usuario" in self.fields:
                self.fields["usuario"].queryset = Usuario.objects.filter(empresa_id=empresa_id).order_by("email")
            if "rol" in self.fields:
                # Roles disponibles
                self.fields["rol"].queryset = Rol.objects.all().order_by("nombre")


# -----------------------------------------------------------------------------
# Alta Empleado + Usuario + Rol (un paso)
# -----------------------------------------------------------------------------


class EmpleadoUsuarioAltaForm(TTBaseForm):
    """Alta de Empleado + Usuario + Rol (onboarding) en una sola pantalla.

    Nota de UX:
    - En esta pantalla se ingresa un solo Email (el del usuario) y se reutiliza como email del empleado.
    - Si no se ingresa teléfono del empleado, se usará el teléfono del usuario.
    """

    # Empresa
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all().order_by("razon_social"), label="Empresa")

    # Datos del empleado
    nombres = forms.CharField(max_length=150, label="Nombres")
    apellidos = forms.CharField(max_length=150, label="Apellidos")
    documento = forms.CharField(max_length=100, required=False, label="Documento (CI/Pasaporte)")
    telefono = forms.CharField(max_length=50, required=False, label="Teléfono")
    direccion = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Dirección")

    fecha_nacimiento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Fecha nacimiento",
    )
    fecha_ingreso = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Fecha ingreso",
    )

    unidad = forms.ModelChoiceField(queryset=UnidadOrganizacional.objects.none(), required=False, label="Unidad")
    puesto = forms.ModelChoiceField(queryset=Puesto.objects.none(), required=False, label="Puesto")
    manager = forms.ModelChoiceField(queryset=Empleado.objects.none(), required=False, label="Manager")

    estado_empleado = forms.ModelChoiceField(
        queryset=EstadoEmpleado.objects.all().order_by("codigo"),
        required=False,
        label="Estado del empleado",
    )

    foto_archivo = forms.ImageField(required=False, label="Foto (archivo)")

    # Usuario + acceso
    email = forms.EmailField(label="Email")
    phone = forms.CharField(max_length=50, required=False, label="Teléfono (usuario)")
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    mfa_habilitado = forms.BooleanField(required=False, label="Habilitar MFA")
    rol = forms.ModelChoiceField(queryset=Rol.objects.all().order_by("nombre"), label="Rol")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ADMIN_RRHH: empresa fija
        if self.user and getattr(self.user, "has_role", None) and self.user.has_role("ADMIN_RRHH") and not _is_sa(self.user):
            if getattr(self.user, "empresa_id", None):
                self.fields["empresa"].queryset = Empresa.objects.filter(id=self.user.empresa_id)
                self.fields["empresa"].initial = self.user.empresa_id
                self.fields["empresa"].disabled = True

        # Placeholders suaves
        self.fields["email"].widget.attrs.setdefault("placeholder", "usuario@empresa.com")

    def clean_estado_empleado(self):
        obj = self.cleaned_data.get("estado_empleado")
        return obj.id if obj else None

    @transaction.atomic
    def save(self):
        empresa: Empresa = self.cleaned_data["empresa"]

        # Reglas UX: email empleado = email usuario; teléfono empleado opcional -> usa el del usuario
        user_email = (self.cleaned_data["email"] or "").strip().lower()
        user_phone = (self.cleaned_data.get("phone") or "").strip() or None
        emp_phone = (self.cleaned_data.get("telefono") or "").strip() or None
        if not emp_phone:
            emp_phone = user_phone

        # 1) Crear empleado
        emp = Empleado(
            empresa_id=empresa.id,
            nombres=self.cleaned_data["nombres"],
            apellidos=self.cleaned_data["apellidos"],
            documento=self.cleaned_data.get("documento"),
            email=user_email,
            telefono=emp_phone,
            direccion=(self.cleaned_data.get("direccion") or "").strip() or None,
            fecha_nacimiento=self.cleaned_data.get("fecha_nacimiento"),
            fecha_ingreso=self.cleaned_data.get("fecha_ingreso"),
            unidad_id=getattr(self.cleaned_data.get("unidad"), "id", None),
            puesto_id=getattr(self.cleaned_data.get("puesto"), "id", None),
            manager_id=getattr(self.cleaned_data.get("manager"), "id", None),
            estado=self.cleaned_data.get("estado_empleado"),
        )

        upload = self.cleaned_data.get("foto_archivo")
        if upload:
            emp.foto_url = _save_upload(upload=upload, prefix=f"empleado/{empresa.id}/nuevo")

        emp.save()

        # 2) Crear usuario
        usr = Usuario(
            empresa_id=empresa.id,
            email=user_email,
            phone=user_phone,
            empleado_id=emp.id,
            estado=None,
            mfa_habilitado=bool(self.cleaned_data.get("mfa_habilitado")),
            hash_password=make_password_if_needed(self.cleaned_data["password"]),
        )
        usr.save()

        # 3) Asignar rol
        rol: Rol = self.cleaned_data["rol"]
        UsuarioRol.objects.create(usuario_id=usr.id, rol_id=rol.id)

        return emp, usr
