import uuid
from django.db import models


# NOTE:
# - All models map to EXISTING PostgreSQL tables from sriptTT.sql
# - We NEVER create/migrate tables from Django: managed = False
# - We use explicit schema-qualified db_table names like 'core"."empresa' so Django quotes to "core"."empresa"


class Empresa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    razon_social = models.CharField(max_length=150)
    nombre_comercial = models.CharField(max_length=150, blank=True, null=True)
    ruc_nit = models.CharField(max_length=50, blank=True, null=True)
    pais = models.CharField(max_length=100, blank=True, null=True)
    moneda = models.CharField(max_length=10, blank=True, null=True)
    logo_url = models.TextField(blank=True, null=True)
    estado = models.UUIDField(blank=True, null=True)
    creada_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"core"."empresa"'
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self):
        return self.nombre_comercial or self.razon_social


# ---------------------------------------------------------------------
# Catálogos (config.*) – definidos en sriptTT.sql
# ---------------------------------------------------------------------


class EstadoGenerico(models.Model):
    """Estado genérico para entidades (config.estado_generico)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."estado_generico"'
        verbose_name = "Estado (genérico)"
        verbose_name_plural = "Estados (genérico)"

    def __str__(self):
        return self.codigo


class EstadoEmpleado(models.Model):
    """Catálogo de estado del empleado (config.estado_empleado)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."estado_empleado"'
        verbose_name = "Estado de empleado"
        verbose_name_plural = "Estados de empleado"

    def __str__(self):
        return self.codigo


class TipoContrato(models.Model):
    """Catálogo de tipo de contrato (config.tipo_contrato)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."tipo_contrato"'
        verbose_name = "Tipo de contrato"
        verbose_name_plural = "Tipos de contrato"

    def __str__(self):
        return self.codigo


class TipoUnidad(models.Model):
    """Catálogo de tipo de unidad (config.tipo_unidad)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."tipo_unidad"'
        verbose_name = "Tipo de unidad"
        verbose_name_plural = "Tipos de unidad"

    def __str__(self):
        return self.codigo


class TipoTurno(models.Model):
    """Catálogo de tipo de turno (config.tipo_turno)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."tipo_turno"'
        verbose_name = "Tipo de turno"
        verbose_name_plural = "Tipos de turno"

    def __str__(self):
        return self.codigo


class TipoGeocerca(models.Model):
    """Catálogo de tipo de geocerca (config.tipo_geocerca)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."tipo_geocerca"'
        verbose_name = "Tipo de geocerca"
        verbose_name_plural = "Tipos de geocerca"

    def __str__(self):
        return self.codigo


