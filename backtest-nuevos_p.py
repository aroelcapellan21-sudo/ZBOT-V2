#!/usr/bin/env python3
"""
Prueba diferentes rangos de RSI y configuraciones de trailing
sobre los datos históricos de BTCUSDT 4H.
No modifica nada de tu bot principal.
"""

import csv
import os

# ==========================================
# CONFIGURACIÓN DE LA PRUEBA
# ==========================================
ARCHIVO = os.path.expanduser("~/bot-padre-v2/data/historico_4h/BTCUSDT_4h.csv")

CAPITAL_INICIAL = 1000.0
MONTO_POR_OP    = 10.0
STOP_LOSS_BASE  = 3.5
TAKE_PROFIT_BASE = 6.0
EMA_CORTA = 20
EMA_LARGA = 50
DIFF_EMA_MAX = 2.0
VENTANA_FASE = 30
UMBRAL_FASE = 2.5

# Configuraciones a probar
CONFIGS = [
    {"nombre": "Original (45-55)", "rsi_min": 45, "rsi_max": 55, "trail_act": 0.5, "trail_dist": 1.5},
    {"nombre": "Amplio (40-60)",   "rsi_min": 40, "rsi_max": 60, "trail_act": 2.0, "trail_dist": 2.0},
    {"nombre": "Muy amplio (35-65)","rsi_min": 35, "rsi_max": 65, "trail_act": 2.5, "trail_dist": 2.0},
    {"nombre": "Estricto (48-52)",  "rsi_min": 48, "rsi_max": 52, "trail_act": 1.0, "trail_dist": 1.5},
]

# ==========================================
# FUNCIONES (copiadas de tu lógica real)
# ==========================================
def cargar_datos():
    datos = []
    with open(ARCHIVO) as f:
        reader = csv.DictReader(f)
        for row in reader:
            datos.append({
                "close": float(row["close"]),
                "high":  float(row["high"]),
                "low":   float(row["low"]),
            })
    return datos

def calcular_ema(cierres, periodo):
    if len(cierres) < periodo:
        return None
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for p in cierres[periodo:]:
        ema = p * k + ema * (1 - k)
    return ema

def calcular_rsi(cierres, periodo=14):
    if len(cierres) < periodo + 1:
        return None
    ganancias = []
    perdidas = []
    for i in range(1, periodo+1):
        diff = cierres[-i] - cierres[-i-1]
        if diff >= 0:
            ganancias.append(diff)
            perdidas.append(0)
        else:
            ganancias.append(0)
            perdidas.append(-diff)
    avg_g = sum(ganancias) / periodo
    avg_p = sum(perdidas) / periodo
    if avg_p == 0:
        return 100.0
    rs = avg_g / avg_p
    return 100 - (100 / (1 + rs))

def detectar_fase(cierres):
    if len(cierres) < VENTANA_FASE:
        return "DESCONOCIDA"
    precio_actual = cierres[-1]
    inicio = cierres[-VENTANA_FASE]
    cambio = ((precio_actual - inicio) / inicio) * 100
    ema50 = calcular_ema(cierres, 50)
    ema200 = calcular_ema(cierres, 200)
    if ema200 is None:
        return "DESCONOCIDA"
    if precio_actual > ema50 and precio_actual > ema200 and cambio > UMBRAL_FASE:
        return "ALCISTA"
    elif precio_actual < ema50 and precio_actual < ema200 and cambio < -UMBRAL_FASE:
        return "BAJISTA"
    else:
        return "LATERAL"

def señal_entrada(cierres, rsi_min, rsi_max):
    if len(cierres) < EMA_LARGA + 1:
        return False
    fase = detectar_fase(cierres)
    if fase != "LATERAL":
        return False
    rsi = calcular_rsi(cierres[-15:])
    if rsi is None:
        return False
    if not (rsi_min <= rsi <= rsi_max):
        return False
    ema_c = calcular_ema(cierres, EMA_CORTA)
    ema_l = calcular_ema(cierres, EMA_LARGA)
    if ema_c is None or ema_l is None:
        return False
    diff = abs(ema_c - ema_l) / ema_l * 100
    if diff >= DIFF_EMA_MAX:
        return False
    return True

def simular(config):
    datos = cargar_datos()
    cierres = [d["close"] for d in datos]
    highs = [d["high"] for d in datos]
    lows = [d["low"] for d in datos]
    
    capital = CAPITAL_INICIAL
    trades = 0
    ganados = 0
    en_trade = False
    precio_entrada = 0.0
    precio_max = 0.0
    sl_actual = 0.0
    
    for i in range(EMA_LARGA + 20, len(datos)):
        c_slice = cierres[:i+1]
        precio = cierres[i]
        high = highs[i]
        low = lows[i]
        
        if not en_trade:
            if señal_entrada(c_slice, config["rsi_min"], config["rsi_max"]):
                en_trade = True
                precio_entrada = precio
                precio_max = precio
                sl_actual = precio_entrada * (1 - STOP_LOSS_BASE / 100)
                trades += 1
        else:
            if high > precio_max:
                precio_max = high
            ganancia_max = (precio_max - precio_entrada) / precio_entrada * 100
            if ganancia_max >= config["trail_act"]:
                sl_trail = precio_max * (1 - config["trail_dist"] / 100)
                if sl_trail > sl_actual:
                    sl_actual = sl_trail
            # Comprobar TP
            cambio_actual = (precio - precio_entrada) / precio_entrada * 100
            if cambio_actual >= TAKE_PROFIT_BASE:
                capital += MONTO_POR_OP * (TAKE_PROFIT_BASE / 100)
                ganados += 1
                en_trade = False
            elif low <= sl_actual:
                capital += MONTO_POR_OP * ((sl_actual - precio_entrada) / precio_entrada)
                en_trade = False
    
    win_rate = (ganados / trades * 100) if trades > 0 else 0
    beneficio = capital - CAPITAL_INICIAL
    return trades, win_rate, beneficio

# ==========================================
# EJECUCIÓN DE LA PRUEBA
# ==========================================
print("=" * 60)
print("  COMPARATIVA DE RANGOS RSI Y TRAILING")
print("  BTCUSDT 4H - Backtest rápido")
print("=" * 60)

for cfg in CONFIGS:
    trades, wr, ben = simular(cfg)
    print(f"\n📊 {cfg['nombre']}")
    print(f"   RSI: {cfg['rsi_min']}-{cfg['rsi_max']}  Trail: {cfg['trail_act']}%/{cfg['trail_dist']}%")
    print(f"   Trades: {trades}  |  Win Rate: {wr:.1f}%  |  Beneficio: ${ben:.2f}")
    if trades > 0:
        print(f"   → Expectativa por trade: ${ben/trades:.2f}")
    else:
        print("   → Sin operaciones en el periodo.")
