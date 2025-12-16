from django.contrib import admin
from .models import Empresa, Empleado, EventoAsistencia, SolicitudAusencia, KPI, Usuario, Rol, UsuarioRol

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("razon_social","nombre_comercial","ruc_nit","pais","moneda")
    search_fields = ("razon_social","nombre_comercial","ruc_nit")

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ("apellidos","nombres","empresa","documento","email")
    list_filter = ("empresa",)
    search_fields = ("nombres","apellidos","documento","email")

@admin.register(EventoAsistencia)
class EventoAsistenciaAdmin(admin.ModelAdmin):
    list_display = ("registrado_el","empresa","empleado","tipo","dentro_geocerca")
    list_filter = ("empresa",)
    search_fields = ("empleado__nombres","empleado__apellidos")

@admin.register(SolicitudAusencia)
class SolicitudAusenciaAdmin(admin.ModelAdmin):
    list_display = ("empresa","empleado","fecha_inicio","fecha_fin","dias_habiles")
    list_filter = ("empresa",)
    search_fields = ("empleado__nombres","empleado__apellidos")

@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ("empresa","codigo","nombre","activo","origen_datos")
    list_filter = ("empresa","activo")
    search_fields = ("codigo","nombre")

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("empresa","email","phone","activo","ultimo_acceso")
    list_filter = ("empresa","activo")
    search_fields = ("email","phone")

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("empresa_id","nombre")
    search_fields = ("nombre",)

@admin.register(UsuarioRol)
class UsuarioRolAdmin(admin.ModelAdmin):
    list_display = ("usuario","rol","asignado_el")
