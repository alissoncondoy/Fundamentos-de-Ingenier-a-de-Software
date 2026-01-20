-- Script completo para PostgreSQL (UUID + tablas catálogo)
-- Generado según diagrama y documento "Estructura Base de Datos"
-- Requiere PostgreSQL 12+; recomendado 14/15+
-- Uso: ejecutar como superusuario o usuario con permisos CREATE EXTENSION, CREATE SCHEMA

-- 0) Extensión para gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1) Crear schemas
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS personas;
CREATE SCHEMA IF NOT EXISTS asistencia;
CREATE SCHEMA IF NOT EXISTS vacaciones;
CREATE SCHEMA IF NOT EXISTS kpi;
CREATE SCHEMA IF NOT EXISTS seguridad;
CREATE SCHEMA IF NOT EXISTS integracion;
CREATE SCHEMA IF NOT EXISTS auditoria;
CREATE SCHEMA IF NOT EXISTS config;

-- 2) Tablas catálogo (configuración / enumerados)
-- Estado empleado, tipo contrato, tipo evento asistencia, fuente marcación, estado jornada, estado solicitud, unidad KPI, semáforo KPI, tipo unidad, tipo turno, tipo dispositivo, tipo geocerca, tipo ausencia, estado entidad (genérico)
CREATE TABLE config.estado_empleado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.tipo_contrato (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.tipo_evento_asistencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.fuente_marcacion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.estado_jornada (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.estado_solicitud (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.unidad_kpi (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.semaforo_kpi (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.tipo_unidad (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.tipo_turno (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.tipo_dispositivo (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.tipo_geocerca (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

CREATE TABLE config.tipo_ausencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL,
  afecta_sueldo BOOLEAN DEFAULT FALSE,
  requiere_soporte BOOLEAN DEFAULT FALSE
);

CREATE TABLE config.estado_generico (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(50) NOT NULL UNIQUE,
  descripcion TEXT NOT NULL
);

-- 3) Núcleo multiempresa (empresa, unidad, puesto)
CREATE TABLE core.empresa (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  razon_social VARCHAR(150) NOT NULL,
  nombre_comercial VARCHAR(150),
  ruc_nit VARCHAR(50),
  pais VARCHAR(100),
  moneda VARCHAR(10),
  logo_url TEXT,
  estado UUID REFERENCES config.estado_generico(id),
  creada_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE core.unidad_organizacional (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  nombre VARCHAR(150) NOT NULL,
  tipo UUID REFERENCES config.tipo_unidad(id),
  padre_id UUID REFERENCES core.unidad_organizacional(id) ON DELETE SET NULL,
  ubicacion VARCHAR(250),
  estado UUID REFERENCES config.estado_generico(id),
  creada_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_unidad_empresa ON core.unidad_organizacional(empresa_id);

CREATE TABLE core.puesto (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  nombre VARCHAR(150) NOT NULL,
  descripcion TEXT,
  unidad_id UUID REFERENCES core.unidad_organizacional(id) ON DELETE SET NULL,
  nivel VARCHAR(50),
  salario_referencial NUMERIC(12,2)
);

CREATE INDEX idx_puesto_empresa ON core.puesto(empresa_id);

-- 4) Personas y contratos
CREATE TABLE personas.empleado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  nombres VARCHAR(150) NOT NULL,
  apellidos VARCHAR(150) NOT NULL,
  documento VARCHAR(100),
  email VARCHAR(150),
  telefono VARCHAR(50),
  direccion TEXT,
  fecha_nacimiento DATE,
  fecha_ingreso DATE,
  unidad_id UUID REFERENCES core.unidad_organizacional(id) ON DELETE SET NULL,
  puesto_id UUID REFERENCES core.puesto(id) ON DELETE SET NULL,
  manager_id UUID REFERENCES personas.empleado(id) ON DELETE SET NULL,
  foto_url TEXT,
  estado UUID REFERENCES config.estado_empleado(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_empleado_empresa ON personas.empleado(empresa_id);
CREATE INDEX idx_empleado_doc ON personas.empleado(documento);

CREATE TABLE personas.contrato (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  tipo UUID REFERENCES config.tipo_contrato(id),
  fecha_inicio DATE,
  fecha_fin DATE,
  salario_base NUMERIC(12,2),
  jornada_semanal_horas INTEGER,
  turno_base_id UUID REFERENCES asistencia.turno(id) DEFAULT NULL,
  estado UUID REFERENCES config.estado_generico(id),
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Nota: turno table se crea más abajo (asistencia.turno). Para evitar dependencia circular,
-- definiremos la FK de turno_base_id con ALTER TABLE después de crear la tabla turno.

CREATE TABLE personas.documento_empleado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  tipo UUID, -- referencia a config.tipo_documento ? (reusar tipo_ausencia si se desea) - mantengo abierto
  archivo_url TEXT,
  observaciones TEXT,
  cargado_el TIMESTAMP WITH TIME ZONE DEFAULT now(),
  vigente BOOLEAN DEFAULT TRUE
);

-- 5) Reglas, turnos y geocercas
CREATE TABLE asistencia.turno (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  nombre VARCHAR(150) NOT NULL,
  hora_inicio TIME,
  hora_fin TIME,
  dias_semana JSONB, -- ejemplo: [1,2,3,4,5]
  tolerancia_minutos INTEGER DEFAULT 0,
  requiere_gps BOOLEAN DEFAULT FALSE,
  requiere_foto BOOLEAN DEFAULT FALSE,
  tipo UUID REFERENCES config.tipo_turno(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_turno_empresa ON asistencia.turno(empresa_id);

-- Ahora alteramos contratos para añadir FK a turno
ALTER TABLE personas.contrato
  ADD CONSTRAINT fk_contrato_turno_base FOREIGN KEY (turno_base_id) REFERENCES asistencia.turno(id) ON DELETE SET NULL;

CREATE TABLE asistencia.asignacion_turno (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  turno_id UUID NOT NULL REFERENCES asistencia.turno(id) ON DELETE CASCADE,
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE,
  es_rotativo BOOLEAN DEFAULT FALSE,
  es_activo BOOLEAN DEFAULT TRUE,
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX idx_asignacion_turno_empleado ON asistencia.asignacion_turno(empleado_id);
CREATE INDEX idx_asignacion_turno_turno ON asistencia.asignacion_turno(turno_id);

CREATE TABLE asistencia.regla_asistencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  considera_tardanza_desde_min INTEGER DEFAULT 15,
  calculo_horas_extra TEXT, -- ejemplo: 'tope_diario'/'tope_semanal' -> referencia a tabla si se desea
  geocerca_id UUID REFERENCES asistencia.geocerca(id) ON DELETE SET NULL,
  ip_permitidas JSONB,
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE asistencia.geocerca (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  nombre VARCHAR(150) NOT NULL,
  tipo UUID REFERENCES config.tipo_geocerca(id),
  coordenadas JSONB, -- formato: centro/radio o lista de puntos
  activo BOOLEAN DEFAULT TRUE,
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Dispositivo empleado
CREATE TABLE asistencia.dispositivo_empleado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  tipo UUID REFERENCES config.tipo_dispositivo(id),
  device_uid VARCHAR(150),
  ultimo_uso_el TIMESTAMP WITH TIME ZONE,
  activo BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_dispositivo_empleado_emp ON asistencia.dispositivo_empleado(empleado_id);

-- Evento de asistencia (marcaciones)
CREATE TABLE asistencia.evento_asistencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  tipo UUID REFERENCES config.tipo_evento_asistencia(id),
  registrado_el TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  fuente UUID REFERENCES config.fuente_marcacion(id),
  gps_lat NUMERIC(10,7),
  gps_lng NUMERIC(10,7),
  dentro_geocerca BOOLEAN,
  foto_url TEXT,
  ip VARCHAR(100),
  observacion TEXT,
  dispositivo_id UUID REFERENCES asistencia.dispositivo_empleado(id) ON DELETE SET NULL,
  metadata JSONB
);

-- Índices para rendimiento (tablas grandes)
CREATE INDEX idx_evento_empleado_fecha ON asistencia.evento_asistencia (empleado_id, registrado_el);
CREATE INDEX idx_evento_empresa_fecha ON asistencia.evento_asistencia (empresa_id, registrado_el);

-- Jornada calculada (resultado diario)
CREATE TABLE asistencia.jornada_calculada (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  fecha DATE NOT NULL,
  hora_primera_entrada TIMESTAMP WITH TIME ZONE,
  hora_ultima_salida TIMESTAMP WITH TIME ZONE,
  minutos_trabajados INTEGER DEFAULT 0,
  minutos_tardanza INTEGER DEFAULT 0,
  minutos_extra INTEGER DEFAULT 0,
  estado UUID REFERENCES config.estado_jornada(id),
  detalles JSONB,
  calculado_el TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE (empresa_id, empleado_id, fecha)
);

CREATE INDEX idx_jornada_empleado_fecha ON asistencia.jornada_calculada (empleado_id, fecha);
CREATE INDEX idx_jornada_empresa_fecha ON asistencia.jornada_calculada (empresa_id, fecha);

-- 6) Permisos y vacaciones
CREATE TABLE vacaciones.tipo_ausencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID REFERENCES core.empresa(id),
  nombre VARCHAR(150) NOT NULL,
  afecta_sueldo BOOLEAN DEFAULT FALSE,
  requiere_soporte BOOLEAN DEFAULT FALSE,
  descripcion TEXT
);

CREATE TABLE vacaciones.solicitud_ausencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  tipo_ausencia_id UUID NOT NULL REFERENCES vacaciones.tipo_ausencia(id) ON DELETE RESTRICT,
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE NOT NULL,
  dias_habiles NUMERIC(8,2),
  motivo TEXT,
  estado UUID REFERENCES config.estado_solicitud(id),
  flujo_actual INTEGER DEFAULT 0,
  adjunto_url TEXT,
  creada_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE vacaciones.aprobacion_ausencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  solicitud_id UUID NOT NULL REFERENCES vacaciones.solicitud_ausencia(id) ON DELETE CASCADE,
  aprobador_id UUID REFERENCES personas.empleado(id) ON DELETE SET NULL,
  accion VARCHAR(50), -- 'aprobar'/'rechazar'
  comentario TEXT,
  fecha TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE vacaciones.saldo_vacaciones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  periodo VARCHAR(20) NOT NULL, -- '2025'
  dias_asignados NUMERIC(10,2),
  dias_tomados NUMERIC(10,2),
  dias_disponibles NUMERIC(10,2),
  actualizado_el TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE (empresa_id, empleado_id, periodo)
);

-- 7) KPI y desempeño
CREATE TABLE kpi.kpi (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  codigo VARCHAR(50) NOT NULL,
  nombre VARCHAR(150) NOT NULL,
  descripcion TEXT,
  unidad UUID REFERENCES config.unidad_kpi(id),
  origen_datos VARCHAR(50), -- 'asistencia', 'evaluacion', 'mixto'
  formula TEXT, -- texto o JSON
  activo BOOLEAN DEFAULT TRUE,
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE UNIQUE INDEX uq_kpi_empresa_codigo ON kpi.kpi(empresa_id, codigo);

CREATE TABLE kpi.plantilla_kpi (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  nombre VARCHAR(150) NOT NULL,
  aplica_a UUID, -- referencia a tipo_unidad o puesto (depende diseño)
  objetivos JSONB, -- lista de {kpi_id, meta, umbral_rojo, umbral_amarillo}
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE kpi.asignacion_kpi (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  plantilla_kpi_id UUID NOT NULL REFERENCES kpi.plantilla_kpi(id) ON DELETE CASCADE,
  desde DATE NOT NULL,
  hasta DATE,
  ajustes_personalizados JSONB,
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE kpi.resultado_kpi (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  kpi_id UUID NOT NULL REFERENCES kpi.kpi(id) ON DELETE CASCADE,
  periodo VARCHAR(50) NOT NULL, -- '2025-10', '2025-S2'
  valor NUMERIC(18,4),
  cumplimiento_pct NUMERIC(5,2),
  clasificacion UUID REFERENCES config.semaforo_kpi(id),
  calculado_el TIMESTAMP WITH TIME ZONE DEFAULT now(),
  fuente VARCHAR(100),
  detalles JSONB
);

CREATE INDEX idx_resultado_kpi_empleado_periodo ON kpi.resultado_kpi (empleado_id, periodo);
CREATE INDEX idx_resultado_kpi_empresa_periodo ON kpi.resultado_kpi (empresa_id, periodo);

CREATE TABLE kpi.evaluacion_desempeno (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  periodo VARCHAR(50),
  tipo VARCHAR(50), -- auto/manager/360
  instrumento JSONB,
  puntaje_total NUMERIC(8,2),
  comentarios TEXT,
  evaluador_id UUID REFERENCES personas.empleado(id),
  fecha TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- 8) Usuarios, seguridad y roles
CREATE TABLE seguridad.usuario (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID REFERENCES core.empresa(id),
  email VARCHAR(150) NOT NULL,
  phone VARCHAR(50),
  hash_password TEXT,
  mfa_habilitado BOOLEAN DEFAULT FALSE,
  empleado_id UUID REFERENCES personas.empleado(id),
  estado UUID REFERENCES config.estado_generico(id),
  ultimo_acceso TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE (empresa_id, email)
);

CREATE TABLE seguridad.rol (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID,
  nombre VARCHAR(100) NOT NULL,
  descripcion TEXT
);

CREATE TABLE seguridad.usuario_rol (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id UUID NOT NULL REFERENCES seguridad.usuario(id) ON DELETE CASCADE,
  rol_id UUID NOT NULL REFERENCES seguridad.rol(id) ON DELETE CASCADE,
  asignado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE seguridad.permiso (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo VARCHAR(150) NOT NULL UNIQUE,
  descripcion TEXT
);

CREATE TABLE seguridad.rol_permiso (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rol_id UUID NOT NULL REFERENCES seguridad.rol(id) ON DELETE CASCADE,
  permiso_id UUID NOT NULL REFERENCES seguridad.permiso(id) ON DELETE CASCADE
);

-- Índices para usuarios
CREATE INDEX idx_usuario_empresa_email ON seguridad.usuario (empresa_id, email);

-- 9) Reportes, exportaciones e integración
CREATE TABLE integracion.reporte_programado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  nombre VARCHAR(150) NOT NULL,
  tipo VARCHAR(50), -- asistencia, kpi, ausencias
  parametros JSONB,
  frecuencia_cron VARCHAR(200),
  formato VARCHAR(20),
  destinatarios JSONB,
  activo BOOLEAN DEFAULT TRUE,
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE integracion.integracion_erp (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  erp_nombre VARCHAR(150),
  tipo VARCHAR(50), -- nomina, contabilidad
  metodo VARCHAR(50), -- API, SFTP, Archivo
  endpoint TEXT,
  credenciales JSONB,
  mapeos JSONB,
  activo BOOLEAN DEFAULT TRUE,
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE integracion.webhook (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  evento VARCHAR(100), -- check_in, permiso_aprobado, kpi_listo
  url TEXT,
  secreto VARCHAR(250),
  activo BOOLEAN DEFAULT TRUE,
  reintentos_max INTEGER DEFAULT 3,
  ultimo_envio_el TIMESTAMP WITH TIME ZONE
);

CREATE TABLE integracion.exportacion_nomina (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  periodo VARCHAR(50),
  total_horas NUMERIC(14,2),
  total_extras NUMERIC(14,2),
  observaciones TEXT,
  archivo_url TEXT,
  generado_el TIMESTAMP WITH TIME ZONE DEFAULT now(),
  estado UUID REFERENCES config.estado_generico(id)
);

-- 10) Notificaciones y auditoría
CREATE TABLE auditoria.notificacion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID REFERENCES core.empresa(id),
  usuario_id UUID REFERENCES seguridad.usuario(id),
  empleado_id UUID REFERENCES personas.empleado(id),
  canal VARCHAR(50), -- app, email, whatsapp, webhook
  titulo VARCHAR(200),
  mensaje TEXT,
  enviada_el TIMESTAMP WITH TIME ZONE,
  leida_el TIMESTAMP WITH TIME ZONE,
  accion_url TEXT,
  metadata JSONB
);

CREATE TABLE auditoria.log_auditoria (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID REFERENCES core.empresa(id),
  usuario_id UUID REFERENCES seguridad.usuario(id),
  accion VARCHAR(200),
  entidad VARCHAR(150),
  entidad_id UUID,
  detalles JSONB,
  fecha TIMESTAMP WITH TIME ZONE DEFAULT now(),
  ip VARCHAR(100)
);

CREATE INDEX idx_log_fecha ON auditoria.log_auditoria (fecha);

-- 11) Otras tablas útiles vistas en diagrama (opcional/extra que estaban en la imagen)
CREATE TABLE core.contrato (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  empleado_id UUID NOT NULL REFERENCES personas.empleado(id) ON DELETE CASCADE,
  tipo UUID REFERENCES config.tipo_contrato(id),
  fecha_inicio DATE,
  fecha_fin DATE,
  salario_base NUMERIC(12,2),
  jornada_semanal_horas INTEGER,
  estado UUID REFERENCES config.estado_generico(id),
  creado_el TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Si existen tablas como 'plantillakpi' ya cubiertas con kpi.plantilla_kpi
-- Tabla de dispositivos implicados (puede fusionarse con dispositivo_empleado)
CREATE TABLE core.dispositivo_implicado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id UUID NOT NULL REFERENCES core.empresa(id) ON DELETE CASCADE,
  tipo UUID REFERENCES config.tipo_dispositivo(id),
  device_uid VARCHAR(150),
  ultimo_uso TIMESTAMP WITH TIME ZONE,
  activo BOOLEAN DEFAULT TRUE
);

-- 12) Restricciones y triggers básicos (opcional)
-- Ejemplo: cuando se inserta evento_asistencia, podría validarse fuera en backend.
-- Dejo el trigger vacío para que lo personalices si necesitas automatizar cálculos nocturnos.

-- 13) Datos iniciales sugeridos para catálogos (ejemplo)
INSERT INTO config.estado_generico (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'activo', 'Activo'),
  (gen_random_uuid(), 'inactivo', 'Inactivo');

INSERT INTO config.estado_empleado (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'activo', 'Empleado activo'),
  (gen_random_uuid(), 'suspendido', 'Empleado suspendido'),
  (gen_random_uuid(), 'baja', 'Empleado inactivo / baja');

INSERT INTO config.tipo_contrato (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'indefinido', 'Contrato indefinido'),
  (gen_random_uuid(), 'plazo', 'Contrato a plazo'),
  (gen_random_uuid(), 'temporal', 'Contrato temporal'),
  (gen_random_uuid(), 'practicante', 'Practicante');

INSERT INTO config.tipo_evento_asistencia (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'check_in', 'Entrada / check in'),
  (gen_random_uuid(), 'check_out', 'Salida / check out'),
  (gen_random_uuid(), 'pausa_in', 'Inicio pausa'),
  (gen_random_uuid(), 'pausa_out', 'Fin pausa');

INSERT INTO config.fuente_marcacion (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'app', 'Aplicación móvil'),
  (gen_random_uuid(), 'web', 'Web'),
  (gen_random_uuid(), 'lector', 'Lector / hardware');

INSERT INTO config.estado_jornada (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'completo', 'Jornada completa'),
  (gen_random_uuid(), 'incompleto', 'Jornada incompleta'),
  (gen_random_uuid(), 'sin_registros', 'Sin registros');

INSERT INTO config.estado_solicitud (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'pendiente', 'Pendiente'),
  (gen_random_uuid(), 'aprobado', 'Aprobado'),
  (gen_random_uuid(), 'rechazado', 'Rechazado'),
  (gen_random_uuid(), 'cancelado', 'Cancelado');

INSERT INTO config.unidad_kpi (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'porcentaje', '%'),
  (gen_random_uuid(), 'puntos', 'Puntos'),
  (gen_random_uuid(), 'minutos', 'Minutos'),
  (gen_random_uuid(), 'horas', 'Horas');

INSERT INTO config.semaforo_kpi (id, codigo, descripcion) VALUES
  (gen_random_uuid(), 'verde', 'Verde'),
  (gen_random_uuid(), 'amarillo', 'Amarillo'),
  (gen_random_uuid(), 'rojo', 'Rojo');

-- 14) Índices adicionales recomendados
CREATE INDEX IF NOT EXISTS idx_evento_empleado_empresa_fecha ON asistencia.evento_asistencia (empresa_id, empleado_id, registrado_el);
CREATE INDEX IF NOT EXISTS idx_jornada_empresa_empleado_fecha ON asistencia.jornada_calculada (empresa_id, empleado_id, fecha);
CREATE INDEX IF NOT EXISTS idx_resultadokpi_empresa_kpi_periodo ON kpi.resultado_kpi (empresa_id, kpi_id, periodo);



