# Talent Track 2.0 – Plataforma de Gestión de Talento Humano

## 1. Introducción

Talent Track 2.0 es una plataforma web diseñada para optimizar la gestión de personal y talento humano en empresas de distintos tamaños. Permite controlar asistencia, registrar jornadas laborales, gestionar permisos y vacaciones, y evaluar el desempeño mediante indicadores KPI configurables.

El sistema se implementa utilizando Django como framework backend y PostgreSQL como motor de base de datos, lo que garantiza seguridad, escalabilidad y alto rendimiento. El proyecto se basa en los requerimientos funcionales y no funcionales establecidos por PuntoPymes Cia. Ltda.

---

## 2. Objetivos del Proyecto

### 2.1 Objetivo General
Desarrollar una plataforma web multiempresa que permita gestionar asistencia, permisos, vacaciones y evaluaciones de desempeño, con posibilidad de integrarse con sistemas externos mediante APIs.

### 2.2 Objetivos Específicos
- Automatizar el registro de asistencia mediante app móvil y web.
- Centralizar la información del personal (empleados, departamentos, turnos, contratos).
- Implementar un módulo de permisos y vacaciones con flujo de aprobación.
- Diseñar dashboards con métricas clave de RRHH y KPI configurables.
- Construir una API REST para integraciones con sistemas ERP.
- Garantizar seguridad y escalabilidad mediante Django y PostgreSQL.

---

## 3. Marco Teórico

### 3.1 Sistemas de Gestión del Talento Humano
Los sistemas de gestión de RRHH permiten digitalizar procesos internos como asistencia, solicitudes, control de jornadas y evaluaciones. Mejoran la eficiencia organizacional y facilitan la toma de decisiones basada en datos.

### 3.2 Control de Asistencia
El control de asistencia consiste en registrar horarios de entrada y salida, horas trabajadas y tardanzas. Las tecnologías usadas pueden incluir GPS, fotografía, geofencing, análisis de IP y dispositivos biométricos.

### 3.3 KPI (Indicadores Clave de Desempeño)
Los KPI permiten medir el desempeño laboral mediante métricas como puntualidad, productividad y cumplimiento de objetivos. Un sistema automatizado puede calcular estos indicadores integrando datos de asistencia y evaluaciones periódicas.

### 3.4 Framework Django
Django es un framework de desarrollo web basado en Python que emplea el patrón MTV (Model–Template–View). Sus principales ventajas incluyen:
- Seguridad integrada (CSRF, XSS, gestión de usuarios).
- ORM potente para trabajar con datos.
- Arquitectura modular.
- Escalabilidad para sistemas multiempresa.

### 3.5 PostgreSQL
PostgreSQL es un motor de base de datos relacional robusto, ideal para aplicaciones empresariales debido a:
- Integridad transaccional.
- Rendimiento con grandes volúmenes de datos.
- Soporte de JSON, vistas, triggers y funciones avanzadas.
- Alta compatibilidad con Django ORM.

---

## 4. Metodología del Proyecto

El proyecto sigue una metodología ágil (Scrum) organizada en fases:

- Análisis de requerimientos.
- Diseño de arquitectura, flujos y modelo de datos.
- Implementación del backend, APIs y frontend.
- Pruebas unitarias, integrales, de usabilidad y rendimiento.
- Despliegue en un servidor Linux con PostgreSQL.
- Mantenimiento y mejora continua.

---

## 5. Desarrollo del Sistema

### 5.1 Arquitectura General
- Backend: Django + Django REST Framework
- Base de datos: PostgreSQL
- Frontend: HTML, CSS, JavaScript, React (opcional)
- Aplicación móvil: consumo de API REST
- Integraciones: API REST y Webhooks
- Seguridad: autenticación por sesiones o JWT, HTTPS, MFA opcional

### 5.2 Módulos Funcionales
- Administración: empresas, unidades organizacionales, puestos, turnos y usuarios.
- Empleados: perfil, contratos, documentos e historial.
- Asistencia: check-in/out con GPS, fotografía, IP y cálculo de horas extras.
- Permisos y vacaciones: solicitudes, aprobaciones y calendario.
- Evaluaciones y KPI: plantillas, fórmulas y autoevaluaciones.
- Reportes: generación de informes en CSV, XLS y PDF.
- Integraciones: importación de empleados y conectividad con ERP.
- Seguridad y auditoría: gestión de roles, permisos y registros de actividad.

---

## 6. Modelo de Datos (Resumen)

Entidades principales del sistema:
- Empresa
- UnidadOrganizacional
- Empleado
- Asistencia
- Permiso
- Vacacion
- KPI / Evaluación
- Roles y permisos
- Logs de auditoría

---

## 7. Conclusiones

- Talent Track 2.0 permite automatizar procesos clave de la gestión del talento humano.
- Django y PostgreSQL proporcionan una plataforma segura, escalable y eficiente.
- La arquitectura permite soportar múltiples empresas y usuarios concurrentes.
- El sistema está preparado para integrarse con sistemas ERP mediante una API REST.
