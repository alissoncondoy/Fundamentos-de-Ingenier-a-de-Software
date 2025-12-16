from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("login/", views.TTLoginView.as_view(), name="tt_login"),
    path("logout/", views.TTLogoutView.as_view(), name="tt_logout"),

    # Dashboard
    path("", views.TT_DashboardView.as_view(), name="tt_dashboard"),

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
    path("empleados/<uuid:pk>/", views.EmpleadoDetail.as_view(), name="tt_empleado_detail"),
    path("empleados/<uuid:pk>/editar/", views.EmpleadoUpdate.as_view(), name="tt_empleado_update"),
    path("empleados/<uuid:pk>/eliminar/", views.EmpleadoDelete.as_view(), name="tt_empleado_delete"),

    # Asistencia
    path("asistencia/", views.AsistenciaList.as_view(), name="tt_asistencia_list"),
    path("asistencia/nuevo/", views.AsistenciaCreate.as_view(), name="tt_asistencia_create"),

    # Ausencias
    path("ausencias/", views.AusenciaList.as_view(), name="tt_ausencia_list"),
    path("ausencias/nuevo/", views.AusenciaCreate.as_view(), name="tt_ausencia_create"),
    path("ausencias/<uuid:pk>/cancelar/", views.AusenciaCancel.as_view(), name="tt_ausencia_cancel"),

    # KPIs
    path("kpis/", views.KPIList.as_view(), name="tt_kpi_list"),
    path("kpis/nuevo/", views.KPICreate.as_view(), name="tt_kpi_create"),
    path("kpis/<uuid:pk>/editar/", views.KPIUpdate.as_view(), name="tt_kpi_update"),
    path("kpis/<uuid:pk>/eliminar/", views.KPIDelete.as_view(), name="tt_kpi_delete"),

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
