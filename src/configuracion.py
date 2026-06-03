"""
configuracion.py — Configuración centralizada del sistema AAMRE.

Contiene todos los parámetros ajustables del agente sin dispersarlos
por el código fuente (principio DRY + Single Source of Truth).

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas base del proyecto
# ---------------------------------------------------------------------------

# Raíz del proyecto: sube dos niveles desde src/
_RAIZ_PROYECTO: Path = Path(__file__).resolve().parent.parent
_RAIZ_LOGS: Path = _RAIZ_PROYECTO / "logs"
_RAIZ_LOGS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Dataclasses de configuración (inmutables en tiempo de ejecución)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfigReactivo:
    """Parámetros que rigen la capa reactiva (comportamiento de emergencia).

    Attributes:
        umbral_critico: Porcentaje de uso de disco que activa emergencia.
        umbral_recuperacion: Porcentaje al que se restaura operación normal.
        intervalo_monitoreo_seg: Frecuencia de sondeo del sensor reactivo.
    """

    umbral_critico: float = 95.0
    umbral_recuperacion: float = 90.0
    intervalo_monitoreo_seg: float = 5.0


@dataclass(frozen=True)
class ConfigDeliberativo:
    """Parámetros de la capa deliberativa (planificación y mantenimiento).

    Attributes:
        intervalo_planificacion_seg: Cada cuánto segundos se ejecuta el plan.
        dias_antiguedad_logs: Días mínimos para considerar un log "antiguo".
        extensiones_temporales: Extensiones de ficheros temporales a detectar.
        nombres_cache_seguros: Patrones de directorio cache considerados seguros.
        max_archivos_por_ciclo: Límite de archivos procesados por ciclo.
    """

    intervalo_planificacion_seg: float = 30.0
    dias_antiguedad_logs: int = 7
    extensiones_temporales: tuple[str, ...] = (".tmp", ".temp", ".bak", ".swp")
    nombres_cache_seguros: tuple[str, ...] = (
        "__pycache__",
        ".pytest_cache",
        "node_modules/.cache",
        ".mypy_cache",
        ".ruff_cache",
    )
    max_archivos_por_ciclo: int = 50


@dataclass(frozen=True)
class ConfigActuadores:
    """Parámetros que controlan el comportamiento de los actuadores.

    Attributes:
        safe_mode: Si es True, simula las acciones sin eliminar nada real.
        ruta_escaneo: Directorio raíz que el agente monitorea.
        respetar_sistema: No tocar rutas del sistema operativo.
    """

    safe_mode: bool = False
    ruta_escaneo: Path = Path("C:/Prueba_AAMRE")
    respetar_sistema: bool = False


@dataclass(frozen=True)
class ConfigLogger:
    """Configuración del subsistema de registro de eventos.

    Attributes:
        ruta_log: Ruta completa al archivo de log.
        nivel: Nivel mínimo de registro ('DEBUG', 'INFO', 'WARNING', 'ERROR').
        formato: Cadena de formato para cada entrada del log.
        max_bytes: Tamaño máximo del archivo antes de rotar.
        backups: Número de archivos de respaldo a conservar.
    """

    ruta_log: Path = field(default_factory=lambda: _RAIZ_LOGS / "acciones.log")
    nivel: str = "INFO"
    formato: str = "%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s"
    fecha_formato: str = "%Y-%m-%d %H:%M:%S"
    max_bytes: int = 5 * 1024 * 1024  # 5 MB
    backups: int = 3


@dataclass(frozen=True)
class ConfigSistema:
    """Agrupador raíz que combina todas las sub-configuraciones.

    Attributes:
        reactivo: Configuración de la capa reactiva.
        deliberativo: Configuración de la capa deliberativa.
        actuadores: Configuración de los actuadores.
        logger: Configuración del logger.
        plataforma: Nombre del SO detectado automáticamente.
        version: Versión del agente.
    """

    reactivo: ConfigReactivo = field(default_factory=ConfigReactivo)
    deliberativo: ConfigDeliberativo = field(default_factory=ConfigDeliberativo)
    actuadores: ConfigActuadores = field(default_factory=ConfigActuadores)
    logger: ConfigLogger = field(default_factory=ConfigLogger)
    plataforma: str = field(default_factory=platform.system)
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        """Validaciones post-inicialización."""
        if not (0 < self.reactivo.umbral_recuperacion < self.reactivo.umbral_critico <= 100):
            raise ValueError(
                "Los umbrales deben satisfacer: 0 < recuperación < crítico ≤ 100"
            )


# ---------------------------------------------------------------------------
# Instancia global (Singleton de configuración)
# ---------------------------------------------------------------------------

#: Instancia única de configuración usada por todo el sistema.
CONFIG: ConfigSistema = ConfigSistema()
