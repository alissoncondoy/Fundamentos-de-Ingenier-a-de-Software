from django.urls import path

# Views are organized as a package (apps/talenttrack/views/)
from . import views

urlpatterns = [
    # Auth
    path("login/", views.TTLoginView.as_view(), name="tt_login"),
    path("logout/", views.TTLogoutView.as_view(), name="tt_logout"),

    # Mi perfil (self-service)
    path("perfil/", views.MiPerfil.as_view(), name="tt_profile"),
    path("perfil/editar/", views.MiPerfilEdit.as_view(), name="tt_profile_edit"),
    path("perfil/password/", views.MiPerfilPassword.as_view(), name="tt_profile_password"),

    # Dashboard
    path("", views.TT_DashboardView.as_view(), name="tt_dashboard"),
    path("dashboard/data/", views.TT_DashboardDataView.as_view(), name="tt_dashboard_data"),

    # AJAX (dependent dropdowns)
    path("ajax/unidades/", views.AjaxUnidades.as_view(), name="tt_ajax_unidades"),
    path("ajax/puestos/", views.AjaxPuestos.as_view(), name="tt_ajax_puestos"),
    path("ajax/empleados/", views.AjaxEmpleados.as_view(), name="tt_ajax_empleados"),
    path("ajax/managers/", views.AjaxManagers.as_view(), name="tt_ajax_managers"),
    path("ajax/roles/", views.AjaxRoles.as_view(), name="tt_ajax_roles"),
    path("ajax/turnos/", views.AjaxTurnos.as_view(), name="tt_ajax_turnos"),

    # Empresas (SUPERADMIN)
    path("empresas/", views.EmpresaList.as_view(), name="tt_empresa_list"),
    path("empresas/nuevo/", views.EmpresaCreate.as_view(), name="tt_empresa_create"),
    path("empresas/<uuid:pk>/editar/", views.EmpresaUpdate.as_view(), name="tt_empresa_update"),
    path("empresas/<uuid:pk>/eliminar/", views.EmpresaDelete.as_view(), name="tt_empresa_delete"),

    # Administración
    path("unidades/", views.UnidadList.as_view(), name="tt_unidad_list"),
    path("unidades/nuevo/", views.UnidadCreate.as_view(), name="tt_unidad_create"),
    path("unidades/<uuid:pk>/editar/", views.UnidadUpdate.as_view(), name="tt_unidad_update"),
    path("unidades/<uuid:pk>/eliminar/", views.UnidadDelete.as_view(), name="tt_unidad_delete"),

    path("puestos/", views.PuestoList.as_view(), name="tt_puesto_list"),
    path("puestos/nuevo/", views.PuestoCreate.as_view(), name="tt_puesto_create"),
    path("puestos/<uuid:pk>/editar/", views.PuestoUpdate.as_view(), name="tt_puesto_update"),
    path("puestos/<uuid:pk>/eliminar/", views.PuestoDelete.as_view(), name="tt_puesto_delete"),

    path("turnos/", views.TurnoList.as_view(), name="tt_turno_list"),
    path("turnos/nuevo/", views.TurnoCreate.as_view(), name="tt_turno_create"),
    path("turnos/<uuid:pk>/editar/", views.TurnoUpdate.as_view(), name="tt_turno_update"),
    path("turnos/<uuid:pk>/eliminar/", views.TurnoDelete.as_view(), name="tt_turno_delete"),

    # Empleados
    path("empleados/", views.EmpleadoList.as_view(), name="tt_empleado_list"),
    path("empleados/nuevo/", views.EmpleadoCreate.as_view(), name="tt_empleado_create"),
    path("empleados/alta/", views.EmpleadoUsuarioAltaCreate.as_view(), name="tt_empleado_usuario_alta"),
    path("empleados/<uuid:pk>/", views.EmpleadoDetail.as_view(), name="tt_empleado_detail"),
    path("empleados/<uuid:pk>/editar/", views.EmpleadoUpdate.as_view(), name="tt_empleado_update"),
    path("empleados/<uuid:pk>/eliminar/", views.EmpleadoDelete.as_view(), name="tt_empleado_delete"),

    # Asistencia
    path("asistencia/", views.AsistenciaList.as_view(), name="tt_asistencia_list"),
    path("asistencia/hoy/", views.AsistenciaHoy.as_view(), name="tt_asistencia_hoy"),
    path("asistencia/marcar/", views.AsistenciaMarcar.as_view(), name="tt_asistencia_marcar"),
    # Manual attendance creation is intentionally disabled. Attendance is registered only via the
    # dedicated "Marcar asistencia" screen + button flow.

    # Configuración de asistencia (RRHH / SUPERADMIN)
    path("asistencia/geocercas/", views.GeocercaList.as_view(), name="tt_geocerca_list"),
    path("asistencia/geocercas/nuevo/", views.GeocercaCreate.as_view(), name="tt_geocerca_create"),
    path("asistencia/geocercas/<uuid:pk>/editar/", views.GeocercaUpdate.as_view(), name="tt_geocerca_update"),
    path("asistencia/geocercas/<uuid:pk>/eliminar/", views.GeocercaDelete.as_view(), name="tt_geocerca_delete"),

    path("asistencia/reglas/", views.ReglaAsistenciaList.as_view(), name="tt_regla_asistencia_list"),
    path("asistencia/reglas/nuevo/", views.ReglaAsistenciaCreate.as_view(), name="tt_regla_asistencia_create"),
    path("asistencia/reglas/<uuid:pk>/editar/", views.ReglaAsistenciaUpdate.as_view(), name="tt_regla_asistencia_update"),
    path("asistencia/reglas/<uuid:pk>/eliminar/", views.ReglaAsistenciaDelete.as_view(), name="tt_regla_asistencia_delete"),

    path("asistencia/asignaciones-turno/", views.AsignacionTurnoList.as_view(), name="tt_asignacion_turno_list"),
    path("asistencia/asignaciones-turno/nuevo/", views.AsignacionTurnoCreate.as_view(), name="tt_asignacion_turno_create"),
    path("asistencia/asignaciones-turno/<uuid:pk>/editar/", views.AsignacionTurnoUpdate.as_view(), name="tt_asignacion_turno_update"),
    path("asistencia/asignaciones-turno/<uuid:pk>/eliminar/", views.AsignacionTurnoDelete.as_view(), name="tt_asignacion_turno_delete"),

    # Ausencias
    path("ausencias/", views.AusenciaList.as_view(), name="tt_ausencia_list"),
    path("ausencias/nuevo/", views.AusenciaCreate.as_view(), name="tt_ausencia_create"),
    path("ausencias/<uuid:pk>/cancelar/", views.AusenciaCancel.as_view(), name="tt_ausencia_cancel"),
    path("ausencias/<uuid:pk>/aprobar/", views.AusenciaApprove.as_view(), name="tt_ausencia_approve"),
    path("ausencias/<uuid:pk>/rechazar/", views.AusenciaReject.as_view(), name="tt_ausencia_reject"),

    # KPIs
    path("kpis/", views.KPIList.as_view(), name="tt_kpi_list"),
    path("kpis/nuevo/", views.KPICreate.as_view(), name="tt_kpi_create"),
    path("kpis/<uuid:pk>/editar/", views.KPIUpdate.as_view(), name="tt_kpi_update"),
    path("kpis/<uuid:pk>/eliminar/", views.KPIDelete.as_view(), name="tt_kpi_delete"),

    # Evaluaciones (lectura por rol)
    path("evaluaciones/", views.EvaluacionList.as_view(), name="tt_evaluacion_list"),
    path("evaluaciones/nuevo/", views.EvaluacionCreate.as_view(), name="tt_evaluacion_create"),
    path("evaluaciones/<uuid:pk>/editar/", views.EvaluacionUpdate.as_view(), name="tt_evaluacion_update"),
    path("evaluaciones/<uuid:pk>/eliminar/", views.EvaluacionDelete.as_view(), name="tt_evaluacion_delete"),

    # Seguridad (SUPERADMIN)
    path("seguridad/usuarios/", views.UsuarioList.as_view(), name="tt_usuario_list"),
    path("seguridad/usuarios/nuevo/", views.UsuarioCreate.as_view(), name="tt_usuario_create"),
    path("seguridad/usuarios/<uuid:pk>/editar/", views.UsuarioUpdate.as_view(), name="tt_usuario_update"),
    path("seguridad/usuarios/<uuid:pk>/eliminar/", views.UsuarioDelete.as_view(), name="tt_usuario_delete"),

    path("seguridad/roles/", views.RolList.as_view(), name="tt_rol_list"),
    path("seguridad/roles/nuevo/", views.RolCreate.as_view(), name="tt_rol_create"),
    path("seguridad/roles/<uuid:pk>/editar/", views.RolUpdate.as_view(), name="tt_rol_update"),
    path("seguridad/roles/<uuid:pk>/eliminar/", views.RolDelete.as_view(), name="tt_rol_delete"),

    path("seguridad/asignaciones/", views.UsuarioRolList.as_view(), name="tt_usuariorol_list"),
    path("seguridad/asignaciones/nuevo/", views.UsuarioRolCreate.as_view(), name="tt_usuariorol_create"),
    path("seguridad/asignaciones/<uuid:pk>/eliminar/", views.UsuarioRolDelete.as_view(), name="tt_usuariorol_delete"),

    # Export CSV (with date filters)
    path("export/empleados.csv", views.ExportEmpleadosCSV.as_view(), name="tt_export_empleados_csv"),
    path("export/asistencia.csv", views.ExportAsistenciaCSV.as_view(), name="tt_export_asistencia_csv"),
    path("export/ausencias.csv", views.ExportAusenciasCSV.as_view(), name="tt_export_ausencias_csv"),
    path("export/kpis.csv", views.ExportKPIsCSV.as_view(), name="tt_export_kpis_csv"),
]
