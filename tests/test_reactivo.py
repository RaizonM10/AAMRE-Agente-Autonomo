"""
test_reactivo.py — Tests unitarios para la capa reactiva.

Verifica el comportamiento de emergencia, la coordinación de hilos y
la lógica de umbrales de la CapaReactiva.

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from actuadores import GestorActuadores
from percepcion import EstadoDisco, ResultadoEscaneo, SensorVirtual
from reactivo import CapaReactiva


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sensor_mock() -> MagicMock:
    """Sensor virtual mockeado."""
    sensor = MagicMock(spec=SensorVirtual)
    sensor.obtener_uso_disco.return_value = EstadoDisco(
        ruta=Path("/"),
        total_bytes=100 * 1024**3,
        usado_bytes=50 * 1024**3,
        libre_bytes=50 * 1024**3,
        porcentaje_uso=50.0,
    )
    sensor.escanear_entorno.return_value = ResultadoEscaneo()
    return sensor


@pytest.fixture
def actuadores_mock() -> MagicMock:
    """Gestor de actuadores mockeado."""
    actuadores = MagicMock(spec=GestorActuadores)
    actuadores.ejecutar_recuperacion_emergencia.return_value = MagicMock(
        archivos_eliminados=0,
        bytes_liberados=0,
    )
    return actuadores


@pytest.fixture
def capa_reactiva(sensor_mock: MagicMock, actuadores_mock: MagicMock) -> CapaReactiva:
    """Instancia de CapaReactiva con dependencias mockeadas."""
    return CapaReactiva(sensor=sensor_mock, actuadores=actuadores_mock)


# ---------------------------------------------------------------------------
# Tests de CapaReactiva
# ---------------------------------------------------------------------------

class TestCapaReactiva:
    def test_inicializacion(self, capa_reactiva: CapaReactiva) -> None:
        """Verifica estado inicial del objeto."""
        assert not capa_reactiva.esta_en_emergencia
        assert capa_reactiva._hilo is None

    def test_iniciar_detener(self, capa_reactiva: CapaReactiva) -> None:
        """Verifica que el hilo inicia y detiene correctamente."""
        capa_reactiva.iniciar()
        assert capa_reactiva._hilo is not None
        assert capa_reactiva._hilo.is_alive()

        capa_reactiva.detener()
        time.sleep(0.2)
        assert not capa_reactiva._hilo.is_alive()

    def test_no_emergencia_bajo_umbral(
        self,
        capa_reactiva: CapaReactiva,
        sensor_mock: MagicMock,
    ) -> None:
        """Bajo el umbral crítico no debe activarse emergencia."""
        sensor_mock.obtener_uso_disco.return_value = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100 * 1024**3,
            usado_bytes=50 * 1024**3,
            libre_bytes=50 * 1024**3,
            porcentaje_uso=50.0,
        )
        estado = sensor_mock.obtener_uso_disco()
        capa_reactiva._evaluar_estado(estado)
        assert not capa_reactiva.esta_en_emergencia

    def test_emergencia_sobre_umbral_critico(
        self,
        capa_reactiva: CapaReactiva,
        sensor_mock: MagicMock,
        actuadores_mock: MagicMock,
    ) -> None:
        """Sobre el umbral crítico debe activarse emergencia."""
        estado_critico = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100 * 1024**3,
            usado_bytes=96 * 1024**3,
            libre_bytes=4 * 1024**3,
            porcentaje_uso=96.0,
        )
        capa_reactiva._evaluar_estado(estado_critico)
        assert capa_reactiva.esta_en_emergencia
        actuadores_mock.ejecutar_recuperacion_emergencia.assert_called_once()

    def test_recuperacion_bajo_umbral_recuperacion(
        self,
        capa_reactiva: CapaReactiva,
        sensor_mock: MagicMock,
        actuadores_mock: MagicMock,
    ) -> None:
        """Cuando baja del umbral de recuperación, la emergencia debe desactivarse."""
        # Primero activar emergencia
        estado_critico = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100 * 1024**3,
            usado_bytes=96 * 1024**3,
            libre_bytes=4 * 1024**3,
            porcentaje_uso=96.0,
        )
        capa_reactiva._evaluar_estado(estado_critico)
        assert capa_reactiva.esta_en_emergencia

        # Luego simular recuperación
        estado_recuperado = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100 * 1024**3,
            usado_bytes=85 * 1024**3,
            libre_bytes=15 * 1024**3,
            porcentaje_uso=85.0,
        )
        capa_reactiva._evaluar_estado(estado_recuperado)
        assert not capa_reactiva.esta_en_emergencia

    def test_suspension_deliberativo_en_emergencia(
        self,
        capa_reactiva: CapaReactiva,
        sensor_mock: MagicMock,
        actuadores_mock: MagicMock,
    ) -> None:
        """Verifica que se setea el evento de suspensión al entrar en emergencia."""
        evento_suspender = threading.Event()
        evento_restaurar = threading.Event()
        capa_reactiva.registrar_eventos_deliberativo(evento_suspender, evento_restaurar)

        estado_critico = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100 * 1024**3,
            usado_bytes=96 * 1024**3,
            libre_bytes=4 * 1024**3,
            porcentaje_uso=96.0,
        )
        capa_reactiva._evaluar_estado(estado_critico)
        assert evento_suspender.is_set()

    def test_restauracion_deliberativo_tras_emergencia(
        self,
        capa_reactiva: CapaReactiva,
        sensor_mock: MagicMock,
        actuadores_mock: MagicMock,
    ) -> None:
        """Verifica que se setea el evento de restauración al salir de emergencia."""
        evento_suspender = threading.Event()
        evento_restaurar = threading.Event()
        capa_reactiva.registrar_eventos_deliberativo(evento_suspender, evento_restaurar)

        # Activar y desactivar emergencia
        estado_critico = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100 * 1024**3,
            usado_bytes=96 * 1024**3,
            libre_bytes=4 * 1024**3,
            porcentaje_uso=96.0,
        )
        capa_reactiva._evaluar_estado(estado_critico)

        estado_recuperado = EstadoDisco(
            ruta=Path("/"),
            total_bytes=100 * 1024**3,
            usado_bytes=85 * 1024**3,
            libre_bytes=15 * 1024**3,
            porcentaje_uso=85.0,
        )
        capa_reactiva._evaluar_estado(estado_recuperado)
        assert evento_restaurar.is_set()
