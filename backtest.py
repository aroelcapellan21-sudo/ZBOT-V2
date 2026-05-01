import csv
import random
import os

ARCHIVO = os.path.expanduser("~/bot-padre-v2/data/historico_4h/BTCUSDT_4h.csv")

CAPITAL_INICIAL = 1000.0
MONTO_POR_OP = 10.0
TAKE_PROFIT = 6.0
STOP_LOSS = 3.5
EMA_CORTA = 20
EMA_LARGA = 50
DIFF_EMA_MAX = 2.0
VENTANA_FASE = 30
UMBRAL_FASE = 2.5
RSI_MIN = 45
RSI_MAX = 55
FEE_PCT = 0.001
SLIPPAGE_PCT = 0.0003
MONTECARLO_SIMS = 500

def cargar_csv(ruta):
    datos = []
    with open(ruta) as f:
        reader = csv.DictReader(f)
        for row in reader:
            datos.append({
                "close": float(row["close"]),
                "high": float(row["high"])
            })
    return datos

def calcular_rsi(cierres):
    if len(cierres) < 15: return 50.0
    ganancias = 0.0
    perdidas = 0.0
    for i in range(-14, 0):
        cambio = cierres[i] - cierres[i-1]
        if cambio > 0:
            ganancias += cambio
        else:
            perdidas -= cambio
    if perdidas == 0: return 100.0
    rs = ganancias / 14 / (perdidas / 14)
    return 100 - 100 / (1 + rs)

def calcular_ema(cierres, periodo):
    if len(cierres) < periodo: return cierres[-1]
    k = 2 / (periodo + 1)
    ema = sum(cierres[:periodo]) / periodo
    for p in cierres[periodo:]:
        ema = p * k + ema * (1 - k)
    return ema

def detectar_fase(cierres):
    if len(cierres) < VENTANA_FASE: return "LATERAL"
    cambio = (cierres[-1] - cierres[-VENTANA_FASE]) / cierres[-VENTANA_FASE] * 100
    if cambio > UMBRAL_FASE: return "ALCISTA"
    if cambio < -UMBRAL_FASE: return "BAJISTA"
    return "LATERAL"

def senal_entrada(cierres):
    if len(cierres) < EMA_LARGA + 15: return False
    if detectar_fase(cierres) != "LATERAL": return False
    rsi = calcular_rsi(cierres)
    ema_c = calcular_ema(cierres, EMA_CORTA)
    ema_l = calcular_ema(cierres, EMA_LARGA)
    diff = abs(ema_c - ema_l) / ema_l * 100
    return RSI_MIN <= rsi <= RSI_MAX and diff < DIFF_EMA_MAX

def backtest(datos, trailing_act, trailing_dist):
    capital = CAPITAL_INICIAL
    trades = []
    en_trade = False
    precio_entrada = 0
    precio_max = 0
    sl_actual = 0
    
    cierres = [d["close"] for d in datos]
    highs = [d["high"] for d in datos]
    
    for i in range(EMA_LARGA + 15, len(datos)):
        c_slice = cierres[:i+1]
        precio = cierres[i]
        high = highs[i]
        
        if not en_trade:
            if senal_entrada(c_slice):
                en_trade = True
                precio_entrada = precio * (1 + SLIPPAGE_PCT)
                precio_max = precio_entrada
                sl_actual = precio_entrada * (1 - STOP_LOSS/100)
        else:
            if high > precio_max:
                precio_max = high
            
            gan_max = (precio_max - precio_entrada) / precio_entrada * 100
            
            if gan_max >= trailing_act:
                nuevo_sl = precio_max * (1 - trailing_dist/100)
                if nuevo_sl > sl_actual:
                    sl_actual = nuevo_sl
            
            cambio = (precio - precio_entrada) / precio_entrada * 100
            
            if cambio >= TAKE_PROFIT:
                pct = TAKE_PROFIT * (1 - 2*FEE_PCT - 2*SLIPPAGE_PCT)
                usd = (pct / 100) * MONTO_POR_OP
                capital += usd
                trades.append(usd)
                en_trade = False
                continue
            
            if precio * (1 - SLIPPAGE_PCT) <= sl_actual:
                pct = ((sl_actual - precio_entrada) / precio_entrada * 100) * (1 - 2*FEE_PCT - 2*SLIPPAGE_PCT)
                usd = (pct / 100) * MONTO_POR_OP
                capital += usd
                trades.append(usd)
                en_trade = False
    
    return capital, trades

def montecarlo(trades):
    if not trades: return 0, 0
    dds = []
    caps = []
    base = trades[:]
    
    for _ in range(MONTECARLO_SIMS):
        random.shuffle(base)
        cap = CAPITAL_INICIAL
        peak = CAPITAL_INICIAL
        for t in base:
            cap += t
            if cap > peak:
                peak = cap
            dd = (peak - cap) / peak * 100
            if dd > max(dds) if dds else 0:
                dds.append(dd)
        caps.append(cap)
    
    dds.sort()
    caps.sort()
    return dds[int(len(dds)*0.95)], caps[int(len(caps)*0.5)]

datos = cargar_csv(ARCHIVO)

print("RESULTADOS 9 AÑOS")
print("================")

VARIANTES = [
    (0.5, 1.5, "GANADORA 0.5/1.5"),
    (1.0, 1.5, "1.0/1.5"), 
    (3.0, 2.0, "ORIGINAL 3.0/2.0")
]

for act, dist, nombre in VARIANTES:
    capital, trades = backtest(datos, act, dist)
    dd95, cap_mc = montecarlo(trades)
    wr = len([t for t in trades if t > 0]) / len(trades) * 100 if trades else 0
    
    print()
    print(nombre)
    print("Trades:", len(trades))
    print("Capital: $%.2f" % capital)
    print("Winrate: %.1f%%" % wr)
    print("MC DD95: %.2f%%" % dd95)
    print("MC Capital: $%.2f" % cap_mc)
    print("-" * 30)

print("OK")
