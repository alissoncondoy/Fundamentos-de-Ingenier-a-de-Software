from __future__ import annotations

import json
import os
import uuid

from django import forms
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q

from .tt_security import make_password_if_needed, verify_and_upgrade_password

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
    TipoGeocerca,
    EvaluacionDesempeno,
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

        # Checkbox simple: clase al <input>
        if isinstance(widget, forms.CheckboxInput):
            _add_css_class(widget, "form-check-input")
            continue

        # CheckboxSelectMultiple (ej: selector de días). No aplicamos clases de input al contenedor,
        # porque Django renderiza un contenedor (ul/div) y no el <input> directamente.
        if isinstance(widget, forms.CheckboxSelectMultiple):
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
        # Algunos CBVs (CreateView/UpdateView) inyectan `instance` pensando en ModelForm.
        # Este form NO es ModelForm, así que lo ignoramos para evitar TypeError.
        kwargs.pop("instance", None)
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
    # Geocerca (se almacena en asistencia.geocerca y se referencia desde asistencia.regla_asistencia)
    geocerca_lat = forms.FloatField(required=True, widget=forms.HiddenInput())
    geocerca_lng = forms.FloatField(required=True, widget=forms.HiddenInput())
    geocerca_radio_m = forms.IntegerField(required=True, widget=forms.HiddenInput(), initial=150)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Precargar geocerca actual (si existe)
        empresa_id = getattr(getattr(self.instance, "id", None), "hex", None) or getattr(self.instance, "id", None)
        if empresa_id:
            regla = ReglaAsistencia.objects.filter(empresa_id=empresa_id).first()
            geo = None
            if regla and getattr(regla, "geocerca_id", None):
                geo = Geocerca.objects.filter(id=regla.geocerca_id).first()
            if not geo:
                geo = Geocerca.objects.filter(empresa_id=empresa_id).order_by("-creado_el").first()

            coords = getattr(geo, "coordenadas", None) if geo else None
            try:
                if coords and isinstance(coords, dict):
                    center = coords.get("center") or {}
                    self.fields["geocerca_lat"].initial = center.get("lat")
                    self.fields["geocerca_lng"].initial = center.get("lng")
                    self.fields["geocerca_radio_m"].initial = coords.get("radius_m") or coords.get("radio_m") or 150
            except Exception:
                # si el JSON no tiene el formato esperado, dejamos defaults
                pass

    def save(self, commit=True):
        instance: Empresa = super().save(commit=False)

        upload = self.cleaned_data.get("logo_archivo")
        if upload:
            instance.logo_url = _save_upload(upload=upload, prefix=f"empresa/{instance.id or 'nuevo'}")

        if commit:
            instance.save()

            # Guardar/actualizar Geocerca principal de la empresa
            lat = self.cleaned_data.get("geocerca_lat")
            lng = self.cleaned_data.get("geocerca_lng")
            radio = self.cleaned_data.get("geocerca_radio_m")

            if lat is not None and lng is not None and radio is not None:
                from django.utils import timezone

                coords = {
                    "center": {"lat": float(lat), "lng": float(lng)},
                    "radius_m": int(radio),
                }

                regla = ReglaAsistencia.objects.filter(empresa_id=instance.id).first()
                geo = None
                if regla and getattr(regla, "geocerca_id", None):
                    geo = Geocerca.objects.filter(id=regla.geocerca_id).first()

                if not geo:
                    geo = Geocerca.objects.filter(empresa_id=instance.id).order_by("-creado_el").first()

                # Tipo de geocerca por defecto (si existe en catálogo)
                tipo_id = None
                try:
                    tipo = (
                        TipoGeocerca.objects.filter(codigo__icontains="CIR").order_by("codigo").first()
                        or TipoGeocerca.objects.all().order_by("codigo").first()
                    )
                    tipo_id = getattr(tipo, "id", None)
                except Exception:
                    tipo_id = None

                if not geo:
                    geo = Geocerca(
                        id=uuid.uuid4(),
                        empresa_id=instance.id,
                        nombre="Geocerca principal",
                        tipo=tipo_id,
                        coordenadas=coords,
                        activo=True,
                        creado_el=timezone.now(),
                    )
                else:
                    geo.nombre = geo.nombre or "Geocerca principal"
                    geo.tipo = geo.tipo or tipo_id
                    geo.coordenadas = coords
                    geo.activo = True
                    if not geo.creado_el:
                        geo.creado_el = timezone.now()
                geo.save()

                if not regla:
                    regla = ReglaAsistencia(
                        id=uuid.uuid4(),
                        empresa_id=instance.id,
                        geocerca_id=geo.id,
                        creado_el=timezone.now(),
                    )
                else:
                    regla.geocerca_id = geo.id
                    if not regla.creado_el:
                        regla.creado_el = timezone.now()
                regla.save()
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

        if "padre" in self.fields:
            # Si todavía no hay empresa seleccionada (típico en SUPERADMIN creando),
            # iniciamos vacío y dejamos que el JS de dependent_selects lo cargue.
            if not empresa_id:
                self.fields["padre"].queryset = UnidadOrganizacional.objects.none()
            else:
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

    class WeekdayCircleWidget(forms.Widget):
        """Widget sin templates: renderiza checkboxes como círculos L M X J V S D en fila.

        Evita depender de templates custom y funciona igual en cualquier página.
        """

        allow_multiple_selected = True

        def __init__(self, choices=(), attrs=None):
            super().__init__(attrs)
            self.choices = list(choices)

        def value_from_datadict(self, data, files, name):
            # Django envía múltiples valores con el mismo name.
            getter = getattr(data, "getlist", None)
            if callable(getter):
                return getter(name)
            v = data.get(name)
            if v is None:
                return []
            return v if isinstance(v, (list, tuple)) else [v]

        def render(self, name, value, attrs=None, renderer=None):
            from django.utils.safestring import mark_safe
            value = value or []
            if not isinstance(value, (list, tuple, set)):
                value = [value]
            value_set = {str(v) for v in value}

            attrs = attrs or {}
            base_id = attrs.get("id") or f"id_{name}"

            # Inline styles to avoid dependency on external css bundles.
            # Goal: horizontal circles, white background; when selected it fills with a nice color.
            out = [
                """
                <style>
                  .tt-weekdays--circle{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
                  .tt-weekday-input{position:absolute;opacity:0;width:1px;height:1px;margin:0;padding:0;}
                  .tt-weekday{width:36px;height:36px;border:2px solid #cbd5e1;border-radius:9999px;
                    display:inline-flex;align-items:center;justify-content:center;
                    font-weight:700;color:#334155;cursor:pointer;user-select:none;
                    transition:background .15s,border-color .15s,color .15s,box-shadow .15s;
                  }
                  .tt-weekday:hover{border-color:#8b1d2c;}
                  .tt-weekday-input:focus + .tt-weekday{outline:3px solid rgba(139,29,44,.25);outline-offset:2px;}
                  .tt-weekday-input:checked + .tt-weekday{background:#8b1d2c;border-color:#8b1d2c;color:#fff;
                    box-shadow:0 4px 10px rgba(139,29,44,.25);
                  }
                </style>
                """,
                '<div class="tt-weekdays tt-weekdays--circle" role="group" aria-label="Días de la semana">'
            ]
            for idx, (val, label) in enumerate(self.choices):
                cid = f"{base_id}_{idx}"
                checked = " checked" if str(val) in value_set else ""
                out.append(
                    f'<input class="tt-weekday-input" type="checkbox" name="{name}" value="{val}" id="{cid}"{checked}>'
                )
                out.append(
                    f'<label class="tt-weekday" for="{cid}">{label}</label>'
                )
            out.append("</div>")
            return mark_safe("".join(out))

    # UI: selección rápida de días (L M X J V S D).
    # En BD se guarda como lista de enteros: 1=Lun ... 7=Dom
    DIAS_CHOICES = (
        ('1', 'L'),
        ('2', 'M'),
        ('3', 'X'),
        ('4', 'J'),
        ('5', 'V'),
        ('6', 'S'),
        ('7', 'D'),
    )

    dias_semana = forms.MultipleChoiceField(
        required=False,
        choices=DIAS_CHOICES,
        label='Días de la semana',
        help_text='Marca los días en los que aplica el turno.',
        # Render propio (sin templates) para asegurar UI circular horizontal.
        widget=WeekdayCircleWidget(choices=DIAS_CHOICES),
    )

    # 2da jornada (opcional). Se guarda dentro de Turno.dias_semana (JSON) para no tocar esquema.
    hora_inicio_2 = forms.TimeField(
        required=False,
        label="Hora de inicio (2da jornada)",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    hora_fin_2 = forms.TimeField(
        required=False,
        label="Hora de fin (2da jornada)",
        widget=forms.TimeInput(attrs={"type": "time"}),
    )

    class Meta:
        model = Turno
        fields = [
            "empresa",
            "nombre",
            "hora_inicio",
            "hora_fin",
            "hora_inicio_2",
            "hora_fin_2",
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
            "hora_inicio_2": "Hora de inicio (2da jornada)",
            "hora_fin_2": "Hora de fin (2da jornada)",
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
        # Inicial: soporta lista [1..7] o dict {days:[1..7], segments:[...]}.
        raw = getattr(self.instance, "dias_semana", None) if getattr(self, "instance", None) is not None else None
        days = []
        seg2_start = None
        seg2_end = None
        try:
            if isinstance(raw, dict):
                days = raw.get("days") or []
                segs = raw.get("segments") or []
                if isinstance(segs, list) and len(segs) >= 2 and isinstance(segs[1], dict):
                    seg2_start = segs[1].get("start")
                    seg2_end = segs[1].get("end")
            elif isinstance(raw, (list, tuple)):
                days = list(raw)
        except Exception:
            days = []

        if days:
            self.initial["dias_semana"] = [str(x) for x in days]

        # Precarga 2da jornada si viene en JSON.
        if seg2_start and not self.initial.get("hora_inicio_2"):
            try:
                self.initial["hora_inicio_2"] = datetime.strptime(str(seg2_start)[:5], "%H:%M").time()
            except Exception:
                pass
        if seg2_end and not self.initial.get("hora_fin_2"):
            try:
                self.initial["hora_fin_2"] = datetime.strptime(str(seg2_end)[:5], "%H:%M").time()
            except Exception:
                pass

        # UX: si no hay 2da jornada, ocultamos labels redundantes con ayuda.
        self.fields["hora_inicio_2"].help_text = "Opcional. Para turnos con doble jornada (ej: 08:00-13:00 y 15:00-18:00)."
        self.fields["hora_fin_2"].help_text = ""

    def clean_dias_semana(self):
        raw = self.cleaned_data.get('dias_semana') or []
        if not raw:
            return None
        try:
            vals = sorted({int(x) for x in raw})
        except Exception:
            raise forms.ValidationError('Selecciona días válidos.')
        for x in vals:
            if x < 1 or x > 7:
                raise forms.ValidationError('Los días deben estar entre 1 y 7.')
        return vals

    def clean(self):
        data = super().clean()

        h1_i = data.get("hora_inicio")
        h1_f = data.get("hora_fin")
        h2_i = data.get("hora_inicio_2")
        h2_f = data.get("hora_fin_2")

        # Validación básica de rangos
        if h1_i and h1_f and h1_i >= h1_f:
            self.add_error("hora_fin", "La hora de fin debe ser mayor que la hora de inicio.")

        if (h2_i and not h2_f) or (h2_f and not h2_i):
            self.add_error("hora_inicio_2", "Si defines 2da jornada, debes indicar inicio y fin.")

        if h2_i and h2_f:
            if h2_i >= h2_f:
                self.add_error("hora_fin_2", "La hora de fin (2da jornada) debe ser mayor que la hora de inicio.")
            # Evita solapes evidentes con la primera jornada (si hay datos)
            if h1_i and h1_f:
                # Permitimos jornadas separadas; si se solapan, bloquear.
                overlap = not (h1_f <= h2_i or h2_f <= h1_i)
                if overlap:
                    self.add_error("hora_inicio_2", "La 2da jornada se solapa con la primera. Ajusta los horarios.")

        return data

    def save(self, commit=True):
        instance = super().save(commit=False)

        days = self.cleaned_data.get("dias_semana")  # ya viene como lista[int] o None
        h2_i = self.cleaned_data.get("hora_inicio_2")
        h2_f = self.cleaned_data.get("hora_fin_2")

        # Persistencia compatible: si hay 2da jornada, guardamos dict en JSON.
        if days and h2_i and h2_f:
            instance.dias_semana = {
                "days": days,
                "segments": [
                    {
                        "start": instance.hora_inicio.strftime("%H:%M") if instance.hora_inicio else None,
                        "end": instance.hora_fin.strftime("%H:%M") if instance.hora_fin else None,
                    },
                    {
                        "start": h2_i.strftime("%H:%M"),
                        "end": h2_f.strftime("%H:%M"),
                    },
                ],
            }
        else:
            # Mantener formato legacy (lista) cuando no se usa doble jornada.
            instance.dias_semana = days

        if commit:
            instance.save()
            self.save_m2m()
        return instance


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


class EmpleadoSelfProfileForm(TTModelForm):
    """Edición limitada del propio empleado.

    Reglas:
    - El empleado NO puede editar datos laborales/rol/empresa.
    - Solo puede actualizar: dirección y foto.
    """

    fieldsets = [
        ("Mi perfil", ["direccion", "foto_archivo"]),
    ]

    foto_archivo = forms.ImageField(
        required=False,
        label="Foto (archivo)",
        help_text="Opcional. JPG/PNG.",
    )

    class Meta:
        model = Empleado
        fields = [
            "direccion",
            "foto_archivo",
        ]
        labels = {
            "direccion": "Dirección",
        }

    def save(self, commit=True):
        instance: Empleado = super().save(commit=False)

        upload = self.cleaned_data.get("foto_archivo")
        if upload:
            prefix = f"empleado/{instance.empresa_id or 'sin-empresa'}/{instance.id or 'nuevo'}"
            instance.foto_url = _save_upload(upload=upload, prefix=prefix)

        if commit:
            instance.save()
        return instance


class TTPasswordChangeForm(forms.Form):
    """Cambio de contraseña para el usuario logueado (TTUser).

    Este proyecto usa autenticación propia (cookie) y NO usa django.contrib.auth.
    Por eso no podemos usar PasswordChangeForm de Django.
    """

    old_password = forms.CharField(
        label="Contraseña actual",
        widget=forms.PasswordInput,
        strip=False,
        required=True,
    )
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput,
        strip=False,
        required=True,
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput,
        strip=False,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        self.tt_user = kwargs.pop("tt_user", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()

        if not self.tt_user or not getattr(self.tt_user, "user_id", None):
            raise forms.ValidationError("No se pudo identificar el usuario.")

        old = cleaned.get("old_password")
        new1 = cleaned.get("new_password1")
        new2 = cleaned.get("new_password2")

        if new1 and new2 and new1 != new2:
            self.add_error("new_password2", "Las contraseñas no coinciden.")

        # Validación de contraseña actual
        try:
            usuario = Usuario.objects.get(id=self.tt_user.user_id)
        except Usuario.DoesNotExist:
            raise forms.ValidationError("Usuario no encontrado.")

        ok, upgraded = verify_and_upgrade_password(usuario.hash_password, old or "")
        if not ok:
            self.add_error("old_password", "Contraseña actual incorrecta.")
        else:
            # Si era legacy plaintext y se puede mejorar, lo guardamos ya.
            if upgraded:
                usuario.hash_password = upgraded
                usuario.save(update_fields=["hash_password"])

        return cleaned

    def save(self):
        """Guarda la nueva contraseña (hash) en Usuario."""
        if not self.is_valid():
            raise ValueError("El formulario no es válido")

        usuario = Usuario.objects.get(id=self.tt_user.user_id)
        usuario.hash_password = make_password_if_needed(self.cleaned_data["new_password1"])
        usuario.save(update_fields=["hash_password"])
        return usuario


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
        ("Definición", ["descripcion", "unidad", "origen_datos", "metrica", "formula"]),
    ]

    # Métricas predefinidas para cálculo automático (más fácil que escribir fórmula manual)
    METRICA_CHOICES = [
        ("", "— Selecciona una métrica —"),
        ("asistencia.puntualidad_pct", "Puntualidad (%)"),
        ("asistencia.dias_trabajados", "Días trabajados"),
        ("asistencia.horas_trabajadas", "Horas trabajadas"),
        ("asistencia.horas_extra", "Horas extra"),
        ("asistencia.minutos_tardanza", "Minutos de tardanza"),
    ]

    metrica = forms.ChoiceField(
        required=False,
        choices=METRICA_CHOICES,
        label="Métrica (automática)",
        help_text=(
            "Opcional. Selecciona una métrica para que el sistema la calcule automáticamente "
            "(asistencia/jornadas). Si eliges una métrica, la 'Fórmula' se completa sola."
        ),
    )

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

        # Si el KPI ya tiene una fórmula que coincide con una métrica conocida, precargarla.
        inst = getattr(self, "instance", None)
        if inst and getattr(inst, "formula", None):
            if inst.formula in dict(self.METRICA_CHOICES):
                self.fields["metrica"].initial = inst.formula

        # UX: el 80% de casos no necesita "fórmula" libre.
        self.fields["formula"].required = False
        self.fields["formula"].help_text = (
            "Opcional. Si necesitas una fórmula personalizada, escríbela aquí. "
            "Si seleccionaste una métrica, se usará esa automáticamente."
        )

    def clean(self):
        cleaned = super().clean()
        metrica = cleaned.get("metrica")
        formula = (cleaned.get("formula") or "").strip()

        # Si el usuario elige una métrica, guardamos la clave en el campo formula
        # (sin migraciones: usamos un campo existente del modelo).
        if metrica:
            cleaned["formula"] = metrica
            # Origen sugerido
            if not (cleaned.get("origen_datos") or "").strip():
                cleaned["origen_datos"] = "ASISTENCIA"
        else:
            cleaned["formula"] = formula

        return cleaned

    def clean_unidad(self):
        obj = self.cleaned_data.get("unidad")
        return obj.id if obj else None


class EvaluacionForm(TTModelForm):
    """Evaluación de desempeño: CRUD básico.

    Nota: el campo `instrumento` se puede editar como JSON (opcional).
    """

    fieldsets = [
        ('Datos generales', ['empresa', 'empleado', 'evaluador', 'fecha']),
        ('Resultado', ['periodo', 'tipo', 'puntaje_total', 'comentarios']),
        ('Instrumento (opcional)', ['instrumento_json']),
    ]

    instrumento_json = forms.CharField(
        required=False,
        label='Instrumento (JSON)',
        help_text='Opcional. Pega/edita un JSON válido (ej: preguntas, rúbrica, etc.).',
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': '{"preguntas": [...]}' }),
    )

    class Meta:
        model = EvaluacionDesempeno
        fields = [
            'empresa', 'empleado', 'evaluador', 'fecha',
            'periodo', 'tipo', 'puntaje_total', 'comentarios',
            'instrumento_json',
        ]
        labels = {
            'empresa': 'Empresa',
            'empleado': 'Empleado',
            'evaluador': 'Evaluador',
            'fecha': 'Fecha',
            'periodo': 'Periodo',
            'tipo': 'Tipo',
            'puntaje_total': 'Puntaje total',
            'comentarios': 'Comentarios',
        }
        widgets = {
            'fecha': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'comentarios': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Scopes: limitar empresa/empleados si no es SUPERADMIN
        if self.user and not _is_sa(self.user):
            if 'empresa' in self.fields:
                self.fields['empresa'].queryset = Empresa.objects.filter(id=self.user.empresa_id)
                self.fields['empresa'].initial = self.user.empresa_id
                self.fields['empresa'].disabled = True
            if 'empleado' in self.fields:
                self.fields['empleado'].queryset = Empleado.objects.filter(empresa_id=self.user.empresa_id).order_by('apellidos','nombres')
            if 'evaluador' in self.fields:
                self.fields['evaluador'].queryset = Empleado.objects.filter(empresa_id=self.user.empresa_id).order_by('apellidos','nombres')

        # Inicializar instrumento_json desde el JSONField
        inst = getattr(self, 'instance', None)
        if inst is not None and getattr(inst, 'instrumento', None):
            try:
                self.initial['instrumento_json'] = json.dumps(inst.instrumento, ensure_ascii=False)
            except Exception:
                self.initial['instrumento_json'] = str(inst.instrumento)

    def clean_instrumento_json(self):
        raw = (self.cleaned_data.get('instrumento_json') or '').strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            raise forms.ValidationError('Instrumento JSON inválido.')

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.instrumento = self.cleaned_data.get('instrumento_json')
        if commit:
            obj.save()
        return obj


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
            qs_roles = Rol.objects.all().order_by("nombre")
            if self.user and not _is_sa(self.user):
                qs_roles = qs_roles.exclude(nombre__iexact="SUPERADMIN")
            self.fields["rol"].queryset = qs_roles


    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get('rol')
        empleado = cleaned.get('empleado')
        empresa = cleaned.get('empresa')

        # Restringir roles altos si no es SUPERADMIN
        if self.user and not _is_sa(self.user):
            if rol and str(getattr(rol, 'nombre', '')).upper() == 'SUPERADMIN':
                self.add_error('rol', 'No puedes asignar el rol SUPERADMIN.')

        # Validación de acceso: si el rol requiere relación con empleado, obligamos a seleccionarlo
        rol_name = (getattr(rol, 'nombre', '') or '').upper() if rol else ''
        if rol_name in {'EMPLEADO', 'MANAGER'} and not empleado:
            self.add_error('empleado', 'Para este rol debes asociar un empleado.')

        # Empresa siempre requerida
        if not empresa:
            self.add_error('empresa', 'Selecciona una empresa.')

        return cleaned
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
                qs_roles = Rol.objects.all().order_by("nombre")
            if self.user and not _is_sa(self.user):
                qs_roles = qs_roles.exclude(nombre__iexact="SUPERADMIN")
            self.fields["rol"].queryset = qs_roles


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

        # Seguridad: RRHH (y cualquier no-superadmin) NO puede ver/seleccionar SUPERADMIN
        qs_roles = Rol.objects.all().order_by("nombre")
        if self.user and not _is_sa(self.user):
            qs_roles = qs_roles.exclude(nombre__iexact="SUPERADMIN")
        self.fields["rol"].queryset = qs_roles

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("rol")
        if self.user and not _is_sa(self.user):
            if rol and str(getattr(rol, "nombre", "")).upper() == "SUPERADMIN":
                self.add_error("rol", "No puedes asignar el rol SUPERADMIN.")
        return cleaned

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
