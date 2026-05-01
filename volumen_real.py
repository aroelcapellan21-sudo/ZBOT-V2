# =========================================
# volumen_real.py - Volumen Real + CMF + MFI
# FIX: Rutas absolutas
# FIX: except pass eliminados
# MEJORA: CMF (Chaikin Money Flow) agregado
# MEJORA: MFI (Money Flow Index) agregado
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import time
import urllib.request
import urllib.parse
import os
from datetime import datetime

MONEDAS       = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'AVAXUSDT']
ARCHIVO_CSV   = os.path.expanduser("~/bot-padre-v2/data/volumen_real.csv")
ESTADO_JSON   = os.path.expanduser("~/bot-padre-v2/signals/estado_volumen.json")

UMBRAL_INYECCION = 2.0
VENTANA_MEDIA    = 20
PERIODO_CMF      = 20
PERIODO_MFI      = 14
INTERVALO        = 60

def obtener_velas(symbol, intervalo="1m", limite=50):
    try:
        params = urllib.parse.urlencode({
            "symbol":   symbol,
            "interval": intervalo,
            "limit":    limite
        })
        url = f"https://api.binance.com/api/v3/klines?{params}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[VOLUMEN] Error fetch {symbol}: {e}")
        return []

def calcular_cmf(velas, periodo=20):
    if len(velas) < periodo:
        return None
    velas_periodo = velas[-periodo:]
    suma_mfv = 0.0
    suma_vol = 0.0
    for v in velas_periodo:
        alto   = float(v[2])
        bajo   = float(v[3])
        cierre = float(v[4])
        vol    = float(v[5])
        rango  = alto - bajo
        if rango == 0:
            continue
        mfv = ((cierre - bajo) - (alto - cierre)) / rango * vol
        suma_mfv += mfv
        suma_vol += vol
    if suma_vol == 0:
        return None
    return round(suma_mfv / suma_vol, 4)

def calcular_mfi(velas, periodo=14):
    if len(velas) < periodo + 1:
        return None
    precios_tipicos = []
    for v in velas:
        alto   = float(v[2])
        bajo   = float(v[3])
        cierre = float(v[4])
        vol    = float(v[5])
        pt     = (alto + bajo + cierre) / 3
        precios_tipicos.append((pt, vol))
    mf_pos = 0.0
    mf_neg = 0.0
    for i in range(len(precios_tipicos) - periodo, len(precios_tipicos)):
        pt_actual   = precios_tipicos[i][0]
        pt_anterior = precios_tipicos[i-1][0]
        vol         = precios_tipicos[i][1]
        raw_mf      = pt_actual * vol
        if pt_actual > pt_anterior:
            mf_pos += raw_mf
        elif pt_actual < pt_anterior:
            mf_neg += raw_mf
    if mf_neg == 0:
        return 100.0
    if mf_pos == 0:
        return 0.0
    return round(100 - (100 / (1 + mf_pos / mf_neg)), 2)

def interpretar_cmf(cmf):
    if cmf is None:
        return "SIN_DATOS"
    if cmf > 0.15:
        return "COMPRA_FUERTE"
    elif cmf > 0.05:
        return "COMPRA_DEBIL"
    elif cmf < -0.15:
        return "VENTA_FUERTE"
    elif cmf < -0.05:
        return "VENTA_DEBIL"
    else:
        return "NEUTRAL"

def interpretar_mfi(mfi):
    if mfi is None:
        return "SIN_DATOS"
    if mfi >= 80:
        return "SOBRECOMPRA"
    elif mfi >= 60:
        return "PRESION_COMPRA"
    elif mfi <= 20:
        return "SOBREVENTA"
    elif mfi <= 40:
        return "PRESION_VENTA"
    else:
        return "NEUTRAL"

def detectar_inyeccion(velas):
    if len(velas) < VENTANA_MEDIA + 1:
        return "SIN_DATOS", None
    volumenes  = [float(v[5]) for v in velas[:-1]]
    vol_actual = float(velas[-2][5])
    promedio   = sum(volumenes[-VENTANA_MEDIA:]) / VENTANA_MEDIA
    if promedio == 0:
        return "SIN_DATOS", None
    ratio = round(vol_actual / promedio, 2)
    if ratio >= UMBRAL_INYECCION:
        return "INYECCION", ratio
    return "NORMAL", ratio

def guardar_csv(timestamp, symbol, estado, ratio, cmf, mfi):
    try:
        os.makedirs(os.path.dirname(ARCHIVO_CSV), exist_ok=True)
        escribir_header = not os.path.exists(ARCHIVO_CSV) or os.path.getsize(ARCHIVO_CSV) == 0
        with open(ARCHIVO_CSV, "a") as f:
            if escribir_header:
                f.write("timestamp,symbol,estado,ratio,cmf,mfi\n")
            f.write(f"{timestamp},{symbol},{estado},{ratio},{cmf},{mfi}\n")
    except Exception as e:
        print(f"[VOLUMEN] Error guardando CSV: {e}")

def guardar_estado(resultados):
    try:
        os.makedirs(os.path.dirname(ESTADO_JSON), exist_ok=True)
        with open(ESTADO_JSON, 'w') as f:
            json.dump({
                "timestamp":  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "resultados": resultados
            }, f, indent=2)
    except Exception as e:
        print(f"[VOLUMEN] Error guardando estado: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("💰 volumen_real - Volumen Real + CMF + MFI")
    print(f"   Monedas  : {', '.join(MONEDAS)}")
    print(f"   Intervalo: {INTERVALO}s")
    print("=" * 50)

    while True:
        try:
            timestamp  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            resultados = []

            print(f"\n[{timestamp}] 💰 VOLUMEN REAL")
            print(f"  {'─'*48}")

            for symbol in MONEDAS:
                velas = obtener_velas(symbol, limite=50)
                if not velas:
                    continue

                estado_iny, ratio = detectar_inyeccion(velas)
                cmf               = calcular_cmf(velas, PERIODO_CMF)
                mfi               = calcular_mfi(velas, PERIODO_MFI)
                interp_cmf        = interpretar_cmf(cmf)
                interp_mfi        = interpretar_mfi(mfi)

                emoji_iny = "🔥" if estado_iny == "INYECCION" else "✓"
                cmf_str   = f"{cmf:.4f}" if cmf is not None else "N/A"
                mfi_str   = f"{mfi:.1f}" if mfi is not None else "N/A"

                print(f"  {emoji_iny} {symbol}")
                print(f"     Vol ratio: {ratio}x | CMF: {cmf_str} ({interp_cmf}) | MFI: {mfi_str} ({interp_mfi})")

                guardar_csv(timestamp, symbol, estado_iny, ratio, cmf_str, mfi_str)

                resultados.append({
                    "symbol":     symbol,
                    "estado":     estado_iny,
                    "ratio":      ratio,
                    "cmf":        cmf,
                    "cmf_interp": interp_cmf,
                    "mfi":        mfi,
                    "mfi_interp": interp_mfi
                })

            print(f"  {'─'*48}")
            guardar_estado(resultados)
            time.sleep(INTERVALO)

        except KeyboardInterrupt:
            print("\n🛑 volumen_real detenido")
            break
        except Exception as e:
            print(f"[VOLUMEN] Error en ciclo: {e}")
            time.sleep(10)
