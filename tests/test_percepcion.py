"""
test_percepcion.py — Tests unitarios para el módulo de percepción.

Prueba el SensorVirtual y sus métodos de detección de archivos.

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from percepcion import EstadoDisco, ResultadoEscaneo, SensorVirtual


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def directorio_temporal(tmp_path: Path) -> Path:
    """Crea un directorio temporal con archivos de prueba."""
    (tmp_path / "archivo1.tmp").write_text("contenido temporal")
    (tmp_path / "archivo2.temp").write_text("otro temporal")
    (tmp_path / "archivo.bak").write_text("backup")

    log_antiguo = tmp_path / "viejo.log"
    log_antiguo.write_text("log antiguo")
    import os
    tiempo_antiguo = time.time() - (10 * 86_400)
    os.utime(str(log_antiguo), (tiempo_antiguo, tiempo_antiguo))

    (tmp_path / "reciente.log").write_text("log reciente")

    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "modulo.pyc").write_bytes(b"\x00" * 100)

    return tmp_path


@pytest.fixture
def sensor(directorio_temporal: Path) -> SensorVirtual:
    """Instancia un SensorVirtual apuntando al directorio temporal."""
    return SensorVirtual(ruta_escaneo=directorio_temporal)


# ---------------------------------------------------------------------------
# Tests de EstadoDisco
# ---------------------------------------------------------------------------

class TestEstadoDisco:
    def test_str_representacion(self) -> None:
        estado = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100 * 1024**3,
            usado_bytes=80 * 1024**3,
            libre_bytes=20 * 1024**3,
            porcentaje_uso=80.0,
        )
        texto = str(estado)
        assert "80.0%" in texto
        assert "Libre" in texto

    def test_timestamp_autogenerado(self) -> None:
        antes = time.time()
        estado = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100,
            usado_bytes=50,
            libre_bytes=50,
            porcentaje_uso=50.0,
        )
        despues = time.time()
        assert antes <= estado.timestamp <= despues


# ---------------------------------------------------------------------------
# Tests del SensorVirtual
# ---------------------------------------------------------------------------

class TestSensorVirtual:
    def test_obtener_uso_disco_retorna_estado(self, sensor: SensorVirtual) -> None:
        """Verifica que obtener_uso_disco retorna un EstadoDisco válido."""
        estado = sensor.obtener_uso_disco()
        assert isinstance(estado, EstadoDisco)
        assert 0 <= estado.porcentaje_uso <= 100
        assert estado.total_bytes > 0
        assert estado.libre_bytes >= 0

    def test_detectar_archivos_temporales(self, sensor: SensorVirtual) -> None:
        """Verifica que detecta archivos con extensiones temporales."""
        temporales = sensor.detectar_archivos_temporales()
        extensiones_encontradas = {a.suffix.lower() for a in temporales}
        assert ".tmp" in extensiones_encontradas or ".temp" in extensiones_encontradas

    def test_detectar_archivos_log_antiguos(self, sensor: SensorVirtual) -> None:
        """Verifica que detecta logs que superan la antigüedad configurada."""
        logs = sensor.detectar_archivos_log()
        nombres = [a.name for a in logs]
        assert "viejo.log" in nombres
        assert "reciente.log" not in nombres

    def test_detectar_cache(self, sensor: SensorVirtual) -> None:
        """Verifica que detecta directorios de caché seguros."""
        caches = sensor.detectar_cache()
        nombres = [d.name for d in caches]
        assert "__pycache__" in nombres

    def test_calcular_tamano_directorio(self) -> None:
        """Verifica que el cálculo de tamaño es positivo."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "a.txt").write_bytes(b"x" * 1000)
            (base / "b.txt").write_bytes(b"y" * 500)
            sensor_local = SensorVirtual(ruta_escaneo=base)
            tamano = sensor_local.calcular_tamano_directorio(base)
            assert tamano >= 1500

    def test_calcular_tamano_directorio_inexistente(
        self,
        sensor: SensorVirtual,
        tmp_path: Path,
    ) -> None:
        """Verifica que retorna 0 para directorios inexistentes."""
        tamano = sensor.calcular_tamano_directorio(tmp_path / "no_existe")
        assert tamano == 0

    def test_escanear_entorno_retorna_resultado_completo(self) -> None:
        """Verifica que escanear_entorno retorna un ResultadoEscaneo."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "x.tmp").write_bytes(b"t" * 100)
            sensor_local = SensorVirtual(ruta_escaneo=base)
            resultado = sensor_local.escanear_entorno()
            assert isinstance(resultado, ResultadoEscaneo)
            assert resultado.espacio_recuperable_bytes >= 0

    # ------------------------------------------------------------------
    # Tests del patrón Observer
    # ------------------------------------------------------------------

    def test_suscripcion_observer(self, sensor: SensorVirtual) -> None:
        """Verifica que el suscriptor recibe notificaciones."""
        recibidos: list[EstadoDisco] = []

        def callback(estado: EstadoDisco) -> None:
            recibidos.append(estado)

        sensor.suscribir("test", callback)
        estado_mock = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100,
            usado_bytes=50,
            libre_bytes=50,
            porcentaje_uso=50.0,
        )
        sensor.notificar(estado_mock)
        assert len(recibidos) == 1
        assert recibidos[0] is estado_mock

    def test_desuscripcion_observer(self, sensor: SensorVirtual) -> None:
        """Verifica que al desuscribirse ya no se reciben notificaciones."""
        recibidos: list[EstadoDisco] = []
        sensor.suscribir("test2", lambda e: recibidos.append(e))
        sensor.desuscribir("test2")

        estado_mock = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100,
            usado_bytes=50,
            libre_bytes=50,
            porcentaje_uso=50.0,
        )
        sensor.notificar(estado_mock)
        assert len(recibidos) == 0

    def test_callback_roto_no_bloquea_otros(self, sensor: SensorVirtual) -> None:
        """Verifica que un callback que falla no rompe el flujo."""
        recibidos: list[EstadoDisco] = []

        def callback_roto(estado: EstadoDisco) -> None:
            raise RuntimeError("callback roto")

        def callback_bueno(estado: EstadoDisco) -> None:
            recibidos.append(estado)

        sensor.suscribir("roto", callback_roto)
        sensor.suscribir("bueno", callback_bueno)

        estado_mock = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100,
            usado_bytes=50,
            libre_bytes=50,
            porcentaje_uso=50.0,
        )
        sensor.notificar(estado_mock)
        assert len(recibidos) == 1
