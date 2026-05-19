# =========================================
# config_cartera.py
# Configuracion central de la cartera
# FIX: Parametros actualizados post-optimizacion
# FIX: CAPITAL_MAX_POR_OP unificado
# Fuente unica de verdad para todos los modulos
# Sin librerias externas. Constitucion RESPETADA
# =========================================

# --- PESOS OPTIMOS DE CARTERA ---
PESOS_CARTERA = {
    "BTCUSDT":  21.68,
    "ETHUSDT":  18.97,
    "SOLUSDT":  23.85,
    "BNBUSDT":  18.97,
    "AVAXUSDT": 16.53,
}

# --- CAPITAL BASE ---
CAPITAL_BASE = 1000.0

# --- CAPITAL MAXIMO POR OPERACION ---
CAPITAL_MAX_POR_OP = 0.02

# --- MONTO MINIMO BINANCE ---
MONTO_MINIMO_BINANCE = 5.0

# --- INTERVALO DE REVISION ---
INTERVALO_4H = 240

# --- UMBRAL REBALANCEO ---
UMBRAL_REBALANCEO = 10.0

# --- PARAMETROS OPTIMOS POST-OPTIMIZACION ---
# Validados con 18,678 velas 4H por activo
# Meta Blue Guardian: WR 65%+ PF 1.8+
PARAMETROS = {
    "BTCUSDT": {
        "alcista": {"rsi_min": 55, "rsi_max": 75, "sl": 5.0, "tp": 6.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 4.0, "ec": 10, "el":  50, "trail_act": 0.5, "trail_dist": 1.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 3.5, "tp": 4.0, "ec": 10, "el":  30, "trail_act": 0.5, "trail_dist": 1.0},
    },
    "ETHUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.0, "tp": 4.0, "ec": 20, "el":  50, "trail_act": 0.5, "trail_dist": 1.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 4.5, "tp": 6.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
    },
    "SOLUSDT": {
        "alcista": {"rsi_min": 50, "rsi_max": 70, "sl": 5.0, "tp": 6.0, "ec": 20, "el":  50, "trail_act": 0.5, "trail_dist": 1.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 5.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 3.5, "tp": 4.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
    },
    "BNBUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 4.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
    },
    "AVAXUSDT": {
        "alcista": {"rsi_min": 60, "rsi_max": 75, "sl": 4.5, "tp": 5.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
        "bajista": {"rsi_min": 30, "rsi_max": 50, "sl": 3.5, "tp": 4.0, "ec": 20, "el":  50, "trail_act": 0.5, "trail_dist": 1.0},
        "lateral": {"rsi_min": 43, "rsi_max": 57, "sl": 5.0, "tp": 6.0, "ec": 20, "el": 100, "trail_act": 0.5, "trail_dist": 1.0},
    },
}

def capital_por_moneda(capital_actual):
    return {
        symbol: round(capital_actual * (peso / 100), 2)
        for symbol, peso in PESOS_CARTERA.items()
    }

def get_params(symbol, fase):
    """
    Retorna parametros optimos para un symbol y fase.
    Uso: p = get_params('BTCUSDT', 'alcista')
    """
    return PARAMETROS.get(symbol, PARAMETROS["BTCUSDT"]).get(fase, PARAMETROS["BTCUSDT"]["lateral"])

if __name__ == "__main__":
    print("=== CONFIGURACION DE CARTERA ===")
    print(f"Capital base         : ${CAPITAL_BASE}")
    print(f"Capital max por op   : {CAPITAL_MAX_POR_OP*100}%")
    print(f"Monto minimo Binance : ${MONTO_MINIMO_BINANCE}")
    print(f"\nCapital por moneda con ${CAPITAL_BASE}:")
    for symbol, monto in capital_por_moneda(CAPITAL_BASE).items():
        print(f"  {symbol}: ${monto} ({PESOS_CARTERA[symbol]}%)")
    print(f"\nParametros optimizados:")
    for symbol, fases in PARAMETROS.items():
        for fase, p in fases.items():
            print(f"  {symbol} {fase.upper()}: RSI {p['rsi_min']}-{p['rsi_max']} SL {p['sl']}% TP {p['tp']}% EMA {p['ec']}/{p['el']}")
