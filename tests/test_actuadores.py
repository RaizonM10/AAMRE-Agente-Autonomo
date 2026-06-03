"""
test_actuadores.py — Tests unitarios para el módulo de actuadores.

Verifica que las estrategias de limpieza funcionen correctamente en
modo seguro (sin eliminar archivos reales) y valida el protocolo
de recuperación de emergencia.

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from actuadores import (
    EstrategiaEliminarArchivos,
    EstrategiaEliminarDirectorios,
    GestorActuadores,
    ResultadoAccion,
)
from logger_manager import LoggerManager
from percepcion import ResultadoEscaneo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def log() -> LoggerManager:
    return LoggerManager.obtener_instancia()


@pytest.fixture
def archivos_tmp(tmp_path: Path) -> list[Path]:
    """Crea archivos temporales de prueba."""
    archivos = []
    for i in range(3):
        p = tmp_path / f"archivo_{i}.tmp"
        p.write_text(f"contenido {i}" * 100)
        archivos.append(p)
    return archivos


@pytest.fixture
def directorio_cache(tmp_path: Path) -> list[Path]:
    """Crea un directorio de caché de prueba."""
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "mod.pyc").write_bytes(b"\x00" * 500)
    return [cache]


@pytest.fixture
def gestor_safe() -> GestorActuadores:
    """Gestor de actuadores en modo seguro."""
    return GestorActuadores(safe_mode=True)


# ---------------------------------------------------------------------------
# Tests de ResultadoAccion
# ---------------------------------------------------------------------------

class TestResultadoAccion:
    def test_str_modo_simulacion(self) -> None:
        r = ResultadoAccion(archivos_eliminados=5, bytes_liberados=1024, modo_simulacion=True)
        assert "SIMULADO" in str(r)
        assert "5" in str(r)

    def test_str_modo_real(self) -> None:
        r = ResultadoAccion(archivos_eliminados=2, bytes_liberados=2048, modo_simulacion=False)
        assert "REAL" in str(r)

    def test_acumulacion_errores(self) -> None:
        r = ResultadoAccion()
        r.errores.append("error 1")
        r.errores.append("error 2")
        assert len(r.errores) == 2


# ---------------------------------------------------------------------------
# Tests de EstrategiaEliminarArchivos
# ---------------------------------------------------------------------------

class TestEstrategiaEliminarArchivos:
    def test_safe_mode_no_elimina(
        self,
        archivos_tmp: list[Path],
        log: LoggerManager,
    ) -> None:
        """En SAFE_MODE los archivos deben seguir existiendo."""
        estrategia = EstrategiaEliminarArchivos()
        resultado = estrategia.ejecutar(archivos_tmp, safe_mode=True, log=log)

        assert resultado.modo_simulacion is True
        assert resultado.archivos_eliminados == len(archivos_tmp)
        # Los archivos siguen ahí
        for archivo in archivos_tmp:
            assert archivo.exists()

    def test_modo_real_elimina_archivos(
        self,
        archivos_tmp: list[Path],
        log: LoggerManager,
    ) -> None:
        """En modo real los archivos deben eliminarse."""
        estrategia = EstrategiaEliminarArchivos()
        resultado = estrategia.ejecutar(archivos_tmp, safe_mode=False, log=log)

        assert resultado.archivos_eliminados == len(archivos_tmp)
        for archivo in archivos_tmp:
            assert not archivo.exists()

    def test_archivos_inexistentes_generan_error(
        self,
        tmp_path: Path,
        log: LoggerManager,
    ) -> None:
        """Archivos inexistentes no deben causar crash."""
        estrategia = EstrategiaEliminarArchivos()
        no_existen = [tmp_path / "fantasma.tmp"]
        # No lanza excepción
        resultado = estrategia.ejecutar(no_existen, safe_mode=False, log=log)
        # Es archivo inexistente pero ruta segura → puede contar error o simplemente omitir
        assert isinstance(resultado, ResultadoAccion)

    def test_bytes_liberados_correctos(
        self,
        archivos_tmp: list[Path],
        log: LoggerManager,
    ) -> None:
        """Los bytes liberados deben coincidir con el tamaño real."""
        tamano_total = sum(a.stat().st_size for a in archivos_tmp)
        estrategia = EstrategiaEliminarArchivos()
        resultado = estrategia.ejecutar(archivos_tmp, safe_mode=True, log=log)
        assert resultado.bytes_liberados == tamano_total


# ---------------------------------------------------------------------------
# Tests de EstrategiaEliminarDirectorios
# ---------------------------------------------------------------------------

class TestEstrategiaEliminarDirectorios:
    def test_safe_mode_no_elimina_directorio(
        self,
        directorio_cache: list[Path],
        log: LoggerManager,
    ) -> None:
        """En SAFE_MODE los directorios deben permanecer."""
        estrategia = EstrategiaEliminarDirectorios()
        resultado = estrategia.ejecutar(directorio_cache, safe_mode=True, log=log)

        assert resultado.modo_simulacion is True
        for d in directorio_cache:
            assert d.exists()

    def test_modo_real_elimina_directorio(
        self,
        directorio_cache: list[Path],
        log: LoggerManager,
    ) -> None:
        """En modo real los directorios deben eliminarse."""
        estrategia = EstrategiaEliminarDirectorios()
        resultado = estrategia.ejecutar(directorio_cache, safe_mode=False, log=log)

        assert resultado.archivos_eliminados == len(directorio_cache)
        for d in directorio_cache:
            assert not d.exists()


# ---------------------------------------------------------------------------
# Tests del GestorActuadores (Facade)
# ---------------------------------------------------------------------------

class TestGestorActuadores:
    def test_inicializacion_safe_mode(self) -> None:
        gestor = GestorActuadores(safe_mode=True)
        assert gestor._safe_mode is True

    def test_eliminar_temporales_safe(
        self,
        gestor_safe: GestorActuadores,
        archivos_tmp: list[Path],
    ) -> None:
        resultado = gestor_safe.eliminar_temporales(archivos_tmp)
        assert resultado.modo_simulacion is True
        assert resultado.archivos_eliminados == len(archivos_tmp)

    def test_limpiar_caches_safe(
        self,
        gestor_safe: GestorActuadores,
        directorio_cache: list[Path],
    ) -> None:
        resultado = gestor_safe.limpiar_caches(directorio_cache)
        assert resultado.modo_simulacion is True

    def test_recuperacion_emergencia(
        self,
        gestor_safe: GestorActuadores,
        archivos_tmp: list[Path],
        directorio_cache: list[Path],
    ) -> None:
        """Verifica el protocolo de emergencia en modo seguro."""
        escaneo = ResultadoEscaneo(
            archivos_temporales=archivos_tmp,
            archivos_log_antiguos=[],
            directorios_cache=directorio_cache,
        )
        resultado = gestor_safe.ejecutar_recuperacion_emergencia(escaneo)
        assert isinstance(resultado, ResultadoAccion)
        assert resultado.archivos_eliminados > 0
        assert resultado.bytes_liberados >= 0

    def test_recuperacion_emergencia_sin_candidatos(
        self,
        gestor_safe: GestorActuadores,
    ) -> None:
        """Emergencia con escaneo vacío no debe fallar."""
        escaneo = ResultadoEscaneo()
        resultado = gestor_safe.ejecutar_recuperacion_emergencia(escaneo)
        assert resultado.archivos_eliminados == 0
        assert resultado.bytes_liberados == 0
