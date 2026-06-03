# Fundamentos Teóricos — AAMRE

## 1. Arquitectura Híbrida 3T (Three-Layer Architecture)

Propuesta por Bonasso et al. (1997), la Arquitectura 3T organiza un sistema autónomo en tres capas con responsabilidades bien definidas y niveles de abstracción distintos:

### 1.1 Capa Reactiva (Skill Layer)
- Opera sobre el **ciclo de control más rápido** del sistema.
- No realiza planificación; responde directamente a estímulos del entorno.
- Basada en el paradigma de subsunción de **Rodney Brooks (1986)**: comportamientos simples emergentes generan conducta compleja.
- En AAMRE: monitorea continuamente el porcentaje de uso del disco y ejecuta limpieza de emergencia cuando supera el 95%.

### 1.2 Capa Deliberativa (Planner Layer)
- Opera sobre el **ciclo de control más lento** del sistema.
- Realiza planificación simbólica basada en modelos del mundo.
- Implementa razonamiento tipo **BDI** (Beliefs, Desires, Intentions).
- En AAMRE: genera planes de mantenimiento preventivo basados en el escaneo completo del sistema de archivos.

### 1.3 Capa Ejecutiva (Sequencer Layer)
- **Intermediaria** entre las capas reactiva y deliberativa.
- Traduce los planes deliberativos en secuencias ejecutables.
- Implementa el **arbitraje de prioridades**: la reactividad prevalece ante la deliberación.
- En AAMRE: coordina hilos, resuelve conflictos y supervisa el estado global del agente.

---

## 2. Ciclo de Percepción–Decisión–Acción (PDA)

El ciclo fundamental en sistemas autónomos:

```
PERCEPCIÓN → DELIBERACIÓN → ACCIÓN → (retroalimentación) → PERCEPCIÓN
```

- **Percepción**: `psutil` + `pathlib` miden el estado del disco.
- **Deliberación**: La capa deliberativa analiza el escaneo y genera un plan priorizado.
- **Acción**: Los actuadores ejecutan la limpieza (real o simulada).
- **Retroalimentación**: El sensor verifica el nuevo estado tras la acción.

---

## 3. Modelo de Concurrencia

AAMRE implementa **concurrencia real mediante hilos del sistema operativo** (`threading`):

| Hilo             | Responsabilidad                    | Prioridad |
|------------------|------------------------------------|-----------|
| Hilo-Reactivo    | Monitoreo continuo de emergencias  | ALTA      |
| Hilo-Deliberativo| Planificación preventiva periódica | MEDIA     |
| Hilo-Ejecutivo   | Supervisión y arbitraje            | MEDIA     |

### Primitivas de Sincronización

| Primitiva       | Uso en AAMRE                                    |
|-----------------|-------------------------------------------------|
| `threading.Event` | Señalización inter-hilo (suspender/restaurar) |
| `threading.Lock`  | Protección de estado compartido (`_en_emergencia`) |
| `threading.Thread`| Creación de hilos dedicados por capa          |

---

## 4. Patrones de Diseño Aplicados

### Singleton
El `LoggerManager` garantiza una única instancia del logger usando **double-checked locking** thread-safe.

### Observer
El `SensorVirtual` notifica cambios de estado a suscriptores (capas del agente) sin acoplamiento directo. Esto sigue el principio de **Inversión de Dependencias** (SOLID-D).

### Strategy
Las estrategias de limpieza (`EstrategiaEliminarArchivos`, `EstrategiaEliminarDirectorios`) son intercambiables sin modificar el código cliente. Esto cumple el principio **Open/Closed** (SOLID-O).

### Facade
`GestorActuadores` expone una API simplificada que oculta la complejidad de las estrategias internas.

---

## 5. Referencias

- Brooks, R. A. (1986). *A robust layered control system for a mobile robot*. IEEE Journal on Robotics and Automation.
- Bonasso, R. P., Firby, R. J., Gat, E., Kortenkamp, D., Miller, D. P., & Slack, M. G. (1997). *Experiences with an architecture for intelligent, reactive agents*. Journal of Experimental & Theoretical Artificial Intelligence.
- Martin, R. C. (2003). *Agile Software Development: Principles, Patterns, and Practices*. Prentice Hall.
- Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). *Design Patterns: Elements of Reusable Object-Oriented Software*. Addison-Wesley.
