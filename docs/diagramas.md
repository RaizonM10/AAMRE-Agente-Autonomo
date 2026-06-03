# Diagramas del Sistema — AAMRE

Todos los diagramas están escritos en **Mermaid** y se renderizan automáticamente en GitHub.

---

## 1. Arquitectura Híbrida 3T

```mermaid
graph TB
    subgraph EJECUTIVO["🧠 Capa Ejecutiva (AgenteAAMRE)"]
        EJ[Coordinación & Arbitraje<br/>Hilo-Ejecutivo]
    end

    subgraph REACTIVO["⚡ Capa Reactiva (CapaReactiva)"]
        RE[Monitor Continuo<br/>Hilo-Reactivo<br/>Prioridad ALTA]
    end

    subgraph DELIBERATIVO["📋 Capa Deliberativa (CapaDeliberativa)"]
        DE[Planificador Periódico<br/>Hilo-Deliberativo<br/>Prioridad MEDIA]
    end

    subgraph PERCEPCION["👁️ Percepción (SensorVirtual)"]
        SE[psutil + pathlib<br/>Sensor Virtual]
    end

    subgraph ACTUADORES["🤖 Actuadores (GestorActuadores)"]
        AC[Estrategias de Limpieza<br/>SAFE_MODE / Producción]
    end

    EJ -->|arbitraje| RE
    EJ -->|coordina| DE
    RE -->|consulta| SE
    DE -->|consulta| SE
    SE -->|notifica Observer| EJ
    RE -->|ejecuta| AC
    DE -->|ejecuta| AC
```

---

## 2. Flujo de Datos del Sistema

```mermaid
flowchart LR
    DISCO[(Sistema de<br/>Archivos)] -->|psutil| SV[SensorVirtual]
    SV -->|EstadoDisco| CR[CapaReactiva]
    SV -->|ResultadoEscaneo| CD[CapaDeliberativa]
    CR -->|emergencia| GA[GestorActuadores]
    CD -->|plan| GA
    GA -->|log| LOG[Logger Singleton]
    CR -->|Event suspender| CD
    CR -->|Event restaurar| CD
    AE[AgenteAAMRE] -->|supervisa| CR
    AE -->|supervisa| CD
    AE -->|métricas| LOG
```

---

## 3. Comunicación entre Hilos

```mermaid
sequenceDiagram
    participant HR as Hilo-Reactivo
    participant HE as Hilo-Ejecutivo
    participant HD as Hilo-Deliberativo
    participant SV as SensorVirtual

    loop Cada 5 segundos
        HR->>SV: obtener_uso_disco()
        SV-->>HR: EstadoDisco(96%)
        HR->>HR: uso ≥ 95% → EMERGENCIA
        HR->>HD: Event.set(suspender)
        Note over HD: HD detecta Event<br/>y se pausa
        HR->>SV: escanear_entorno()
        SV-->>HR: ResultadoEscaneo
        HR->>GA: ejecutar_recuperacion_emergencia()
        GA-->>HR: ResultadoAccion
    end

    loop Cada 60 segundos
        HE->>HR: esta_en_emergencia?
        HR-->>HE: False (recuperado)
        HE->>HE: arbitraje OK
        HE->>HD: Event.set(restaurar)
        Note over HD: HD reanuda<br/>planificación
    end

    loop Cada 30 segundos
        HD->>SV: escanear_entorno()
        SV-->>HD: ResultadoEscaneo
        HD->>HD: _generar_plan()
        HD->>GA: eliminar_temporales()
        HD->>GA: eliminar_logs_antiguos()
        HD->>GA: limpiar_caches()
    end
```

---

## 4. Ciclo Percepción–Decisión–Acción (PDA)

```mermaid
stateDiagram-v2
    [*] --> Percepcion : Agente iniciado

    Percepcion : Percepción\nSensorVirtual.obtener_uso_disco()\nSensorVirtual.escanear_entorno()

    Percepcion --> Decision_Reactiva : uso ≥ 95%
    Percepcion --> Decision_Deliberativa : uso < 95%
    Percepcion --> Reposo : sin candidatos

    Decision_Reactiva : Decisión Reactiva\nProtocolo de Emergencia\nSuspender Deliberativo

    Decision_Deliberativa : Decisión Deliberativa\n_generar_plan()\nPriorizar acciones

    Decision_Reactiva --> Accion_Emergencia
    Decision_Deliberativa --> Accion_Preventiva

    Accion_Emergencia : Acción Emergencia\nejecutar_recuperacion_emergencia()\nEliminar tmp + logs + cache

    Accion_Preventiva : Acción Preventiva\neliminar_temporales()\neliminar_logs_antiguos()\nlimpiar_caches()

    Accion_Emergencia --> Verificacion
    Accion_Preventiva --> Verificacion
    Reposo --> Percepcion

    Verificacion : Verificación\nuso < 90% → restaurar deliberativo\nRegistrar en log

    Verificacion --> Percepcion
```

---

## 5. Diagrama de Clases (simplificado)

```mermaid
classDiagram
    class AgenteAAMRE {
        -SensorVirtual _sensor
        -GestorActuadores _actuadores
        -CapaReactiva _reactivo
        -CapaDeliberativa _deliberativo
        +iniciar()
        +detener()
        +esperar_hasta_detener()
    }

    class SensorVirtual {
        -Path _ruta_escaneo
        -list _suscriptores
        +obtener_uso_disco() EstadoDisco
        +escanear_entorno() ResultadoEscaneo
        +suscribir(nombre, callback)
        +notificar(estado)
    }

    class CapaReactiva {
        -threading.Thread _hilo
        -threading.Event _evento_emergencia
        -threading.Lock _lock_estado
        +iniciar()
        +detener()
        +esta_en_emergencia bool
    }

    class CapaDeliberativa {
        -threading.Thread _hilo
        -schedule.Scheduler _scheduler
        +iniciar()
        +detener()
        +ciclos_completados int
    }

    class GestorActuadores {
        -bool _safe_mode
        +eliminar_temporales(archivos)
        +eliminar_logs_antiguos(archivos)
        +limpiar_caches(dirs)
        +ejecutar_recuperacion_emergencia(escaneo)
    }

    class LoggerManager {
        <<Singleton>>
        -Logger _logger
        +obtener_instancia() LoggerManager
        +info(componente, mensaje)
        +error(componente, mensaje)
    }

    AgenteAAMRE --> SensorVirtual
    AgenteAAMRE --> GestorActuadores
    AgenteAAMRE --> CapaReactiva
    AgenteAAMRE --> CapaDeliberativa
    CapaReactiva --> SensorVirtual
    CapaReactiva --> GestorActuadores
    CapaDeliberativa --> SensorVirtual
    CapaDeliberativa --> GestorActuadores
    AgenteAAMRE --> LoggerManager
    CapaReactiva --> LoggerManager
    CapaDeliberativa --> LoggerManager
    GestorActuadores --> LoggerManager
```
