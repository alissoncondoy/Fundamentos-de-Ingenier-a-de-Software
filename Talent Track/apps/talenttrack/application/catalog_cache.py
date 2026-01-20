from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _CatalogCacheState:
    estado_solicitud: dict[str, str]
    semaforo_kpi: dict[str, str]
    estado_jornada: dict[str, str]


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
            )
        return cls._instance

    @property
    def state(self) -> _CatalogCacheState:
        return self._state
