"""Módulo de notificaciones y control bidireccional vía Telegram."""
import requests
import threading
import time
import shutil
from logger_manager import LoggerManager

# Credenciales de Telegram
TOKEN = "8947284167:AAH6k37OHzeUPn6iYmUzvRQR0k27QuNSIdA"
CHAT_ID = "5133659874"

log = LoggerManager.obtener_instancia()

def enviar_mensaje_normal(texto: str):
    """Envía un mensaje de texto a Telegram."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        log.error("TELEGRAM", f"Fallo al enviar respuesta: {e}")

def enviar_alerta_emergencia(porcentaje_uso: float):
    """Envía la alerta de pánico (Capa Reactiva)."""
    mensaje = (
        "🚨 *ALERTA AAMRE: PROTOCOLO DE EMERGENCIA* 🚨\n\n"
        f"⚠️ Uso crítico: *{porcentaje_uso}%*\n"
        "🧹 Ejecutando limpieza instintiva..."
    )
    enviar_mensaje_normal(mensaje)

def _escuchar_comandos(funcion_limpiar):
    """Bucle infinito que lee los mensajes de Telegram (Long Polling)."""
    offset = 0
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    log.info("TELEGRAM", "Oreja digital activada. Escuchando comandos...")

    while True:
        try:
            params = {"timeout": 20, "offset": offset}
            respuesta = requests.get(url, params=params, timeout=25)

            if respuesta.status_code == 200:
                datos = respuesta.json()
                for msg in datos.get("result", []):
                    offset = msg["update_id"] + 1
                    
                    chat_id_remitente = str(msg.get("message", {}).get("chat", {}).get("id", ""))
                    texto = msg.get("message", {}).get("text", "")

                    if chat_id_remitente == CHAT_ID:
                        if texto == "/limpiar":
                            log.warning("TELEGRAM", "Orden remota: /limpiar recibida.")
                            enviar_mensaje_normal("⚙️ *Comando aceptado:* Iniciando barrido manual del sistema...")
                            funcion_limpiar()
                            enviar_mensaje_normal("✅ *Barrido completado.* Sistema optimizado.")
                        
                        elif texto == "/estado":
                            log.info("TELEGRAM", "Consulta de estado solicitada.")
                            # Lee el disco C directamente sin molestar al sensor principal
                            total, usado, libre = shutil.disk_usage("C:\\")
                            porcentaje = (usado / total) * 100
                            msg_estado = (
                                "📊 *ESTADO DEL SISTEMA AAMRE*\n\n"
                                f"💾 Uso de Disco: *{porcentaje:.1f}%*\n"
                                "🟢 Capa Reactiva: *Activa*\n"
                                "🟢 Capa Deliberativa: *Operativa*\n"
                                "🟢 Capa Ejecutiva: *En línea*"
                            )
                            enviar_mensaje_normal(msg_estado)

                        elif texto == "/ayuda" or texto == "/start":
                            msg_ayuda = (
                                "🤖 *Panel de Control AAMRE*\n\n"
                                "Selecciona una acción:\n"
                                "👉 /estado - Ver métricas en tiempo real\n"
                                "👉 /limpiar - Forzar recuperación de espacio\n"
                            )
                            enviar_mensaje_normal(msg_ayuda)

        except Exception as e:
            time.sleep(5)

def activar_receptor_telegram(funcion_limpiar):
    """Inicia el hilo espía en segundo plano."""
    hilo = threading.Thread(
        target=_escuchar_comandos, 
        args=(funcion_limpiar,), 
        daemon=True,
        name="Hilo-Telegram"
    )
    hilo.start()