# =========================================
# main.py - Z-Bot Padre v2
# FIX: import json movido al tope
# FIX: Hilos con watchdog - reinicio automatico
# FIX: Capital leido de billetera real
# FIX: except pass eliminados
# NO ejecuta. NO decide. NO toca capital.
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import time
import threading
import json
import os
from padre_corecro import ejecutar_corecro
from consejero import consultar_consejero
from engine import enviar_aviso
from estado_padre import esta_activo
from brain.data_engine import fetch_candles, preparar_datos_mercado, QUINTETO
from memoria.memoria import registrar_evento, registrar_corecro, registrar_matrix, registrar_centinela
from director_orquesta import orquestar
from centinela.centinela import iniciar as iniciar_centinela
from brain.telegram_engine import escuchar

BILLETERA     = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
ESTADO_ARCHIVO = os.path.expanduser("~/bot-padre-v2/estado_padre.txt")

# --- Verificacion de actividad ---
if not esta_activo():
    print("Z-BOT PADRE INACTIVO - EJECUCION BLOQUEADA")
    registrar_evento("Sistema bloqueado. Padre inactivo.")
    exit()

# --- Mensaje inicial controlado por bandera ---
try:
    with open(ESTADO_ARCHIVO, "r") as f:
        estado = f.read().strip()
except FileNotFoundError:
    estado = ""

if estado != "mensaje_enviado":
    print("Z-Bot Padre: Vigilancia silenciosa en curso...")
    enviar_aviso("Z-Bot en modo Silencio Inteligente. Solo responderé si me escribes /status.")
    registrar_evento("Sistema iniciado. Modo silencio inteligente activo.")
    try:
        with open(ESTADO_ARCHIVO, "w") as f:
            f.write("mensaje_enviado")
    except Exception as e:
        print(f"[MAIN] Error guardando estado: {e}")

def cargar_capital():
    try:
        with open(BILLETERA, "r") as f:
            bill = json.load(f)
        return float(bill.get("USDT", 0))
    except Exception as e:
        print(f"[MAIN] Error leyendo capital: {e}")
        return 0.0

# --- Funcion principal del ciclo ---
def ejecutar_ciclo_padre():
    # 1 Generar reporte CoreCro
    try:
        ejecutar_corecro()
        registrar_corecro("Reporte CoreCro generado correctamente.")
    except Exception as e:
        print(f"[MAIN] Error CoreCro: {e}")

    # 2 Consultar Consejero Economico
    capital = cargar_capital()
    try:
        recomendaciones = consultar_consejero(capital)
        print(f"Consejero: {recomendaciones['estado']} - {recomendaciones['mensaje']}")
        registrar_matrix(f"Consejero: {recomendaciones['estado']} - {recomendaciones['mensaje']}")
    except Exception as e:
        print(f"[MAIN] Error Consejero: {e}")

    # 3 Ciclo de vigilancia silenciosa
    for symbol in QUINTETO:
        try:
            velas_raw = fetch_candles(symbol)
            velas     = preparar_datos_mercado(symbol, velas_raw)
            if velas:
                actual  = velas[-1]
                precio  = actual["close"]
                rsi     = actual.get("rsi", "N/A")
                ema50   = actual.get("ema_50", "N/A")
                ema200  = actual.get("ema_200", "N/A")
                print(f"✅ {symbol}: ${precio} | RSI: {rsi} | EMA50: {ema50} | EMA200: {ema200}")
                registrar_evento(f"{symbol}: ${precio} | RSI: {rsi} | EMA50: {ema50} | EMA200: {ema200}")
        except Exception as e:
            print(f"[MAIN] Error procesando {symbol}: {e}")

    registrar_evento("Ciclo completado.")
    print("Ciclo completado. Reposando...")

def iniciar_hilo(target, nombre):
    """FIX: Crea y arranca un hilo daemon."""
    hilo = threading.Thread(target=target, daemon=True, name=nombre)
    hilo.start()
    return hilo

# --- Inicio del bot ---
if __name__ == "__main__":
    registrar_evento("Bot arrancado. Telegram escuchando.")

    hilo_telegram  = iniciar_hilo(escuchar,          "Telegram")
    hilo_orquesta  = iniciar_hilo(orquestar,          "Orquesta")
    hilo_centinela = iniciar_hilo(iniciar_centinela,  "Centinela")

    while True:
        try:
            # FIX: Watchdog — reinicia hilos caidos
            if not hilo_telegram.is_alive():
                print("[MAIN] ⚠️ Hilo Telegram muerto. Reiniciando...")
                registrar_evento("Hilo Telegram reiniciado por watchdog.")
                hilo_telegram = iniciar_hilo(escuchar, "Telegram")

            if not hilo_orquesta.is_alive():
                print("[MAIN] ⚠️ Hilo Orquesta muerto. Reiniciando...")
                registrar_evento("Hilo Orquesta reiniciado por watchdog.")
                hilo_orquesta = iniciar_hilo(orquestar, "Orquesta")

            if not hilo_centinela.is_alive():
                print("[MAIN] ⚠️ Hilo Centinela muerto. Reiniciando...")
                registrar_evento("Hilo Centinela reiniciado por watchdog.")
                hilo_centinela = iniciar_hilo(iniciar_centinela, "Centinela")

            ejecutar_ciclo_padre()
            time.sleep(60)

        except Exception as e:
            enviar_aviso(f"⚠️ Error en ciclo principal: {e}")
            registrar_centinela(f"Error detectado: {e}")
            print(f"[MAIN] Error: {e}")
            time.sleep(30)