class TipoDispositivo(models.Model):
    """Catálogo de tipo de dispositivo (config.tipo_dispositivo)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."tipo_dispositivo"'
        verbose_name = "Tipo de dispositivo"
        verbose_name_plural = "Tipos de dispositivo"

    def __str__(self):
        return self.codigo


class UnidadOrganizacional(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    nombre = models.CharField(max_length=150)
    tipo = models.UUIDField(blank=True, null=True)
    padre = models.ForeignKey("self", on_delete=models.SET_NULL, db_column="padre_id", null=True, blank=True, db_constraint=False)
    ubicacion = models.CharField(max_length=250, blank=True, null=True)
    estado = models.UUIDField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"core"."unidad_organizacional"'
        verbose_name = "Unidad organizacional"
        verbose_name_plural = "Unidades organizacionales"

    def __str__(self):
        return self.nombre


class Puesto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    unidad = models.ForeignKey(UnidadOrganizacional, on_delete=models.SET_NULL, db_column="unidad_id", null=True, blank=True, db_constraint=False)
    nivel = models.CharField(max_length=50, blank=True, null=True)
    salario_referencial = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"core"."puesto"'
        verbose_name = "Puesto"
        verbose_name_plural = "Puestos"

    def __str__(self):
        return self.nombre


class Turno(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    nombre = models.CharField(max_length=150)
    hora_inicio = models.TimeField(blank=True, null=True)
    hora_fin = models.TimeField(blank=True, null=True)
    dias_semana = models.JSONField(blank=True, null=True)  # e.g. [1,2,3,4,5]
    tolerancia_minutos = models.IntegerField(blank=True, null=True)
    requiere_gps = models.BooleanField(blank=True, null=True)
    requiere_foto = models.BooleanField(blank=True, null=True)
    tipo = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"asistencia"."turno"'
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"

    def __str__(self):
        return self.nombre


class Empleado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    nombres = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=150)
    documento = models.CharField(max_length=100, blank=True, null=True)
    email = models.CharField(max_length=150, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    fecha_ingreso = models.DateField(blank=True, null=True)

    unidad = models.ForeignKey(UnidadOrganizacional, on_delete=models.SET_NULL, db_column="unidad_id", null=True, blank=True, db_constraint=False)
    puesto = models.ForeignKey(Puesto, on_delete=models.SET_NULL, db_column="puesto_id", null=True, blank=True, db_constraint=False)
    manager = models.ForeignKey("self", on_delete=models.SET_NULL, db_column="manager_id", null=True, blank=True, db_constraint=False)

    foto_url = models.TextField(blank=True, null=True)
    estado = models.UUIDField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"personas"."empleado"'
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"

    def __str__(self):
        return f"{self.apellidos} {self.nombres}".strip()

    @property
    def nombre_completo(self) -> str:
        return f"{self.apellidos} {self.nombres}".strip()


class Contrato(models.Model):
    """Contrato laboral del empleado (personas.contrato)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)
    tipo = models.UUIDField(blank=True, null=True)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    salario_base = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    jornada_semanal_horas = models.IntegerField(blank=True, null=True)
    turno_base = models.ForeignKey("Turno", on_delete=models.SET_NULL, db_column="turno_base_id", null=True, blank=True, db_constraint=False)
    estado = models.UUIDField(blank=True, null=True)
    creado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"personas"."contrato"'
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"


class DocumentoEmpleado(models.Model):
    """Documento asociado a un empleado (personas.documento_empleado)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)
    tipo = models.UUIDField(blank=True, null=True)
    archivo_url = models.TextField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    cargado_el = models.DateTimeField(blank=True, null=True)
    vigente = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"personas"."documento_empleado"'
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"



class TipoEventoAsistencia(models.Model):
    """Catálogo de tipos de evento de asistencia (config.tipo_evento_asistencia)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."tipo_evento_asistencia"'
        verbose_name = "Tipo de evento asistencia"
        verbose_name_plural = "Tipos de evento asistencia"

    def __str__(self):
        return self.codigo


class FuenteMarcacion(models.Model):
    """Catálogo de fuente de marcación (config.fuente_marcacion)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."fuente_marcacion"'
        verbose_name = "Fuente de marcación"
        verbose_name_plural = "Fuentes de marcación"

    def __str__(self):
        return self.codigo


class Geocerca(models.Model):
    """Geocerca de una empresa (asistencia.geocerca)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    nombre = models.CharField(max_length=150)
    tipo = models.UUIDField(blank=True, null=True)
    coordenadas = models.JSONField(blank=True, null=True)
    activo = models.BooleanField(blank=True, null=True)
    creado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"asistencia"."geocerca"'
        verbose_name = "Geocerca"
        verbose_name_plural = "Geocercas"

    def __str__(self):
        return self.nombre


class ReglaAsistencia(models.Model):
    """Reglas globales de asistencia por empresa (asistencia.regla_asistencia)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    considera_tardanza_desde_min = models.IntegerField(blank=True, null=True)
    calculo_horas_extra = models.TextField(blank=True, null=True)
    geocerca = models.ForeignKey(Geocerca, on_delete=models.SET_NULL, db_column="geocerca_id", null=True, blank=True, db_constraint=False)
    ip_permitidas = models.JSONField(blank=True, null=True)
    creado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"asistencia"."regla_asistencia"'
        verbose_name = "Regla de asistencia"
        verbose_name_plural = "Reglas de asistencia"


class AsignacionTurno(models.Model):
    """Asignación de turnos a empleados (asistencia.asignacion_turno)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, db_column="turno_id", db_constraint=False)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    es_rotativo = models.BooleanField(blank=True, null=True)
    es_activo = models.BooleanField(blank=True, null=True)
    creado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"asistencia"."asignacion_turno"'
        verbose_name = "Asignación de turno"
        verbose_name_plural = "Asignaciones de turno"


