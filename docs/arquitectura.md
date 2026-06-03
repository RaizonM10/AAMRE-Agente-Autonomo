# Arquitectura del Sistema — AAMRE

## Visión General

AAMRE implementa una **Arquitectura Híbrida 3T** con tres capas concurrentes que operan de forma coordinada:

```
┌──────────────────────────────────────────────────────────┐
│                    CAPA EJECUTIVA                        │
│  AgenteAAMRE — Coordinación, Arbitraje, Supervisión      │
│  Hilo: Hilo-Ejecutivo  │  Patrón: Facade                 │
└──────────────┬──────────────────────┬────────────────────┘
               │                      │
   ┌───────────▼───────────┐ ┌────────▼──────────────────┐
   │   CAPA REACTIVA       │ │   CAPA DELIBERATIVA        │
   │  CapaReactiva         │ │  CapaDeliberativa          │
   │  Hilo: Hilo-Reactivo  │ │  Hilo: Hilo-Deliberativo  │
   │  Prioridad: ALTA      │ │  Prioridad: MEDIA         │
   └───────────┬───────────┘ └────────┬──────────────────┘
               │                      │
   ┌───────────▼──────────────────────▼──────────────────┐
   │              CAPA DE PERCEPCIÓN                      │
   │   SensorVirtual (psutil + pathlib + os)             │
   └───────────────────────┬─────────────────────────────┘
                           │
   ┌───────────────────────▼─────────────────────────────┐
   │              ACTUADORES                              │
   │   GestorActuadores → Estrategias de Limpieza        │
   │   SAFE_MODE: simulación / producción                │
   └─────────────────────────────────────────────────────┘
```

## Flujo de Comunicación Inter-Capa

### Canal Reactivo → Ejecutivo
- `threading.Event` (`_evento_emergencia`): publicado cuando hay emergencia.
- `threading.Lock` (`_lock_estado`): protege bandera `_en_emergencia`.

### Canal Ejecutivo → Deliberativo
- `threading.Event` (`evento_suspender`): suspende el planificador.
- `threading.Event` (`evento_restaurar`): reanuda el planificador.

### Canal Sensor → Capas (Observer)
- El `SensorVirtual` mantiene una lista de suscriptores.
- Al llamar `notificar()`, distribuye el `EstadoDisco` a todas las capas suscritas.

## Módulos y Responsabilidades

| Módulo            | Clase Principal       | Patrón        | Responsabilidad                         |
|-------------------|-----------------------|---------------|-----------------------------------------|
| `configuracion.py`| `ConfigSistema`       | Value Object  | Parámetros centralizados del sistema    |
| `logger_manager.py`| `LoggerManager`      | Singleton     | Registro unificado de eventos           |
| `percepcion.py`   | `SensorVirtual`       | Observer      | Percepción del entorno (disco/archivos) |
| `actuadores.py`   | `GestorActuadores`    | Facade+Strategy| Ejecución de acciones de limpieza      |
| `reactivo.py`     | `CapaReactiva`        | Thread+Event  | Respuesta inmediata a emergencias       |
| `deliberativo.py` | `CapaDeliberativa`    | Thread+Schedule| Planificación preventiva periódica     |
| `ejecutivo.py`    | `AgenteAAMRE`         | Facade        | Coordinación y arbitraje global         |
| `utils.py`        | Funciones             | Utility       | Helpers transversales                   |
| `main.py`         | `main()`              | Entry Point   | Inicialización y CLI                    |

## Política de Arbitraje de Prioridades

```
PRIORIDAD REACTIVA > PRIORIDAD DELIBERATIVA

Si (uso_disco ≥ 95%):
    suspender(deliberativo)
    ejecutar_emergencia(reactivo)

Si (uso_disco < 90%) AND (en_emergencia):
    restaurar(deliberativo)
    limpiar_bandera_emergencia(reactivo)
```
