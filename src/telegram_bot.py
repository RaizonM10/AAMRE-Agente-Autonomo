"""Módulo de notificaciones vía Telegram."""
import requests
from logger_manager import LoggerManager

# Credenciales de Telegram (Tus datos reales)
TOKEN = "8947284167:AAH6k37OHzeUPn6iYmUzvRQR0k27QuNSIdA"
CHAT_ID = "5133659874"

log = LoggerManager.obtener_instancia()

def enviar_alerta_emergencia(porcentaje_uso: float):
    """Envía un mensaje de alerta a Telegram."""
    mensaje = (
        "🚨 *ALERTA AAMRE: PROTOCOLO DE EMERGENCIA* 🚨\n\n"
        f"⚠️ Uso de disco crítico detectado: *{porcentaje_uso}%*\n"
        "🛑 Capa Deliberativa: SUSPENDIDA.\n"
        "🧹 Ejecutando limpieza reactiva instintiva..."
    )
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    
    try:
        respuesta = requests.post(url, json=payload, timeout=5)
        if respuesta.status_code == 200:
            log.info("TELEGRAM", "Alerta enviada al administrador exitosamente.")
        else:
            log.warning("TELEGRAM", f"Fallo al enviar alerta: HTTP {respuesta.status_code}")
    except Exception as e:
        log.error("TELEGRAM", f"Error de conexión con Telegram: {e}")