class DispositivoEmpleado(models.Model):
    """Dispositivo registrado para un empleado (asistencia.dispositivo_empleado)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)
    tipo = models.UUIDField(blank=True, null=True)
    device_uid = models.CharField(max_length=150, blank=True, null=True)
    ultimo_uso_el = models.DateTimeField(blank=True, null=True)
    activo = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"asistencia"."dispositivo_empleado"'
        verbose_name = "Dispositivo de empleado"
        verbose_name_plural = "Dispositivos de empleado"


class EventoAsistencia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)

    tipo = models.UUIDField(blank=True, null=True)
    registrado_el = models.DateTimeField(blank=True, null=True)
    fuente = models.UUIDField(blank=True, null=True)

    gps_lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    gps_lng = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    dentro_geocerca = models.BooleanField(blank=True, null=True)
    foto_url = models.TextField(blank=True, null=True)
    ip = models.CharField(max_length=100, blank=True, null=True)
    observacion = models.TextField(blank=True, null=True)
    dispositivo_id = models.UUIDField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"asistencia"."evento_asistencia"'
        verbose_name = "Evento de asistencia"
        verbose_name_plural = "Eventos de asistencia"

    def __str__(self):
        return f"{self.empleado} @ {self.registrado_el}"


class TipoAusencia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, db_column="empresa_id", null=True, blank=True, db_constraint=False)
    nombre = models.CharField(max_length=150)
    afecta_sueldo = models.BooleanField(blank=True, null=True)
    requiere_soporte = models.BooleanField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"vacaciones"."tipo_ausencia"'
        verbose_name = "Tipo de ausencia"
        verbose_name_plural = "Tipos de ausencia"

    def __str__(self):
        return self.nombre


class SolicitudAusencia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)
    tipo_ausencia = models.ForeignKey(TipoAusencia, on_delete=models.RESTRICT, db_column="tipo_ausencia_id", db_constraint=False)

    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    dias_habiles = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    motivo = models.TextField(blank=True, null=True)
    # Estado de la solicitud (config.estado_solicitud)
    estado = models.ForeignKey(
        "EstadoSolicitud",
        on_delete=models.SET_NULL,
        db_column="estado",
        null=True,
        blank=True,
        db_constraint=False,
        related_name="solicitudes",
    )
    flujo_actual = models.IntegerField(blank=True, null=True)
    adjunto_url = models.TextField(blank=True, null=True)
    creada_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"vacaciones"."solicitud_ausencia"'
        verbose_name = "Solicitud de ausencia"
        verbose_name_plural = "Solicitudes de ausencia"

    def __str__(self):
        return f"{self.empleado} {self.fecha_inicio}→{self.fecha_fin}"


class EstadoSolicitud(models.Model):
    """Catálogo de estados para solicitudes (vacaciones / permisos / ausencias)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."estado_solicitud"'
        verbose_name = "Estado de solicitud"
        verbose_name_plural = "Estados de solicitud"

    def __str__(self):
        return self.codigo


class KPI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    codigo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    unidad = models.UUIDField(blank=True, null=True)
    origen_datos = models.CharField(max_length=50, blank=True, null=True)
    formula = models.TextField(blank=True, null=True)
    activo = models.BooleanField(blank=True, null=True)
    creado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"kpi"."kpi"'
        verbose_name = "KPI"
        verbose_name_plural = "KPIs"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# ---------------------------------------------------------------------
# Asistencia (tablas existentes en sriptTT.sql)
# ---------------------------------------------------------------------


class EstadoJornada(models.Model):
    """Catálogo de estados de jornada (config.estado_jornada)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."estado_jornada"'
        verbose_name = "Estado de jornada"
        verbose_name_plural = "Estados de jornada"

    def __str__(self):
        return self.codigo


class JornadaCalculada(models.Model):
    """Jornada calculada (asistencia.jornada_calculada)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)

    fecha = models.DateField()
    hora_primera_entrada = models.DateTimeField(blank=True, null=True)
    hora_ultima_salida = models.DateTimeField(blank=True, null=True)
    minutos_trabajados = models.IntegerField(default=0)
    minutos_tardanza = models.IntegerField(default=0)
    minutos_extra = models.IntegerField(default=0)
    estado = models.ForeignKey(EstadoJornada, on_delete=models.SET_NULL, db_column="estado", null=True, blank=True, db_constraint=False)
    detalles = models.JSONField(blank=True, null=True)
    calculado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"asistencia"."jornada_calculada"'
        verbose_name = "Jornada calculada"
        verbose_name_plural = "Jornadas calculadas"


