"""
logger_manager.py — Singleton Logger para el sistema AAMRE.

Implementa el patrón Singleton garantizando una única instancia del logger
durante todo el ciclo de vida del agente. Soporta salida simultánea a
archivo (con rotación) y consola.

Patrón: Singleton
Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import ClassVar

from configuracion import CONFIG, ConfigLogger


class LoggerManager:
    """Singleton que gestiona el logger global del sistema AAMRE.

    Garantiza que sólo exista una instancia y que todos los módulos
    compartan el mismo handler de archivo y consola.

    Attributes:
        _instancia: Referencia a la única instancia de la clase.
        _lock: Lock para creación thread-safe de la instancia.
        _logger: Logger de Python configurado.

    Example:
        >>> lm = LoggerManager.obtener_instancia()
        >>> lm.info("REACTIVO", "Monitoreo iniciado")
    """

    _instancia: ClassVar[LoggerManager | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, config: ConfigLogger) -> None:
        """Inicializa el logger interno.

        Args:
            config: Parámetros de configuración del logger.

        Raises:
            RuntimeError: Si se intenta instanciar directamente en lugar
                de usar ``obtener_instancia()``.
        """
        self._config = config
        self._logger = self._construir_logger()

    # ------------------------------------------------------------------
    # Patrón Singleton — constructor controlado
    # ------------------------------------------------------------------

    @classmethod
    def obtener_instancia(cls) -> "LoggerManager":
        """Retorna (o crea) la única instancia del LoggerManager.

        Thread-safe gracias al double-checked locking.

        Returns:
            La instancia singleton de LoggerManager.
        """
        if cls._instancia is None:
            with cls._lock:
                if cls._instancia is None:
                    cls._instancia = cls(CONFIG.logger)
        return cls._instancia

    # ------------------------------------------------------------------
    # Construcción interna del logger
    # ------------------------------------------------------------------

    def _construir_logger(self) -> logging.Logger:
        """Configura y retorna el logger interno de Python.

        Returns:
            Logger configurado con handler de archivo rotativo y consola.
        """
        logger = logging.getLogger("AAMRE")
        logger.setLevel(getattr(logging, self._config.nivel, logging.INFO))

        # Evitar handlers duplicados si se llama más de una vez
        if logger.handlers:
            return logger

        formatter = logging.Formatter(
            fmt=self._config.formato,
            datefmt=self._config.fecha_formato,
        )

        # --- Handler de archivo con rotación ---
        ruta: Path = self._config.ruta_log
        ruta.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=str(ruta),
            maxBytes=self._config.max_bytes,
            backupCount=self._config.backups,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # --- Handler de consola ---
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    # ------------------------------------------------------------------
    # API pública de registro
    # ------------------------------------------------------------------

    def _formatear(self, componente: str, mensaje: str) -> str:
        """Prefija el componente al mensaje para identificación rápida.

        Args:
            componente: Nombre del módulo o capa que emite el mensaje.
            mensaje: Texto del evento.

        Returns:
            Cadena con formato ``[COMPONENTE] mensaje``.
        """
        return f"[{componente.upper()}] {mensaje}"

    def debug(self, componente: str, mensaje: str) -> None:
        """Registra un mensaje de nivel DEBUG.

        Args:
            componente: Nombre de la capa/módulo.
            mensaje: Descripción del evento.
        """
        self._logger.debug(self._formatear(componente, mensaje))

    def info(self, componente: str, mensaje: str) -> None:
        """Registra un mensaje informativo.

        Args:
            componente: Nombre de la capa/módulo.
            mensaje: Descripción del evento.
        """
        self._logger.info(self._formatear(componente, mensaje))

    def warning(self, componente: str, mensaje: str) -> None:
        """Registra una advertencia.

        Args:
            componente: Nombre de la capa/módulo.
            mensaje: Descripción del evento.
        """
        self._logger.warning(self._formatear(componente, mensaje))

    def error(self, componente: str, mensaje: str) -> None:
        """Registra un error.

        Args:
            componente: Nombre de la capa/módulo.
            mensaje: Descripción del evento.
        """
        self._logger.error(self._formatear(componente, mensaje))

    def critical(self, componente: str, mensaje: str) -> None:
        """Registra un error crítico.

        Args:
            componente: Nombre de la capa/módulo.
            mensaje: Descripción del evento.
        """
        self._logger.critical(self._formatear(componente, mensaje))
