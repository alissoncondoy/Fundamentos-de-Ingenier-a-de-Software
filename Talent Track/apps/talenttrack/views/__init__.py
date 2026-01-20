"""Public view exports.

`apps.talenttrack.urls` imports from this package.

Implementation lives under `apps.talenttrack.presentation.views`.
This package is kept as a stable import surface for urls.py.
"""

from ..presentation.views.auth import TTLoginView, TTLogoutView
from ..presentation.views.dashboard import TT_DashboardView, TT_DashboardDataView
from ..presentation.views.ajax import AjaxUnidades, AjaxPuestos, AjaxEmpleados, AjaxManagers, AjaxRoles
from ..presentation.views.companies import EmpresaList, EmpresaCreate, EmpresaUpdate, EmpresaDelete
from ..presentation.views.admin import (
    UnidadList, UnidadCreate, UnidadUpdate, UnidadDelete,
    PuestoList, PuestoCreate, PuestoUpdate, PuestoDelete,
    TurnoList, TurnoCreate, TurnoUpdate, TurnoDelete,
)
from ..presentation.views.employees import (
    EmpleadoList, EmpleadoUsuarioAltaCreate, EmpleadoDetail,
    EmpleadoCreate, EmpleadoUpdate, EmpleadoDelete,
)
from ..presentation.views.attendance import AsistenciaHoy, AsistenciaMarcar, AsistenciaList
from ..presentation.views.attendance_admin import (
    GeocercaList, GeocercaCreate, GeocercaUpdate, GeocercaDelete,
    ReglaAsistenciaList, ReglaAsistenciaCreate, ReglaAsistenciaUpdate, ReglaAsistenciaDelete,
    AsignacionTurnoList, AsignacionTurnoCreate, AsignacionTurnoUpdate, AsignacionTurnoDelete,
)
from ..presentation.views.absences import AusenciaList, AusenciaCreate, AusenciaCancel, AusenciaApprove, AusenciaReject
from ..presentation.views.kpis import KPIList, KPICreate, KPIUpdate, KPIDelete
from ..presentation.views.evaluations import EvaluacionList
from ..presentation.views.security import (
    UsuarioList, UsuarioCreate, UsuarioUpdate, UsuarioDelete,
    RolList, RolCreate, RolUpdate, RolDelete,
    UsuarioRolList, UsuarioRolCreate, UsuarioRolDelete,
)
from ..presentation.views.exports import ExportEmpleadosCSV, ExportAsistenciaCSV, ExportAusenciasCSV, ExportKPIsCSV
