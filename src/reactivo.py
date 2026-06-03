"""
reactivo.py — Capa Reactiva del sistema AAMRE.

Implementa el comportamiento de reflejos inmediatos del agente: monitorea
continuamente el disco y reacciona ante situaciones críticas sin necesitar
planificación deliberativa.

Analogía robótica:
    - Capa de comportamientos reactivos (Brooks, 1986)
    - Responde a estímulos directos del entorno
    - Prioridad máxima sobre las demás capas

Concurrencia: hilo dedicado con threading.Thread + threading.Event.
Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import threading
import time

from actuadores import GestorActuadores
from configuracion import CONFIG
from logger_manager import LoggerManager
from percepcion import EstadoDisco, SensorVirtual

_COMPONENTE = "REACTIVO"


class CapaReactiva:
    """Capa reactiva del agente AAMRE.

    Ejecuta en un hilo dedicado y monitorea el disco de forma continua.
    Al superar el umbral crítico suspende la capa deliberativa y ejecuta
    el protocolo de emergencia. Al recuperarse, restaura la deliberativa.

    Attributes:
        _sensor: Sensor virtual que provee métricas del disco.
        _actuadores: Gestor de actuadores para ejecutar limpiezas.
        _log: Logger singleton.
        _config: Parámetros de configuración reactiva.
        _hilo: Hilo de ejecución del monitor.
        _evento_detener: Señal para detener el hilo de forma segura.
        _evento_emergencia: Publicado cuando hay emergencia activa.
        _lock_estado: Protege el acceso al estado interno.
        _en_emergencia: Bandera de estado de emergencia actual.
        _deliberativo_suspender_cb: Callback para suspender el deliberativo.
        _deliberativo_restaurar_cb: Callback para restaurar el deliberativo.
    """

    def __init__(
        self,
        sensor: SensorVirtual,
        actuadores: GestorActuadores,
    ) -> None:
        """Inicializa la capa reactiva.

        Args:
            sensor: Sensor virtual compartido con el sistema.
            actuadores: Gestor de actuadores del sistema.
        """
        self._sensor = sensor
        self._actuadores = actuadores
        self._log = LoggerManager.obtener_instancia()
        self._config = CONFIG.reactivo

        # Sincronización de hilos
        self._hilo: threading.Thread | None = None
        self._evento_detener = threading.Event()
        self._evento_emergencia = threading.Event()
        self._lock_estado = threading.Lock()

        # Estado interno protegido por _lock_estado
        self._en_emergencia: bool = False

        # Callbacks inyectados por la capa ejecutiva
        self._deliberativo_suspender_cb: threading.Event | None = None
        self._deliberativo_restaurar_cb: threading.Event | None = None

    # ------------------------------------------------------------------
    # Inyección de dependencias (desacoplamiento entre capas)
    # ------------------------------------------------------------------

    def registrar_eventos_deliberativo(
        self,
        evento_suspender: threading.Event,
        evento_restaurar: threading.Event,
    ) -> None:
        """Registra los eventos para controlar la capa deliberativa.

        Args:
            evento_suspender: Event que suspende el deliberativo al setearlo.
            evento_restaurar: Event que restaura el deliberativo al setearlo.
        """
        self._deliberativo_suspender_cb = evento_suspender
        self._deliberativo_restaurar_cb = evento_restaurar

    # ------------------------------------------------------------------
    # Ciclo de vida del hilo
    # ------------------------------------------------------------------

    def iniciar(self) -> None:
        """Crea e inicia el hilo de monitoreo reactivo.

        El hilo es daemon para que no bloquee el cierre del proceso.
        """
        self._evento_detener.clear()
        self._hilo = threading.Thread(
            target=self._ciclo_monitoreo,
            name="Hilo-Reactivo",
            daemon=True,
        )
        self._hilo.start()
        self._log.info(_COMPONENTE, "Hilo reactivo iniciado")

    def detener(self) -> None:
        """Señaliza el hilo para que se detenga y espera su finalización.

        Timeout de 10 segundos para evitar bloqueo indefinido.
        """
        self._log.info(_COMPONENTE, "Deteniendo hilo reactivo…")
        self._evento_detener.set()
        if self._hilo and self._hilo.is_alive():
            self._hilo.join(timeout=10)
        self._log.info(_COMPONENTE, "Hilo reactivo detenido")

    @property
    def esta_en_emergencia(self) -> bool:
        """Indica si el sistema está actualmente en estado de emergencia.

        Returns:
            True si hay una emergencia activa.
        """
        with self._lock_estado:
            return self._en_emergencia

    # ------------------------------------------------------------------
    # Lógica principal del hilo
    # ------------------------------------------------------------------

    def _ciclo_monitoreo(self) -> None:
        """Bucle principal de monitoreo reactivo.

        Se ejecuta en el hilo dedicado. En cada iteración:
        1. Lee el estado del disco.
        2. Evalúa los umbrales.
        3. Actúa si es necesario.
        4. Duerme el intervalo configurado.
        """
        self._log.info(_COMPONENTE, "Ciclo de monitoreo iniciado")

        while not self._evento_detener.is_set():
            try:
                estado = self._sensor.obtener_uso_disco()
                self._log.debug(
                    _COMPONENTE,
                    f"Sondeo → {estado.porcentaje_uso:.1f}% usado",
                )
                self._evaluar_estado(estado)
            except Exception as exc:
                self._log.error(_COMPONENTE, f"Error en sondeo: {exc}")

            # Espera interrumpible para responder rápido a señal de detención
            self._evento_detener.wait(timeout=self._config.intervalo_monitoreo_seg)

        self._log.info(_COMPONENTE, "Ciclo de monitoreo finalizado")

    def _evaluar_estado(self, estado: EstadoDisco) -> None:
        """Evalúa el estado del disco y aplica la respuesta reactiva.

        Implementa la lógica de umbral crítico / recuperación:
        - Si uso ≥ umbral_critico → activar emergencia
        - Si uso < umbral_recuperacion (y estábamos en emergencia) → restaurar

        Args:
            estado: Snapshot actual del disco.
        """
        uso = estado.porcentaje_uso

        with self._lock_estado:
            en_emergencia_actual = self._en_emergencia

        if uso >= self._config.umbral_critico and not en_emergencia_actual:
            self._activar_emergencia(estado)
        elif uso < self._config.umbral_recuperacion and en_emergencia_actual:
            self._desactivar_emergencia(estado)

    def _activar_emergencia(self, estado: EstadoDisco) -> None:
        """Activa el protocolo de emergencia.

        1. Adquiere el lock de estado.
        2. Suspende la capa deliberativa.
        3. Ejecuta el protocolo de recuperación.
        4. Actualiza bandera de emergencia.

        Args:
            estado: Estado del disco que desencadenó la emergencia.
        """
        self._log.critical(
            _COMPONENTE,
            f"¡EMERGENCIA! Uso disco: {estado.porcentaje_uso:.1f}% "
            f"(umbral: {self._config.umbral_critico}%)",
        )

        with self._lock_estado:
            self._en_emergencia = True
        self._evento_emergencia.set()

        # Suspender la capa deliberativa (mayor prioridad reactiva)
        if self._deliberativo_suspender_cb:
            self._deliberativo_suspender_cb.set()
            self._log.warning(_COMPONENTE, "Capa deliberativa SUSPENDIDA")

        # Ejecutar limpieza de emergencia
        try:
            escaneo = self._sensor.escanear_entorno()
            self._log.info(_COMPONENTE, f"Escaneo de emergencia: {escaneo}")
            self._actuadores.ejecutar_recuperacion_emergencia(escaneo)
        except Exception as exc:
            self._log.error(_COMPONENTE, f"Error durante emergencia: {exc}")

    def _desactivar_emergencia(self, estado: EstadoDisco) -> None:
        """Desactiva el estado de emergencia y restaura la operación normal.

        Args:
            estado: Estado del disco que indica recuperación.
        """
        self._log.info(
            _COMPONENTE,
            f"Recuperación: uso disco {estado.porcentaje_uso:.1f}% "
            f"(bajo umbral recuperación {self._config.umbral_recuperacion}%)",
        )

        with self._lock_estado:
            self._en_emergencia = False
        self._evento_emergencia.clear()

        # Restaurar la capa deliberativa
        if self._deliberativo_restaurar_cb:
            self._deliberativo_restaurar_cb.set()
            self._log.info(_COMPONENTE, "Capa deliberativa RESTAURADA")
