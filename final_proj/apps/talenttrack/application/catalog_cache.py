from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _CatalogCacheState:
    estado_solicitud: dict[str, str]
    semaforo_kpi: dict[str, str]
    estado_jornada: dict[str, str]
    tipo_evento_asistencia: dict[str, str]


class CatalogCache:
    """Singleton para cachear IDs de catálogos.

    Patrón aplicado: **Singleton**.
    - Evita consultas repetidas a catálogos.
    - No usa backend de cache ni sesiones (para NO crear tablas nuevas).
    """

    _instance: "CatalogCache | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._state = _CatalogCacheState(
                estado_solicitud={},
                semaforo_kpi={},
                estado_jornada={},
                tipo_evento_asistencia={},
            )
        return cls._instance

    @property
    def state(self) -> _CatalogCacheState:
        return self._state

    def tipo_evento_asistencia(self, codigo: str):
        """Devuelve el UUID (string) del catálogo config.tipo_evento_asistencia por código.

        Se implementa aquí (y no en utils) para que el Dashboard pueda obtener los IDs
        sin depender de funciones externas y manteniendo el patrón Singleton.
        """
        if not codigo:
            return None

        cached = self._state.tipo_evento_asistencia.get(codigo)
        if cached:
            return cached

        # Import local para evitar ciclos de importación en la capa application
        from ..models import TipoEventoAsistencia  # type: ignore

        try:
            tipo_id = str(TipoEventoAsistencia.objects.only("id").get(codigo=codigo).id)
        except TipoEventoAsistencia.DoesNotExist:
            return None

        self._state.tipo_evento_asistencia[codigo] = tipo_id
        return tipo_id
