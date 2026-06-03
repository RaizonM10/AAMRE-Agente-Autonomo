"""
deliberativo.py — Capa Deliberativa del sistema AAMRE.

Implementa el planificador a largo plazo del agente: programa tareas
periódicas de mantenimiento preventivo y puede ser suspendida por la
capa reactiva ante emergencias.

Analogía robótica:
    - Planificador BDI (Beliefs, Desires, Intentions)
    - Genera planes de acción sobre el mapa del entorno
    - Se adapta al estado del mundo antes de actuar

Concurrencia: hilo dedicado con threading.Thread + threading.Event.
Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import threading
import time

import schedule

from actuadores import GestorActuadores
from configuracion import CONFIG
from logger_manager import LoggerManager
from percepcion import SensorVirtual

_COMPONENTE = "DELIBERATIVO"


class CapaDeliberativa:
    """Capa deliberativa del agente AAMRE.

    Planifica y ejecuta mantenimiento preventivo de forma periódica.
    Se suspende automáticamente cuando la capa reactiva detecta una
    emergencia y se reanuda una vez que la emergencia se resuelve.

    Attributes:
        _sensor: Sensor virtual para escanear el entorno.
        _actuadores: Gestor de actuadores para ejecutar acciones.
        _log: Logger singleton.
        _config: Parámetros de configuración deliberativa.
        _hilo: Hilo de ejecución del planificador.
        _evento_detener: Señal para terminar el hilo.
        _evento_suspendido: Señal para pausar la ejecución.
        _evento_restaurar: Señal para reanudar la ejecución.
        _scheduler: Instancia de schedule para tareas periódicas.
        _ciclos_completados: Contador de ciclos de mantenimiento.
    """

    def __init__(
        self,
        sensor: SensorVirtual,
        actuadores: GestorActuadores,
    ) -> None:
        """Inicializa la capa deliberativa.

        Args:
            sensor: Sensor virtual compartido con el sistema.
            actuadores: Gestor de actuadores del sistema.
        """
        self._sensor = sensor
        self._actuadores = actuadores
        self._log = LoggerManager.obtener_instancia()
        self._config = CONFIG.deliberativo

        # Sincronización de hilos
        self._hilo: threading.Thread | None = None
        self._evento_detener = threading.Event()
        self._evento_suspendido = threading.Event()   # SET = suspendido
        self._evento_restaurar = threading.Event()    # SET = restaurar

        # Estado y métricas
        self._ciclos_completados: int = 0
        self._scheduler = schedule.Scheduler()
        self._configurar_tareas_periodicas()

    # ------------------------------------------------------------------
    # Configuración de tareas periódicas
    # ------------------------------------------------------------------

    def _configurar_tareas_periodicas(self) -> None:
        """Registra las tareas periódicas en el scheduler.

        Las tareas se programan en función del intervalo configurado
        en ``CONFIG.deliberativo.intervalo_planificacion_seg``.
        """
        intervalo = int(self._config.intervalo_planificacion_seg)
        self._scheduler.every(intervalo).seconds.do(self._ciclo_mantenimiento)
        self._log.info(
            _COMPONENTE,
            f"Tareas periódicas configuradas cada {intervalo}s",
        )

    # ------------------------------------------------------------------
    # Eventos controlados por la capa ejecutiva / reactiva
    # ------------------------------------------------------------------

    @property
    def evento_suspender(self) -> threading.Event:
        """Event que la capa reactiva setea para suspender este planificador."""
        return self._evento_suspendido

    @property
    def evento_restaurar(self) -> threading.Event:
        """Event que la capa reactiva setea para restaurar este planificador."""
        return self._evento_restaurar

    # ------------------------------------------------------------------
    # Ciclo de vida del hilo
    # ------------------------------------------------------------------

    def iniciar(self) -> None:
        """Crea e inicia el hilo del planificador deliberativo."""
        self._evento_detener.clear()
        self._hilo = threading.Thread(
            target=self._bucle_scheduler,
            name="Hilo-Deliberativo",
            daemon=True,
        )
        self._hilo.start()
        self._log.info(_COMPONENTE, "Hilo deliberativo iniciado")

    def detener(self) -> None:
        """Detiene el hilo de planificación de forma segura."""
        self._log.info(_COMPONENTE, "Deteniendo hilo deliberativo…")
        self._evento_detener.set()
        # Desbloquear si estaba suspendido esperando
        self._evento_restaurar.set()
        if self._hilo and self._hilo.is_alive():
            self._hilo.join(timeout=10)
        self._log.info(_COMPONENTE, "Hilo deliberativo detenido")

    # ------------------------------------------------------------------
    # Lógica principal del hilo
    # ------------------------------------------------------------------

    def _bucle_scheduler(self) -> None:
        """Bucle principal del hilo deliberativo.

        En cada iteración:
        1. Verifica si fue suspendido → espera señal de restauración.
        2. Ejecuta las tareas pendientes del scheduler.
        3. Duerme 1 segundo (granularidad del scheduler).
        """
        self._log.info(_COMPONENTE, "Bucle de planificación iniciado")

        while not self._evento_detener.is_set():
            # --- Verificar suspensión ---
            if self._evento_suspendido.is_set():
                self._log.warning(_COMPONENTE, "Planificador SUSPENDIDO por emergencia. Esperando…")
                self._evento_suspendido.clear()

                # Bloquear hasta restauración o señal de detención
                while not self._evento_detener.is_set():
                    if self._evento_restaurar.wait(timeout=1.0):
                        self._evento_restaurar.clear()
                        if not self._evento_detener.is_set():
                            self._log.info(_COMPONENTE, "Planificador REANUDADO")
                        break

            # --- Ejecutar tareas programadas ---
            try:
                self._scheduler.run_pending()
            except Exception as exc:
                self._log.error(_COMPONENTE, f"Error en scheduler: {exc}")

            self._evento_detener.wait(timeout=1.0)

        self._log.info(_COMPONENTE, "Bucle de planificación finalizado")

    # ------------------------------------------------------------------
    # Ciclo de mantenimiento (tarea planificada)
    # ------------------------------------------------------------------

    def _ciclo_mantenimiento(self) -> None:
        """Ejecuta un ciclo completo de mantenimiento preventivo.

        Fases:
        1. Percepción: escanear el entorno.
        2. Deliberación: calcular prioridad de acciones.
        3. Acción: ejecutar actuadores.
        4. Registro: documentar resultados.
        """
        self._ciclos_completados += 1
        self._log.info(
            _COMPONENTE,
            f"=== Ciclo de mantenimiento #{self._ciclos_completados} ===",
        )

        try:
            # Fase 1: Percepción
            escaneo = self._sensor.escanear_entorno()
            self._log.info(_COMPONENTE, f"Escaneo: {escaneo}")

            if not self._hay_trabajo(escaneo):
                self._log.info(_COMPONENTE, "Sin candidatos a limpieza. Ciclo omitido.")
                return

            # Fase 2: Deliberación — ordenar acciones por prioridad
            plan = self._generar_plan(escaneo)
            self._log.info(_COMPONENTE, f"Plan generado: {len(plan)} acciones")

            # Fase 3: Acción — ejecutar según plan
            for accion in plan:
                accion()

        except Exception as exc:
            self._log.error(_COMPONENTE, f"Error en ciclo de mantenimiento: {exc}")

    def _hay_trabajo(self, escaneo) -> bool:  # type: ignore[no-untyped-def]
        """Evalúa si hay candidatos a limpieza en el escaneo.

        Args:
            escaneo: Resultado del escaneo del sensor.

        Returns:
            True si hay al menos un candidato.
        """
        return bool(
            escaneo.archivos_temporales
            or escaneo.archivos_log_antiguos
            or escaneo.directorios_cache
        )

    def _generar_plan(self, escaneo) -> list:  # type: ignore[no-untyped-def]
        """Genera un plan priorizado de acciones de mantenimiento.

        La priorización sigue el criterio de mayor impacto primero:
        1. Archivos temporales (rápidos de eliminar, impacto inmediato).
        2. Logs antiguos (impacto medio).
        3. Cachés (más costoso, menor prioridad en mantenimiento normal).

        Args:
            escaneo: Resultado del escaneo del sensor.

        Returns:
            Lista de callables ordenados por prioridad.
        """
        plan = []

        if escaneo.archivos_temporales:
            archivos = escaneo.archivos_temporales
            plan.append(lambda a=archivos: self._actuadores.eliminar_temporales(a))

        if escaneo.archivos_log_antiguos:
            logs = escaneo.archivos_log_antiguos
            plan.append(lambda l=logs: self._actuadores.eliminar_logs_antiguos(l))

        if escaneo.directorios_cache:
            caches = escaneo.directorios_cache
            plan.append(lambda c=caches: self._actuadores.limpiar_caches(c))

        return plan

    @property
    def ciclos_completados(self) -> int:
        """Número de ciclos de mantenimiento ejecutados."""
        return self._ciclos_completados
