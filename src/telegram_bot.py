"""Módulo de notificaciones y control bidireccional vía Telegram."""
import requests
import threading
import time
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
            # Espera hasta 20 segundos a que llegue un mensaje nuevo
            params = {"timeout": 20, "offset": offset}
            respuesta = requests.get(url, params=params, timeout=25)

            if respuesta.status_code == 200:
                datos = respuesta.json()
                for msg in datos.get("result", []):
                    offset = msg["update_id"] + 1
                    
                    # Extraer quién envía y qué dice
                    chat_id_remitente = str(msg.get("message", {}).get("chat", {}).get("id", ""))
                    texto = msg.get("message", {}).get("text", "")

                    # Seguridad: Solo obedecer si el mensaje viene de TU celular y dice /limpiar
                    if chat_id_remitente == CHAT_ID and texto == "/limpiar":
                        log.warning("TELEGRAM", "Orden remota: /limpiar recibida.")
                        enviar_mensaje_normal("⚙️ *Comando aceptado:* Iniciando barrido manual del sistema...")
                        
                        # ¡Aquí disparamos la función real de tu programa!
                        funcion_limpiar()
                        
                        enviar_mensaje_normal("✅ *Barrido completado.* Sistema optimizado.")

        except Exception as e:
            time.sleep(5) # Si se cae el internet, espera 5s y vuelve a intentar

def activar_receptor_telegram(funcion_limpiar):
    """Inicia el hilo espía en segundo plano."""
    hilo = threading.Thread(
        target=_escuchar_comandos, 
        args=(funcion_limpiar,), 
        daemon=True,
        name="Hilo-Telegram"
    )
    hilo.start()