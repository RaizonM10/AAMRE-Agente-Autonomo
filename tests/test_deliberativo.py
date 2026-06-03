"""
test_deliberativo.py — Tests unitarios para la capa deliberativa.

Verifica la planificación de tareas, la suspensión/restauración por
emergencia y la generación correcta de planes de mantenimiento.

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from actuadores import GestorActuadores, ResultadoAccion
from deliberativo import CapaDeliberativa
from percepcion import ResultadoEscaneo, SensorVirtual


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sensor_mock(tmp_path: Path) -> MagicMock:
    sensor = MagicMock(spec=SensorVirtual)
    sensor.escanear_entorno.return_value = ResultadoEscaneo(
        archivos_temporales=[tmp_path / "a.tmp"],
        archivos_log_antiguos=[tmp_path / "b.log"],
        directorios_cache=[tmp_path / "__pycache__"],
        espacio_recuperable_bytes=1024,
    )
    return sensor


@pytest.fixture
def actuadores_mock() -> MagicMock:
    actuadores = MagicMock(spec=GestorActuadores)
    actuadores.eliminar_temporales.return_value = ResultadoAccion(archivos_eliminados=1)
    actuadores.eliminar_logs_antiguos.return_value = ResultadoAccion(archivos_eliminados=1)
    actuadores.limpiar_caches.return_value = ResultadoAccion(archivos_eliminados=1)
    return actuadores


@pytest.fixture
def capa_deliberativa(
    sensor_mock: MagicMock,
    actuadores_mock: MagicMock,
) -> CapaDeliberativa:
    return CapaDeliberativa(sensor=sensor_mock, actuadores=actuadores_mock)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCapaDeliberativa:
    def test_inicializacion(self, capa_deliberativa: CapaDeliberativa) -> None:
        assert capa_deliberativa.ciclos_completados == 0
        assert capa_deliberativa._hilo is None

    def test_iniciar_detener(self, capa_deliberativa: CapaDeliberativa) -> None:
        capa_deliberativa.iniciar()
        assert capa_deliberativa._hilo is not None
        assert capa_deliberativa._hilo.is_alive()
        capa_deliberativa.detener()
        time.sleep(0.2)
        assert not capa_deliberativa._hilo.is_alive()

    def test_ciclo_mantenimiento_ejecuta_plan(
        self,
        capa_deliberativa: CapaDeliberativa,
        actuadores_mock: MagicMock,
    ) -> None:
        """Verifica que el ciclo llama a los tres actuadores."""
        capa_deliberativa._ciclo_mantenimiento()
        assert capa_deliberativa.ciclos_completados == 1
        actuadores_mock.eliminar_temporales.assert_called_once()
        actuadores_mock.eliminar_logs_antiguos.assert_called_once()
        actuadores_mock.limpiar_caches.assert_called_once()

    def test_ciclo_sin_candidatos_no_actua(
        self,
        sensor_mock: MagicMock,
        actuadores_mock: MagicMock,
        capa_deliberativa: CapaDeliberativa,
    ) -> None:
        """Con escaneo vacío, no se deben llamar actuadores."""
        sensor_mock.escanear_entorno.return_value = ResultadoEscaneo()
        capa_deliberativa._ciclo_mantenimiento()
        actuadores_mock.eliminar_temporales.assert_not_called()
        actuadores_mock.eliminar_logs_antiguos.assert_not_called()
        actuadores_mock.limpiar_caches.assert_not_called()

    def test_generar_plan_con_todo(
        self,
        capa_deliberativa: CapaDeliberativa,
        sensor_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Con todos los tipos de candidatos, el plan debe tener 3 acciones."""
        escaneo = ResultadoEscaneo(
            archivos_temporales=[tmp_path / "x.tmp"],
            archivos_log_antiguos=[tmp_path / "y.log"],
            directorios_cache=[tmp_path / "__pycache__"],
        )
        plan = capa_deliberativa._generar_plan(escaneo)
        assert len(plan) == 3

    def test_generar_plan_parcial(
        self,
        capa_deliberativa: CapaDeliberativa,
        tmp_path: Path,
    ) -> None:
        """Solo con temporales, el plan debe tener 1 acción."""
        escaneo = ResultadoEscaneo(
            archivos_temporales=[tmp_path / "x.tmp"],
        )
        plan = capa_deliberativa._generar_plan(escaneo)
        assert len(plan) == 1

    def test_eventos_suspension_restauracion(
        self,
        capa_deliberativa: CapaDeliberativa,
    ) -> None:
        """Verifica que los eventos son accesibles externamente."""
        assert isinstance(capa_deliberativa.evento_suspender, threading.Event)
        assert isinstance(capa_deliberativa.evento_restaurar, threading.Event)

    def test_contador_ciclos(
        self,
        capa_deliberativa: CapaDeliberativa,
    ) -> None:
        """Verifica que el contador incrementa por cada ciclo."""
        for i in range(3):
            capa_deliberativa._ciclo_mantenimiento()
        assert capa_deliberativa.ciclos_completados == 3

    def test_error_en_escaneo_no_propaga(
        self,
        capa_deliberativa: CapaDeliberativa,
        sensor_mock: MagicMock,
    ) -> None:
        """Un error en el sensor no debe propagar excepción al ciclo."""
        sensor_mock.escanear_entorno.side_effect = OSError("Error de lectura")
        # No debe lanzar excepción
        capa_deliberativa._ciclo_mantenimiento()
