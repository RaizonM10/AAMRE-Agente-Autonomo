"""
ejecutivo.py — Capa Ejecutiva del sistema AAMRE.

Coordina las capas reactiva y deliberativa, resuelve conflictos mediante
arbitraje de prioridades y gestiona el ciclo de vida completo del agente.

Analogía robótica:
    - Capa ejecutiva de la Arquitectura 3T (Bonasso et al., 1997)
    - Árbitro entre comportamientos reactivos y planificación deliberativa
    - Gestor del bus de comunicaciones entre capas

Patrón Facade: expone una API simple para iniciar/detener el agente.
Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import signal
import sys
import threading
import time

from actuadores import GestorActuadores
from configuracion import CONFIG
from deliberativo import CapaDeliberativa
from logger_manager import LoggerManager
from percepcion import SensorVirtual
from reactivo import CapaReactiva

# Importación para telemetría
try:
    from telegram_bot import enviar_mensaje_normal
except ImportError:
    enviar_mensaje_normal = lambda msg: None

_COMPONENTE = "EJECUTIVO"


class AgenteAAMRE:
    """Agente principal que implementa la Arquitectura Híbrida 3T.

    Orquesta las tres capas del sistema:
    - **Reactiva**: respuesta inmediata a emergencias.
    - **Deliberativa**: planificación preventiva periódica.
    - **Ejecutiva**: coordinación y arbitraje (esta clase).

    Implementa el patrón Facade para simplificar el uso externo.

    Attributes:
        _log: Logger singleton.
        _sensor: Sensor virtual compartido.
        _actuadores: Gestor de actuadores compartido.
        _reactivo: Capa reactiva.
        _deliberativo: Capa deliberativa.
        _hilo_ejecutivo: Hilo de supervisión ejecutiva.
        _evento_detener: Señal global de detención.
        _lock_arbitraje: Lock para operaciones de arbitraje.
        _activo: Bandera de estado del agente.
    """

    def __init__(self, safe_mode: bool | None = None) -> None:
        """Construye el agente y todas sus capas.

        Args:
            safe_mode: Si se provee, sobreescribe el valor de CONFIG.
                Si es None, usa el valor de ``CONFIG.actuadores.safe_mode``.
        """
        self._log = LoggerManager.obtener_instancia()

        # Construcción de componentes compartidos
        self._sensor = SensorVirtual()
        self._actuadores = GestorActuadores(safe_mode=safe_mode)

        # Construcción de capas
        self._deliberativo = CapaDeliberativa(self._sensor, self._actuadores)
        self._reactivo = CapaReactiva(self._sensor, self._actuadores)

        # Cableado de eventos inter-capa
        self._cablear_eventos()

        # Sincronización ejecutiva
        self._hilo_ejecutivo: threading.Thread | None = None
        self._evento_detener = threading.Event()
        self._lock_arbitraje = threading.Lock()
        self._activo: bool = False

        # Banderas Anti-Spam para notificaciones
        self._alerta_80_enviada = False
        self._emergencia_95_enviada = False

        # Suscripción del sensor al ejecutivo (patrón Observer)
        self._sensor.suscribir("EJECUTIVO", self._on_estado_disco)

    # ------------------------------------------------------------------
    # Cableado de eventos entre capas
    # ------------------------------------------------------------------

    def _cablear_eventos(self) -> None:
        """Conecta los eventos de comunicación entre capas reactiva y deliberativa.

        La reactiva controla la suspensión/restauración de la deliberativa
        a través de threading.Event, garantizando prioridad reactiva.
        """
        self._reactivo.registrar_eventos_deliberativo(
            evento_suspender=self._deliberativo.evento_suspender,
            evento_restaurar=self._deliberativo.evento_restaurar,
        )
        self._log.info(_COMPONENTE, "Eventos inter-capa configurados")

    # ------------------------------------------------------------------
    # Observer: callback del sensor
    # ------------------------------------------------------------------

    def _on_estado_disco(self, estado) -> None:  # type: ignore[no-untyped-def]
        """Callback invocado por el sensor cuando hay una actualización.

        Registra el estado en el log ejecutivo para trazabilidad y 
        ejecuta la lógica de control de flujo (Alerta vs Autonomía).

        Args:
            estado: Snapshot ``EstadoDisco`` recibido del sensor.
        """
        uso = estado.porcentaje_uso
        umbral_critico = CONFIG.reactivo.umbral_critico
        umbral_alerta = getattr(CONFIG.reactivo, 'umbral_alerta', 80.0)

        # NIVEL 2: EMERGENCIA AUTÓNOMA (>= 95%)
        if uso >= umbral_critico:
            if not self._emergencia_95_enviada:
                self._log.warning(_COMPONENTE, f"🚨 USO CRÍTICO ({uso:.1f}%). Protocolo Autónomo Iniciado.")
                enviar_mensaje_normal(f"🚨 *Protocolo Autónomo:* Disco al {uso:.1f}%. Riesgo de colapso. Iniciando limpieza forzada automáticamente...")
                self._actuadores.eliminar_temporales()
                self._emergencia_95_enviada = True

        # NIVEL 1: ALERTA (80% - 94%)
        elif uso >= umbral_alerta:
            self._emergencia_95_enviada = False  # Resetea emergencia si el disco bajó del 95%
            if not self._alerta_80_enviada:
                self._log.info(_COMPONENTE, f"⚠️ Nivel de alerta alcanzado ({uso:.1f}%). Solicitando intervención.")
                enviar_mensaje_normal(f"⚠️ *Alerta AAMRE:* Disco al {uso:.1f}%. El sistema se acerca al límite. ¿Deseas liberar espacio ahora? Responde /limpiar")
                self._alerta_80_enviada = True

        # ESTADO NORMAL (< 80%)
        else:
            self._alerta_80_enviada = False
            self._emergencia_95_enviada = False

        self._log.debug(_COMPONENTE, f"Estado recibido: {estado}")

    # ------------------------------------------------------------------
    # Ciclo de vida del agente
    # ------------------------------------------------------------------

    def iniciar(self) -> None:
        """Inicia el agente completo: todas las capas y el hilo ejecutivo.

        Registra manejadores de señal para cierre limpio (SIGINT / SIGTERM).

        Raises:
            RuntimeError: Si el agente ya está en ejecución.
        """
        if self._activo:
            raise RuntimeError("El agente ya está en ejecución")

        self._activo = True
        self._evento_detener.clear()

        self._log.info(_COMPONENTE, "=" * 60)
        self._log.info(_COMPONENTE, "AAMRE — Agente Autónomo iniciando")
        self._log.info(_COMPONENTE, f"Versión: {CONFIG.version}")
        self._log.info(_COMPONENTE, f"Plataforma: {CONFIG.plataforma}")
        self._log.info(
            _COMPONENTE,
            f"Modo: {'SIMULACIÓN (SAFE_MODE)' if CONFIG.actuadores.safe_mode else 'PRODUCCIÓN'}",
        )
        self._log.info(_COMPONENTE, "=" * 60)

        # Registrar señales del SO para cierre limpio
        self._registrar_senales()

        # Mostrar estado inicial del sistema
        self._reportar_estado_inicial()

        # Iniciar capas en orden: deliberativa → reactiva → ejecutiva
        self._deliberativo.iniciar()
        self._reactivo.iniciar()
        self._hilo_ejecutivo = threading.Thread(
            target=self._ciclo_ejecutivo,
            name="Hilo-Ejecutivo",
            daemon=True,
        )
        self._hilo_ejecutivo.start()

        self._log.info(_COMPONENTE, "Todas las capas activas. Agente operacional.")

    def detener(self) -> None:
        """Detiene el agente y todas sus capas de forma ordenada.

        Orden de detención: reactiva → deliberativa → ejecutiva.
        Esto garantiza que no queden acciones a medias.
        """
        if not self._activo:
            return

        self._log.info(_COMPONENTE, "Iniciando secuencia de detención…")
        self._activo = False
        self._evento_detener.set()

        # Detener en orden inverso de inicio
        self._reactivo.detener()
        self._deliberativo.detener()

        if self._hilo_ejecutivo and self._hilo_ejecutivo.is_alive():
            self._hilo_ejecutivo.join(timeout=10)

        self._log.info(_COMPONENTE, "Agente AAMRE detenido correctamente")

    def esperar_hasta_detener(self) -> None:
        """Bloquea el hilo llamante hasta que el agente se detenga.

        Útil para mantener el proceso principal vivo mientras el agente
        opera en sus hilos.
        """
        try:
            self._evento_detener.wait()
        except KeyboardInterrupt:
            self.detener()

    # ------------------------------------------------------------------
    # Ciclo ejecutivo de supervisión
    # ------------------------------------------------------------------

    def _ciclo_ejecutivo(self) -> None:
        """Bucle de supervisión ejecutiva.

        Monitorea el estado global del agente, aplica arbitraje de
        prioridades y registra métricas periódicas.
        """
        self._log.info(_COMPONENTE, "Hilo ejecutivo de supervisión iniciado")
        intervalo_reporte: float = 60.0  # Reporte cada 60 segundos

        while not self._evento_detener.is_set():
            try:
                self._arbitraje_prioridades()
                self._reportar_metricas()
            except Exception as exc:
                self._log.error(_COMPONENTE, f"Error en ciclo ejecutivo: {exc}")

            self._evento_detener.wait(timeout=intervalo_reporte)

        self._log.info(_COMPONENTE, "Hilo ejecutivo finalizado")

    def _arbitraje_prioridades(self) -> None:
        """Aplica la política de arbitraje entre capas.

        Regla: la capa reactiva tiene SIEMPRE prioridad sobre la deliberativa.
        Si hay emergencia activa y el deliberativo sigue corriendo,
        lo suspende forzosamente (doble seguro).
        """
        with self._lock_arbitraje:
            if self._reactivo.esta_en_emergencia:
                if not self._deliberativo.evento_suspender.is_set():
                    self._log.warning(
                        _COMPONENTE,
                        "Arbitraje: forzando suspensión del deliberativo por emergencia activa",
                    )
                    self._deliberativo.evento_suspender.set()

    def _reportar_estado_inicial(self) -> None:
        """Registra el estado del disco al iniciar el agente."""
        try:
            estado = self._sensor.obtener_uso_disco()
            self._log.info(_COMPONENTE, f"Estado inicial: {estado}")
        except Exception as exc:
            self._log.error(_COMPONENTE, f"No se pudo leer estado inicial: {exc}")

    def _reportar_metricas(self) -> None:
        """Registra métricas de operación periódicas."""
        try:
            estado = self._sensor.obtener_uso_disco()
            self._log.info(
                _COMPONENTE,
                f"Métricas | {estado} | "
                f"Ciclos deliberativos: {self._deliberativo.ciclos_completados} | "
                f"Emergencia: {'SÍ' if self._reactivo.esta_en_emergencia else 'NO'}",
            )
        except Exception as exc:
            self._log.error(_COMPONENTE, f"Error reportando métricas: {exc}")

    # ------------------------------------------------------------------
    # Manejo de señales del SO
    # ------------------------------------------------------------------

    def _registrar_senales(self) -> None:
        """Registra manejadores para SIGINT y SIGTERM (Linux/macOS).

        En Windows SIGTERM no está disponible, se captura únicamente SIGINT.
        """
        def manejador(sig: int, _frame: object) -> None:
            self._log.warning(_COMPONENTE, f"Señal {sig} recibida — iniciando cierre limpio")
            self.detener()
            sys.exit(0)

        signal.signal(signal.SIGINT, manejador)
        try:
            signal.signal(signal.SIGTERM, manejador)
        except (OSError, AttributeError):
            # SIGTERM no disponible en Windows
            pass