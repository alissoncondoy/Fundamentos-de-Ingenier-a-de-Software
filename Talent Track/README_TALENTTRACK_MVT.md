# Talent Track (MVT Django) - Adaptación PostgreSQL

Esta versión está adaptada para trabajar con la BD **PostgreSQL** creada por `sriptTT.sql` (schemas: core, personas, asistencia, vacaciones, kpi, seguridad, etc.).

## 1) Crear BD y ejecutar el SQL

1. Crear base de datos (ej: `talenttrack`)
2. Ejecutar `sriptTT.sql` en esa BD (crea schemas, tablas y catálogos).

## 2) Configurar .env

Editar `.env` (o variables de entorno):

```
DEBUG=True
DB_ENGINE=postgresql
DB_NAME=talenttrack
DB_USERNAME=postgres
DB_PASS=tu_password
DB_HOST=127.0.0.1
DB_PORT=5432
```

## 3) Instalar dependencias

```
pip install -r requirements.txt
```

## 4) Ejecutar

> OJO: Los modelos de Talent Track tienen `managed=False`, por lo que **NO se crean migraciones** para tus tablas.

```
python manage.py runserver
```

## 5) URLs (MVT)

- `/talenttrack/` Panel
- `/talenttrack/empresas/` CRUD Empresas
- `/talenttrack/empleados/` CRUD Empleados
- `/talenttrack/asistencia/` Eventos (check-in/out)
- `/talenttrack/ausencias/` Solicitudes de ausencia/vacaciones
- `/talenttrack/kpis/` KPIs
- `/talenttrack/seguridad/usuarios/` Usuarios (tabla seguridad.usuario)
- `/talenttrack/seguridad/roles/` Roles
- `/talenttrack/seguridad/asignaciones/` Asignaciones usuario↔rol

## Seguridad (sin tablas nuevas)

- **No se usa** `django.contrib.auth`, `allauth`, `admin`, ni `sessions` (para evitar crear tablas nuevas como `auth_user` o `django_session`).
- El login valida contra **`seguridad.usuario`** (campo `hash_password`) y carga roles desde **`seguridad.usuario_rol`**.
- La sesión se maneja con **cookie firmada**.

## Ausencias

- La acción **Cancelar** NO elimina registros. Cambia el campo `estado` de `vacaciones.solicitud_ausencia` al estado catálogo
  **`config.estado_solicitud`** con `codigo='cancelado'`.
