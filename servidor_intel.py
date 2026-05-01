import os
import telebot
import csv
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN_INTEL")

if not TOKEN:
    print("❌ ERROR: No se encontró el TOKEN en el .env")
    exit()

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['noticias', 'resumen'])
def enviar_resumen(message):
    archivo = "data_inteligencia_pura.csv"
    if not os.path.isfile(archivo) or os.stat(archivo).st_size == 0:
        bot.reply_to(message, "📋 La Matrix está vacía.")
        return

    mensaje = "📋 RESUMEN DE INTELIGENCIA\n\n"
    try:
        with open(archivo, mode='r') as f:
            reader = csv.reader(f)
            lineas = [l for l in list(reader) if len(l) >= 3 and "fecha" not in l[0]]
            for fila in lineas[-5:]:
                # Limpiamos el texto para evitar errores de Telegram
                fecha = fila[0].split(" ")[1] if " " in fila[0] else fila[0]
                cat = fila[2].replace("_", " ")
                nota = fila[-1].replace("*", "").replace("_", "").replace("\"", "")
                mensaje += f"🕒 {fecha} | {cat}\n> {nota}\n\n"
        
        # Enviamos como texto plano para evitar el error 400
        bot.send_message(message.chat.id, mensaje)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: True)
def registrar_desde_movil(message):
    noticia = message.text
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open("data_inteligencia_pura.csv", mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([fecha, "12", "MOVIL_ENTRY", noticia])
        bot.reply_to(message, "✅ Guardado en la Dell E6410.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

print("📡 Servidor blindado y escuchando...")
bot.infinity_polling()
