
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import paho.mqtt.publish as publish
import logging, os
import ssl 

TOKEN = os.environ["TB_TOKEN"]

MQTT_SERVER = "mosquitto"
MQTT_PORT = 8883 
MQTT_USER = os.environ.get("MQTT_USR", "root")
MQTT_PASS = os.environ.get("MQTT_PASS", "iot2026")
ID_PICO = "ID_DISPOSITIVO" 

logging.basicConfig(format='%(asctime)s - TelegramBot - %(levelname)s - %(message)s', level=logging.INFO)

def enviar_mqtt(subtopico, payload):
    topico = f"{ID_PICO}/{subtopico}"
    auth = {'username': MQTT_USER, 'password': MQTT_PASS}
    
    tls_config = {
        'ca_certs': None,
        'tls_version': ssl.PROTOCOL_TLS_CLIENT,
        'cert_reqs': ssl.CERT_NONE 
    }
    
    try:
        publish.single(
            topic=topico,
            payload=str(payload),
            hostname=MQTT_SERVER,
            port=MQTT_PORT,
            auth=auth,
            tls=tls_config 
        )
        logging.info(f"Publicado MQTTS OK -> {topico}: {payload}")
        return True
    except Exception as e:
        logging.error(f"Error de red/TLS: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        f"Control de Termostato.\n\n"
        "/setpoint <valor> - Cambia temp. de corte\n"
        "/periodo <seg> - Tiempo entre mediciones\n"
        "/modo <auto|manual> - Cambia el modo\n"
        "/rele <on|off> - Control manual\n"
        "/destello - Parpadea el LED\n"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=mensaje)

async def cmd_setpoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        enviar_mqtt("setpoint", context.args[0])
        await update.message.reply_text(f"Setpoint: {context.args[0]}°C")

async def cmd_periodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        enviar_mqtt("periodo", context.args[0])
        await update.message.reply_text(f"Periodo: {context.args[0]}s")

async def cmd_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        enviar_mqtt("modo", context.args[0].lower())
        await update.message.reply_text(f"Modo: {context.args[0]}")

async def cmd_rele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        enviar_mqtt("rele", context.args[0].lower())
        await update.message.reply_text(f"Relé: {context.args[0]}")

async def cmd_destello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    enviar_mqtt("destello", "1")
    await update.message.reply_text("Destello enviado.")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('setpoint', cmd_setpoint))
    application.add_handler(CommandHandler('periodo', cmd_periodo))
    application.add_handler(CommandHandler('modo', cmd_modo))
    application.add_handler(CommandHandler('rele', cmd_rele))
    application.add_handler(CommandHandler('destello', cmd_destello))
    application.run_polling()

if __name__ == '__main__':
    main()