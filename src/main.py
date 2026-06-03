"""
main.py — Punto de entrada del sistema AAMRE.

Inicializa y arranca el Agente Autónomo de Mantenimiento y Recuperación
de Espacio. Soporta ejecución en modo seguro (simulación) o producción
mediante argumento de línea de comandos.

Uso:
    python main.py                  # Modo SAFE (simulación)
    python main.py --produccion     # Modo PRODUCCIÓN (operaciones reales)
    python main.py --duracion 120   # Ejecutar durante 120 segundos

Autor: AAMRE Team
Python: 3.11+
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


# Agregar src/ al path para imports directos
sys.path.insert(0, str(Path(__file__).resolve().parent))
from telegram_bot import activar_receptor_telegram
from configuracion import CONFIG
from ejecutivo import AgenteAAMRE
from logger_manager import LoggerManager


def parsear_argumentos() -> argparse.Namespace:
    """Parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="AAMRE",
        description=(
            "Agente Autónomo de Mantenimiento y Recuperación de Espacio\n"
            "Implementa la Arquitectura Híbrida 3T para robótica autónoma."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--produccion",
        action="store_true",
        default=False,
        help="Ejecuta en modo producción (operaciones REALES). Por defecto: simulación.",
    )
    parser.add_argument(
        "--duracion",
        type=float,
        default=None,
        metavar="SEGUNDOS",
        help="Duración máxima de ejecución en segundos. Sin límite si no se especifica.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"AAMRE v{CONFIG.version}",
    )
    return parser.parse_args()


def imprimir_banner() -> None:
    """Imprime el banner de inicio del sistema."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║     AAMRE — Agente Autónomo de Mantenimiento y Recuperación  ║
║                    de Espacio  v{version:<10}               ║
║                                                              ║
║  Arquitectura Híbrida 3T                                     ║
║  ├─ [REACTIVA]     Monitoreo continuo y emergencias          ║
║  ├─ [DELIBERATIVA] Planificación y mantenimiento preventivo  ║
║  └─ [EJECUTIVA]    Coordinación y arbitraje de prioridades   ║
╚══════════════════════════════════════════════════════════════╝
""".format(version=CONFIG.version)
    print(banner)


def main() -> int:
    """Función principal del sistema AAMRE."""
    args = parsear_argumentos()
    imprimir_banner()

    log = LoggerManager.obtener_instancia()
    safe_mode = not args.produccion

    if not safe_mode:
        print("\n⚠️  ADVERTENCIA: Modo PRODUCCIÓN activo — las operaciones son REALES.\n")
        log.warning("MAIN", "Sistema iniciado en MODO PRODUCCIÓN")
    else:
        print("\n🛡️  Modo SIMULACIÓN activo (SAFE_MODE=True) — no se elimina nada real.\n")
        log.info("MAIN", "Sistema iniciado en MODO SIMULACIÓN")

    try:
        agente = AgenteAAMRE(safe_mode=safe_mode)

        # =========================================================
        # NUEVA SECCIÓN: CONTROL REMOTO TELEGRAM
        # =========================================================
        def forzar_limpieza_remota():
            """Esta función se ejecutará cuando mandes /limpiar por Telegram"""
            log.info("MAIN", "Comando /limpiar recibido, ejecutando barrido remoto...")
            try:
                escaneo = agente._sensor.escanear_entorno()
                agente._actuadores.eliminar_temporales(escaneo.archivos_temporales)
                log.info("MAIN", "Barrido remoto completado con éxito.")
            except Exception as e:
                log.error("MAIN", f"Fallo en limpieza remota: {e}")

        # Encendemos la oreja en segundo plano antes de arrancar el agente principal
        activar_receptor_telegram(forzar_limpieza_remota)
        # =========================================================

        agente.iniciar()

        if args.duracion is not None:
            log.info("MAIN", f"Ejecución programada durante {args.duracion}s")
            tiempo_fin = time.time() + args.duracion
            while time.time() < tiempo_fin:
                time.sleep(1.0)
            agente.detener()
        else:
            log.info("MAIN", "Presiona Ctrl+C para detener el agente")
            agente.esperar_hasta_detener()

    except KeyboardInterrupt:
        print("\nInterrupción detectada. Cerrando agente…")
        log.info("MAIN", "Interrupción de usuario — cierre limpio")
        return 0
    except Exception as exc:
        log.error("MAIN", f"Error fatal: {exc}")
        return 1

    log.info("MAIN", "Sistema AAMRE finalizado correctamente")
    return 0


if __name__ == "__main__":
    sys.exit(main())