# ---------------------------------------------------------------------
# KPI y desempeño (tablas existentes en sriptTT.sql)
# ---------------------------------------------------------------------


class UnidadKPI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."unidad_kpi"'
        verbose_name = "Unidad KPI"
        verbose_name_plural = "Unidades KPI"

    def __str__(self):
        return self.codigo


class SemaforoKPI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField()

    class Meta:
        managed = False
        db_table = '"config"."semaforo_kpi"'
        verbose_name = "Semáforo KPI"
        verbose_name_plural = "Semáforos KPI"

    def __str__(self):
        return self.codigo


class PlantillaKPI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    nombre = models.CharField(max_length=150)
    aplica_a = models.UUIDField(blank=True, null=True)
    objetivos = models.JSONField(blank=True, null=True)
    creado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"kpi"."plantilla_kpi"'
        verbose_name = "Plantilla KPI"
        verbose_name_plural = "Plantillas KPI"


class AsignacionKPI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)
    plantilla = models.ForeignKey(PlantillaKPI, on_delete=models.CASCADE, db_column="plantilla_kpi_id", db_constraint=False)
    desde = models.DateField()
    hasta = models.DateField(blank=True, null=True)
    ajustes_personalizados = models.JSONField(blank=True, null=True)
    creado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"kpi"."asignacion_kpi"'
        verbose_name = "Asignación KPI"
        verbose_name_plural = "Asignaciones KPI"


class ResultadoKPI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, db_column="kpi_id", db_constraint=False)
    periodo = models.CharField(max_length=50)
    valor = models.DecimalField(max_digits=18, decimal_places=4, blank=True, null=True)
    cumplimiento_pct = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    clasificacion = models.ForeignKey(SemaforoKPI, on_delete=models.SET_NULL, db_column="clasificacion", null=True, blank=True, db_constraint=False)
    calculado_el = models.DateTimeField(blank=True, null=True)
    fuente = models.CharField(max_length=100, blank=True, null=True)
    detalles = models.JSONField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"kpi"."resultado_kpi"'
        verbose_name = "Resultado KPI"
        verbose_name_plural = "Resultados KPI"


class EvaluacionDesempeno(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column="empresa_id", db_constraint=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column="empleado_id", db_constraint=False)
    periodo = models.CharField(max_length=50, blank=True, null=True)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    instrumento = models.JSONField(blank=True, null=True)
    puntaje_total = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    comentarios = models.TextField(blank=True, null=True)
    evaluador = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        db_column="evaluador_id",
        null=True,
        blank=True,
        related_name="evaluaciones_realizadas",
        db_constraint=False,
    )
    fecha = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"kpi"."evaluacion_desempeno"'
        verbose_name = "Evaluación de desempeño"
        verbose_name_plural = "Evaluaciones de desempeño"


class Usuario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, db_column="empresa_id", null=True, blank=True, db_constraint=False)
    email = models.CharField(max_length=150)
    phone = models.CharField(max_length=50, blank=True, null=True)
    hash_password = models.TextField(blank=True, null=True)
    mfa_habilitado = models.BooleanField(blank=True, null=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, db_column="empleado_id", null=True, blank=True, db_constraint=False)
    estado = models.UUIDField(blank=True, null=True)
    ultimo_acceso = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"seguridad"."usuario"'
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.email


class Rol(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa_id = models.UUIDField(blank=True, null=True)  # NULL = global
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"seguridad"."rol"'
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.nombre


class UsuarioRol(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column="usuario_id", db_constraint=False)
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, db_column="rol_id", db_constraint=False)
    asignado_el = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"seguridad"."usuario_rol"'
        verbose_name = "Usuario-Rol"
        verbose_name_plural = "Asignaciones Usuario-Rol"

    def __str__(self):
        return f"{self.usuario} → {self.rol}"
