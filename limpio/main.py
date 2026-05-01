# =========================================
# main.py - Z-Bot Padre v2 (Modo Silencio Inteligente)
# Rol: Vigilancia, integracion CoreCro y Consejero
# Director de Orquesta BTC ETH SOL BNB AVAX integrado
# Centinela Guardian integrado
# NO ejecuta. NO decide. NO toca capital.
# Sin librerias externas. Constitucion RESPETADA.
# =========================================

import time
import threading
from padre_corecro import ejecutar_corecro
from consejero import consultar_consejero
from engine import enviar_aviso
from estado_padre import esta_activo
from brain.data_engine import fetch_candles, preparar_datos_mercado, QUINTETO
from memoria.memoria import registrar_evento, registrar_corecro, registrar_matrix, registrar_centinela
from director_orquesta import orquestar
from centinela.centinela import iniciar as iniciar_centinela
from brain.telegram_engine import escuchar

# --- Verificacion de actividad ---
if not esta_activo():
    print("Z-BOT PADRE INACTIVO - EJECUCION BLOQUEADA")
    registrar_evento("Sistema bloqueado. Padre inactivo.")
    exit()

# --- Mensaje inicial controlado por bandera ---
try:
    with open("estado_padre.txt", "r") as f:
        estado = f.read().strip()
except FileNotFoundError:
    estado = ""

if estado != "mensaje_enviado":
    print("Z-Bot Padre: Vigilancia silenciosa en curso...")
    enviar_aviso("Z-Bot en modo Silencio Inteligente. Solo responderé si me escribes /status.")
    registrar_evento("Sistema iniciado. Modo silencio inteligente activo.")
    with open("estado_padre.txt", "w") as f:
        f.write("mensaje_enviado")

# --- Funcion principal del ciclo ---
def ejecutar_ciclo_padre():
    # 1 Generar reporte CoreCro
    ejecutar_corecro()
    registrar_corecro("Reporte CoreCro generado correctamente.")

    # 2 Consultar Consejero Economico
    import json
    try:
        with open("signals/billetera.json","r") as _f:
            _cap = json.load(_f).get("USDT", 1000.0)
    except:
        _cap = 1000.0
    recomendaciones = consultar_consejero(_cap)
    print(f"Recomendaciones del Consejero: {recomendaciones}")
    registrar_matrix(f"Consejero: {recomendaciones['estado']} - {recomendaciones['mensaje']}")

    # 3 Ciclo de vigilancia silenciosa
    for symbol in QUINTETO:
        velas_raw = fetch_candles(symbol)
        velas = preparar_datos_mercado(symbol, velas_raw)
        if velas:
            actual = velas[-1]
            precio = actual["close"]
            rsi = actual.get("rsi", "N/A")
            ema50 = actual.get("ema_50", "N/A")
            ema200 = actual.get("ema_200", "N/A")
            print(f"✅ {symbol}: ${precio} | RSI: {rsi} | EMA50: {ema50} | EMA200: {ema200}")
            registrar_evento(f"{symbol}: ${precio} | RSI: {rsi} | EMA50: {ema50} | EMA200: {ema200}")

    registrar_evento("Ciclo completado.")
    print("Ciclo completado. Consola actualizada. Reposando...")

# --- Inicio del bot ---
if __name__ == "__main__":
    registrar_evento("Bot arrancado. Telegram escuchando.")

    hilo_telegram = threading.Thread(target=escuchar, daemon=True)
    hilo_telegram.start()

    hilo_orquesta = threading.Thread(target=orquestar, daemon=True)
    hilo_orquesta.start()

    hilo_centinela = threading.Thread(target=iniciar_centinela, daemon=True)
    hilo_centinela.start()

    while True:
        try:
            ejecutar_ciclo_padre()
            time.sleep(60)
        except Exception as e:
            enviar_aviso(f"Error: {e}")
            registrar_centinela(f"Error detectado: {e}")
            time.sleep(30)
