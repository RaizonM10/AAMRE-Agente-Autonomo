"""
actuadores.py — Actuadores del sistema AAMRE.

Implementa las acciones físicas del agente sobre el sistema de archivos.
Cuando ``SAFE_MODE=True`` todas las acciones son simuladas (modo seguro),
cuando es ``False`` se ejecutan operaciones reales.

Analogía robótica:
    - Eliminar archivos → brazo robótico descartando objetos
    - Limpiar caché     → limpiador barriendo una región
    - Recuperación de emergencia → protocolo de evacuación

Patrón Strategy: cada método de limpieza es intercambiable.

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from configuracion import CONFIG
from logger_manager import LoggerManager
from percepcion import ResultadoEscaneo
from utils import formatear_bytes, es_ruta_segura

_COMPONENTE = "ACTUADORES"


# ---------------------------------------------------------------------------
# Resultado de una acción de limpieza
# ---------------------------------------------------------------------------

@dataclass
class ResultadoAccion:
    """Resultado detallado de una operación de actuación.

    Attributes:
        archivos_eliminados: Número de archivos/dirs procesados.
        bytes_liberados: Bytes efectivamente liberados (o simulados).
        errores: Lista de mensajes de error encontrados.
        modo_simulacion: Indica si se ejecutó en modo seguro.
    """

    archivos_eliminados: int = 0
    bytes_liberados: int = 0
    errores: list[str] = field(default_factory=list)
    modo_simulacion: bool = True

    def __str__(self) -> str:
        modo = "SIMULADO" if self.modo_simulacion else "REAL"
        return (
            f"[{modo}] Eliminados: {self.archivos_eliminados} | "
            f"Liberados: {formatear_bytes(self.bytes_liberados)} | "
            f"Errores: {len(self.errores)}"
        )


# ---------------------------------------------------------------------------
# Estrategias de limpieza (Patrón Strategy)
# ---------------------------------------------------------------------------

class EstrategiaLimpieza:
    """Clase base para estrategias de limpieza (Strategy).

    Define la interfaz común que todas las estrategias deben implementar.
    """

    def ejecutar(
        self,
        objetivos: list[Path],
        safe_mode: bool,
        log: LoggerManager,
    ) -> ResultadoAccion:
        """Ejecuta la estrategia sobre la lista de objetivos.

        Args:
            objetivos: Lista de rutas a procesar.
            safe_mode: Si True, simula la acción.
            log: Instancia del logger.

        Returns:
            Resultado detallado de la operación.

        Raises:
            NotImplementedError: Las subclases deben implementar este método.
        """
        raise NotImplementedError


class EstrategiaEliminarArchivos(EstrategiaLimpieza):
    """Estrategia para eliminar archivos individuales.

    Utiliza únicamente ``pathlib.Path.unlink()`` para la eliminación real.
    """

    def ejecutar(
        self,
        objetivos: list[Path],
        safe_mode: bool,
        log: LoggerManager,
    ) -> ResultadoAccion:
        """Elimina (o simula eliminar) cada archivo en la lista.

        Args:
            objetivos: Archivos a eliminar.
            safe_mode: Si True, solo registra la acción.
            log: Instancia del logger.

        Returns:
            Resultado con conteo de archivos y bytes procesados.
        """
        resultado = ResultadoAccion(modo_simulacion=safe_mode)

        for archivo in objetivos:
            if not es_ruta_segura(archivo, CONFIG.actuadores.respetar_sistema):
                log.warning(_COMPONENTE, f"Ruta insegura omitida: {archivo}")
                continue
            try:
                tamano = archivo.stat().st_size
                if safe_mode:
                    log.info(_COMPONENTE, f"[SIMULADO] Eliminar archivo: {archivo} ({formatear_bytes(tamano)})")
                else:
                    archivo.unlink(missing_ok=True)
                    log.info(_COMPONENTE, f"Archivo eliminado: {archivo} ({formatear_bytes(tamano)})")
                resultado.archivos_eliminados += 1
                resultado.bytes_liberados += tamano
            except (OSError, PermissionError) as exc:
                msg = f"Error al eliminar {archivo}: {exc}"
                log.error(_COMPONENTE, msg)
                resultado.errores.append(msg)

        return resultado


class EstrategiaEliminarDirectorios(EstrategiaLimpieza):
    """Estrategia para eliminar árboles de directorios completos.

    Utiliza únicamente ``shutil.rmtree()`` para la eliminación real.
    """

    def ejecutar(
        self,
        objetivos: list[Path],
        safe_mode: bool,
        log: LoggerManager,
    ) -> ResultadoAccion:
        """Elimina (o simula eliminar) cada directorio en la lista.

        Args:
            objetivos: Directorios a eliminar recursivamente.
            safe_mode: Si True, solo registra la acción.
            log: Instancia del logger.

        Returns:
            Resultado con conteo de directorios y bytes procesados.
        """
        resultado = ResultadoAccion(modo_simulacion=safe_mode)

        for directorio in objetivos:
            if not es_ruta_segura(directorio, CONFIG.actuadores.respetar_sistema):
                log.warning(_COMPONENTE, f"Directorio inseguro omitido: {directorio}")
                continue
            try:
                # Calcular tamaño antes de eliminar
                tamano: int = sum(
                    f.stat().st_size
                    for f in directorio.rglob("*")
                    if f.is_file()
                )
                if safe_mode:
                    log.info(
                        _COMPONENTE,
                        f"[SIMULADO] Eliminar directorio: {directorio} ({formatear_bytes(tamano)})",
                    )
                else:
                    shutil.rmtree(directorio, ignore_errors=True)
                    log.info(
                        _COMPONENTE,
                        f"Directorio eliminado: {directorio} ({formatear_bytes(tamano)})",
                    )
                resultado.archivos_eliminados += 1
                resultado.bytes_liberados += tamano
            except (OSError, PermissionError) as exc:
                msg = f"Error al eliminar directorio {directorio}: {exc}"
                log.error(_COMPONENTE, msg)
                resultado.errores.append(msg)

        return resultado


# ---------------------------------------------------------------------------
# Facade de Actuadores
# ---------------------------------------------------------------------------

class GestorActuadores:
    """Facade que unifica el acceso a todas las estrategias de limpieza.

    Coordina las estrategias (Strategy) y expone una API de alto nivel
    que el ejecutivo y la capa reactiva utilizan.

    Attributes:
        _safe_mode: Modo seguro de operación.
        _log: Instancia del logger singleton.
        _estrategia_archivos: Estrategia para eliminar archivos.
        _estrategia_directorios: Estrategia para eliminar directorios.
    """

    def __init__(self, safe_mode: bool | None = None) -> None:
        """Inicializa el gestor de actuadores.

        Args:
            safe_mode: Sobreescribe el valor de ``CONFIG.actuadores.safe_mode``
                si se provee explícitamente.
        """
        self._safe_mode: bool = (
            safe_mode if safe_mode is not None else CONFIG.actuadores.safe_mode
        )
        self._log = LoggerManager.obtener_instancia()
        self._estrategia_archivos = EstrategiaEliminarArchivos()
        self._estrategia_directorios = EstrategiaEliminarDirectorios()

    # ------------------------------------------------------------------
    # Acciones de mantenimiento preventivo (capa deliberativa)
    # ------------------------------------------------------------------

    def eliminar_temporales(self, archivos: list[Path]) -> ResultadoAccion:
        """Elimina archivos temporales detectados por el sensor.

        Args:
            archivos: Lista de archivos temporales a procesar.

        Returns:
            Resultado de la operación.
        """
        self._log.info(_COMPONENTE, f"Iniciando eliminación de {len(archivos)} archivos temporales")
        resultado = self._estrategia_archivos.ejecutar(archivos, self._safe_mode, self._log)
        self._log.info(_COMPONENTE, str(resultado))
        return resultado

    def eliminar_logs_antiguos(self, archivos: list[Path]) -> ResultadoAccion:
        """Elimina logs que superan la antigüedad configurada.

        Args:
            archivos: Lista de archivos de log a eliminar.

        Returns:
            Resultado de la operación.
        """
        self._log.info(_COMPONENTE, f"Iniciando eliminación de {len(archivos)} logs antiguos")
        resultado = self._estrategia_archivos.ejecutar(archivos, self._safe_mode, self._log)
        self._log.info(_COMPONENTE, str(resultado))
        return resultado

    def limpiar_caches(self, directorios: list[Path]) -> ResultadoAccion:
        """Elimina directorios de caché seguros.

        Args:
            directorios: Lista de directorios de caché a eliminar.

        Returns:
            Resultado de la operación.
        """
        self._log.info(_COMPONENTE, f"Iniciando limpieza de {len(directorios)} cachés")
        resultado = self._estrategia_directorios.ejecutar(directorios, self._safe_mode, self._log)
        self._log.info(_COMPONENTE, str(resultado))
        return resultado

    # ------------------------------------------------------------------
    # Protocolo de emergencia (capa reactiva)
    # ------------------------------------------------------------------

    def ejecutar_recuperacion_emergencia(
        self,
        escaneo: ResultadoEscaneo,
    ) -> ResultadoAccion:
        """Ejecuta el protocolo de emergencia cuando el disco es crítico.

        Combina la eliminación de temporales, logs y cachés en una única
        operación de alta prioridad. Prioriza la acción más rápida
        (archivos temporales) sobre la más costosa (cachés).

        Args:
            escaneo: Resultado del escaneo del sensor virtual.

        Returns:
            Resultado acumulado de todas las sub-operaciones.
        """
        self._log.critical(_COMPONENTE, "=== PROTOCOLO DE EMERGENCIA ACTIVADO ===")

        resultado_total = ResultadoAccion(modo_simulacion=self._safe_mode)

        # Paso 1: Eliminar archivos temporales (más rápido)
        if escaneo.archivos_temporales:
            r = self._estrategia_archivos.ejecutar(
                escaneo.archivos_temporales, self._safe_mode, self._log
            )
            resultado_total.archivos_eliminados += r.archivos_eliminados
            resultado_total.bytes_liberados += r.bytes_liberados
            resultado_total.errores.extend(r.errores)

        # Paso 2: Eliminar logs antiguos
        if escaneo.archivos_log_antiguos:
            r = self._estrategia_archivos.ejecutar(
                escaneo.archivos_log_antiguos, self._safe_mode, self._log
            )
            resultado_total.archivos_eliminados += r.archivos_eliminados
            resultado_total.bytes_liberados += r.bytes_liberados
            resultado_total.errores.extend(r.errores)

        # Paso 3: Limpiar cachés (más lento, al final)
        if escaneo.directorios_cache:
            r = self._estrategia_directorios.ejecutar(
                escaneo.directorios_cache, self._safe_mode, self._log
            )
            resultado_total.archivos_eliminados += r.archivos_eliminados
            resultado_total.bytes_liberados += r.bytes_liberados
            resultado_total.errores.extend(r.errores)

        self._log.critical(
            _COMPONENTE,
            f"Emergencia completada: {resultado_total}",
        )
        return resultado_total
