"""
percepcion.py -- Sensor Virtual del sistema AAMRE.

Implementa la capa de percepcion del agente: recopila informacion del
entorno (sistema de archivos) mediante sensores virtuales que emulan los
sensores fisicos de un robot movil.

Analogia robotica:
    - Disco duro   --> entorno fisico
    - Directorios  --> regiones del entorno
    - Archivos     --> objetos del entorno
    - psutil/os    --> sensor de distancia / vision

Patron Observer: esta clase notifica cambios de estado al ejecutivo.

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import psutil

from configuracion import CONFIG
from utils import formatear_bytes, iterar_archivos


# ---------------------------------------------------------------------------
# Estructuras de datos de percepcion
# ---------------------------------------------------------------------------

@dataclass
class EstadoDisco:
    """Snapshot del estado del disco en un instante dado.

    Attributes:
        ruta: Ruta del punto de montaje analizado.
        total_bytes: Capacidad total en bytes.
        usado_bytes: Espacio utilizado en bytes.
        libre_bytes: Espacio libre en bytes.
        porcentaje_uso: Porcentaje de uso (0-100).
        timestamp: Marca temporal de la medicion.
    """

    ruta: Path
    total_bytes: int
    usado_bytes: int
    libre_bytes: int
    porcentaje_uso: float
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        return (
            f"Disco({self.ruta}): {self.porcentaje_uso:.1f}% usado | "
            f"Libre: {formatear_bytes(self.libre_bytes)} / "
            f"Total: {formatear_bytes(self.total_bytes)}"
        )


@dataclass
class ResultadoEscaneo:
    """Resultado del escaneo de archivos candidatos a limpieza.

    Attributes:
        archivos_temporales: Lista de archivos temporales detectados.
        archivos_log_antiguos: Lista de logs que superan la antiguedad.
        directorios_cache: Directorios de cache seguros a eliminar.
        espacio_recuperable_bytes: Estimacion total de bytes recuperables.
    """

    archivos_temporales: list[Path] = field(default_factory=list)
    archivos_log_antiguos: list[Path] = field(default_factory=list)
    directorios_cache: list[Path] = field(default_factory=list)
    espacio_recuperable_bytes: int = 0

    def __str__(self) -> str:
        return (
            f"Escaneo | Tmp: {len(self.archivos_temporales)} | "
            f"Logs: {len(self.archivos_log_antiguos)} | "
            f"Cache: {len(self.directorios_cache)} | "
            f"Recuperable: {formatear_bytes(self.espacio_recuperable_bytes)}"
        )


# ---------------------------------------------------------------------------
# Sensor Virtual (Observer publisher)
# ---------------------------------------------------------------------------

class SensorVirtual:
    """Sensor virtual que percibe el estado del sistema de archivos.

    Implementa el rol de Publisher del patron Observer.

    Attributes:
        _ruta_escaneo: Directorio raiz que el sensor monitorea.
        _config_deliberativo: Parametros de deteccion de archivos.
        _suscriptores: Callbacks registrados para notificacion de cambios.
    """

    def __init__(self, ruta_escaneo: Path | None = None) -> None:
        """Inicializa el sensor virtual.

        Args:
            ruta_escaneo: Ruta base de monitoreo. Por defecto usa la
                configurada en CONFIG.actuadores.ruta_escaneo.
        """
        self._ruta_escaneo: Path = ruta_escaneo or CONFIG.actuadores.ruta_escaneo
        self._config_d = CONFIG.deliberativo
        self._suscriptores: list[tuple[str, Callable[[EstadoDisco], None]]] = []

    # ------------------------------------------------------------------
    # Patron Observer -- gestion de suscriptores
    # ------------------------------------------------------------------

    def suscribir(
        self,
        nombre: str,
        callback: Callable[[EstadoDisco], None],
    ) -> None:
        """Registra un suscriptor para recibir actualizaciones de estado."""
        self._suscriptores.append((nombre, callback))

    def desuscribir(self, nombre: str) -> None:
        """Elimina un suscriptor por nombre."""
        self._suscriptores = [
            (n, cb) for (n, cb) in self._suscriptores if n != nombre
        ]

    def notificar(self, estado: EstadoDisco) -> None:
        """Notifica el estado actual a todos los suscriptores."""
        for _nombre, callback in self._suscriptores:
            try:
                callback(estado)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Sensores virtuales
    # ------------------------------------------------------------------

    def obtener_uso_disco(self, ruta: Path | None = None) -> EstadoDisco:
        """Mide el uso actual del disco para la ruta dada.

        Args:
            ruta: Punto de montaje a analizar.

        Returns:
            Snapshot EstadoDisco con las metricas actuales.
        """
        if ruta is None:
            ruta = Path("/") if os.name != "nt" else Path("C:\\")

        uso = psutil.disk_usage(str(ruta))
        return EstadoDisco(
            ruta=ruta,
            total_bytes=uso.total,
            usado_bytes=uso.used,
            libre_bytes=uso.free,
            porcentaje_uso=uso.percent,
        )

    def calcular_tamano_directorio(self, directorio: Path) -> int:
        """Calcula el tamano total de un directorio en bytes.

        Args:
            directorio: Ruta del directorio a medir.

        Returns:
            Tamano acumulado en bytes. Retorna 0 si hay errores de acceso.
        """
        total: int = 0
        try:
            for raiz, _dirs, archivos in os.walk(str(directorio), followlinks=False):
                for nombre in archivos:
                    ruta_completa = os.path.join(raiz, nombre)
                    try:
                        st = os.lstat(ruta_completa)
                        if stat.S_ISREG(st.st_mode):
                            total += st.st_size
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass
        return total

    def detectar_archivos_temporales(self) -> list[Path]:
        """Detecta archivos con extensiones temporales en la ruta de escaneo.

        Returns:
            Lista de rutas de archivos temporales encontrados.
        """
        encontrados: list[Path] = []
        extensiones = self._config_d.extensiones_temporales
        maximo = self._config_d.max_archivos_por_ciclo

        for archivo in iterar_archivos(self._ruta_escaneo, extensiones):
            if len(encontrados) >= maximo:
                break
            encontrados.append(archivo)

        return encontrados

    def detectar_archivos_log(self) -> list[Path]:
        """Detecta archivos .log que superan la antiguedad configurada.

        Returns:
            Lista de logs antiguos candidatos a eliminacion.
        """
        encontrados: list[Path] = []
        umbral_segundos: float = self._config_d.dias_antiguedad_logs * 86_400
        ahora: float = time.time()
        maximo = self._config_d.max_archivos_por_ciclo

        for archivo in iterar_archivos(self._ruta_escaneo, (".log",)):
            if len(encontrados) >= maximo:
                break
            try:
                antiguedad = ahora - archivo.stat().st_mtime
                if antiguedad > umbral_segundos:
                    encontrados.append(archivo)
            except (OSError, PermissionError):
                continue

        return encontrados

    def detectar_cache(self) -> list[Path]:
        """Detecta directorios de cache seguros para limpieza.

        Returns:
            Lista de directorios de cache candidatos a eliminacion.
        """
        encontrados: list[Path] = []
        nombres_seguros = self._config_d.nombres_cache_seguros
        maximo = self._config_d.max_archivos_por_ciclo
        raiz_str = str(self._ruta_escaneo)

        try:
            for raiz, dirs, _archivos in os.walk(raiz_str, followlinks=False):
                for nombre_dir in list(dirs):
                    if len(encontrados) >= maximo:
                        dirs.clear()
                        break
                    if any(patron in nombre_dir for patron in nombres_seguros):
                        ruta_dir = Path(raiz) / nombre_dir
                        encontrados.append(ruta_dir)
        except (OSError, PermissionError):
            pass

        return encontrados

    def escanear_entorno(self) -> ResultadoEscaneo:
        """Ejecuta un escaneo completo del entorno y calcula el espacio recuperable.

        Combina los sensores individuales en un unico resultado consolidado,
        analogo a la fusion sensorial en robotica.

        Returns:
            ResultadoEscaneo con todos los candidatos y la estimacion
            de espacio recuperable.
        """
        temporales = self.detectar_archivos_temporales()
        logs = self.detectar_archivos_log()
        caches = self.detectar_cache()

        espacio: int = 0
        for archivo in temporales + logs:
            try:
                espacio += archivo.stat().st_size
            except (OSError, PermissionError):
                pass
        for directorio in caches:
            espacio += self.calcular_tamano_directorio(directorio)

        return ResultadoEscaneo(
            archivos_temporales=temporales,
            archivos_log_antiguos=logs,
            directorios_cache=caches,
            espacio_recuperable_bytes=espacio,
        )
    def obtener_uso_disco(self, ruta: Path | None = None) -> EstadoDisco:
        """Mide el uso actual del disco de forma dinámica."""
        if ruta is None:
            # Extrae automáticamente la raíz (ej. 'D:\') de tu ruta configurada
            ruta = Path(self._ruta_escaneo.anchor)

        uso = psutil.disk_usage(str(ruta))
        return EstadoDisco(
            ruta=ruta,
            total_bytes=uso.total,
            usado_bytes=uso.used,
            libre_bytes=uso.free,
            porcentaje_uso=uso.percent,
        )
