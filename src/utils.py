"""
utils.py — Utilidades transversales del sistema AAMRE.

Funciones auxiliares reutilizadas por múltiples módulos: formateo de
tamaños, validación de rutas, iteración de archivos y helpers varios.
Implementado con os.walk para máxima compatibilidad multiplataforma.

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import os
import platform
import stat
import time
from pathlib import Path
from typing import Generator


# ---------------------------------------------------------------------------
# Formateo de tamaños
# ---------------------------------------------------------------------------

def formatear_bytes(num_bytes: int | float) -> str:
    """Convierte bytes a una representación legible (KB, MB, GB…).

    Args:
        num_bytes: Cantidad de bytes a formatear.

    Returns:
        Cadena con unidad apropiada, e.g. ``"12.34 MB"``.

    Example:
        >>> formatear_bytes(1_048_576)
        '1.00 MB'
    """
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.2f} {unidad}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


# ---------------------------------------------------------------------------
# Validación de rutas
# ---------------------------------------------------------------------------

def es_ruta_segura(ruta: Path, respetar_sistema: bool = True) -> bool:
    """Verifica que la ruta sea segura para operaciones de limpieza.

    Args:
        ruta: Ruta a evaluar.
        respetar_sistema: Si True, rechaza rutas del sistema operativo.

    Returns:
        True si la ruta es segura para operar, False en caso contrario.
    """
    if not ruta.exists():
        return False

    if not respetar_sistema:
        return True

    sistema = platform.system()
    rutas_sistema: list[Path] = []

    if sistema == "Windows":
        rutas_sistema = [
            Path("C:/Windows"),
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
            Path("C:/ProgramData"),
        ]
    elif sistema in ("Linux", "Darwin"):
        rutas_sistema = [
            Path("/bin"),
            Path("/sbin"),
            Path("/usr"),
            Path("/etc"),
            Path("/lib"),
            Path("/lib64"),
            Path("/boot"),
            Path("/dev"),
            Path("/proc"),
            Path("/sys"),
        ]

    try:
        ruta_resuelta = ruta.resolve()
        for ruta_sys in rutas_sistema:
            if ruta_resuelta.is_relative_to(ruta_sys.resolve()):
                return False
    except (OSError, ValueError):
        return False

    return True


# ---------------------------------------------------------------------------
# Iteración de archivos (usa os.walk para máxima compatibilidad)
# ---------------------------------------------------------------------------

def iterar_archivos(
    directorio: Path,
    extensiones: tuple[str, ...],
    max_profundidad: int = 10,
) -> Generator[Path, None, None]:
    """Genera archivos bajo ``directorio`` con las extensiones indicadas.

    Implementado con ``os.walk`` + ``os.lstat`` para garantizar
    compatibilidad multiplataforma sin depender de pathlib.rglob.

    Args:
        directorio: Directorio raíz de búsqueda.
        extensiones: Tupla de extensiones (con punto, e.g. ``".tmp"``).
        max_profundidad: Profundidad máxima de recursión.

    Yields:
        Rutas de archivos que coinciden con las extensiones.

    Example:
        >>> list(iterar_archivos(Path("/tmp"), (".tmp",), max_profundidad=3))
    """
    if not directorio.is_dir():
        return

    raiz_str = str(directorio)
    sep = os.sep
    profundidad_base = raiz_str.count(sep)

    try:
        for raiz, dirs, archivos in os.walk(raiz_str, followlinks=False):
            profundidad_actual = raiz.count(sep) - profundidad_base
            if profundidad_actual >= max_profundidad:
                dirs.clear()
                continue
            for nombre in archivos:
                ruta_completa = os.path.join(raiz, nombre)
                try:
                    st = os.lstat(ruta_completa)
                    if not stat.S_ISREG(st.st_mode):
                        continue
                    _, ext = os.path.splitext(nombre)
                    if ext.lower() in extensiones:
                        yield Path(ruta_completa)
                except (OSError, ValueError):
                    continue
    except (OSError, PermissionError):
        return


# ---------------------------------------------------------------------------
# Medición de tiempo
# ---------------------------------------------------------------------------

class CronometroContexto:
    """Context manager para medir el tiempo de ejecución de un bloque.

    Example:
        >>> with CronometroContexto() as c:
        ...     time.sleep(0.1)
        >>> print(c.elapsed_seg)
    """

    def __init__(self) -> None:
        self._inicio: float = 0.0
        self.elapsed_seg: float = 0.0

    def __enter__(self) -> "CronometroContexto":
        self._inicio = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed_seg = time.perf_counter() - self._inicio


# ---------------------------------------------------------------------------
# Helpers de plataforma
# ---------------------------------------------------------------------------

def obtener_separador_path() -> str:
    """Retorna el separador de ruta del sistema operativo actual.

    Returns:
        ``"\\"`` en Windows, ``"/"`` en Linux/macOS.
    """
    return "\\" if platform.system() == "Windows" else "/"


def es_windows() -> bool:
    """Indica si el sistema operativo es Windows.

    Returns:
        True si se ejecuta en Windows.
    """
    return platform.system() == "Windows"
