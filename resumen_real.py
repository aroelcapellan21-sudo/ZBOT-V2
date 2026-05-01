#!/usr/bin/env python3
# =========================================
# resumen_real.py - Estado Real del Capital
# =========================================

import json
import urllib.request
import csv
from datetime import datetime
import os

BILLETERA = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
AUDITORIA = os.path.expanduser("~/bot-padre-v2/auditoria.csv")

def obtener_precios():
    url = "https://api.binance.com/api/v3/ticker/price"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            datos = json.loads(r.read().decode())
            return {d['symbol']: float(d['price']) for d in datos}
    except:
        return {}

def cargar_billetera():
    with open(BILLETERA) as f:
        return json.load(f)

def analizar_auditoria():
    ops = {"TP": 0, "SL": 0, "TRAILING_SL": 0, "ABIERTA": 0}
    total = 0
    with open(AUDITORIA) as f:
        reader = csv.DictReader(f)
        for row in reader:
            estado = row.get("estado", "").strip()
            if estado in ops:
                ops[estado] += 1
            total += 1
    return ops, total

def main():
    precios = obtener_precios()
    billetera = cargar_billetera()
    ops, total = analizar_auditoria()

    capital_inicial = billetera.get("capital_inicial", 1000.0)
    usdt = billetera.get("USDT", 0)

    # Calcular valor de monedas en USDT
    monedas = {
        "BTC": ("BTCUSDT", billetera.get("BTC", 0)),
        "ETH": ("ETHUSDT", billetera.get("ETH", 0)),
        "SOL": ("SOLUSDT", billetera.get("SOL", 0)),
        "BNB": ("BNBUSDT", billetera.get("BNB", 0)),
        "AVAX": ("AVAXUSDT", billetera.get("AVAX", 0)),
    }

    print("\n" + "="*48)
    print("💰 RESUMEN REAL DE CAPITAL — Z-Bot V2")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*48)

    print("\n📦 ACTIVOS EN CARTERA:")
    print(f"  {'Moneda':<8} {'Cantidad':>12} {'Precio':>12} {'Valor USDT':>12}")
    print(f"  {'─'*46}")

    total_monedas_usdt = 0
    for nombre, (symbol, cantidad) in monedas.items():
        precio = precios.get(symbol, 0)
        valor = cantidad * precio
        total_monedas_usdt += valor
        if cantidad > 0:
            print(f"  {nombre:<8} {cantidad:>12.6f} {precio:>12.2f} {valor:>12.4f}")

    print(f"  {'─'*46}")
    print(f"  {'USDT':<8} {usdt:>12.4f} {'':>12} {usdt:>12.4f}")

    capital_total = usdt + total_monedas_usdt
    ganancia = capital_total - capital_inicial
    pct = (ganancia / capital_inicial) * 100

    print(f"\n{'='*48}")
    print(f"  Capital inicial : ${capital_inicial:>10.2f}")
    print(f"  Capital total   : ${capital_total:>10.4f}")
    emoji = "📈" if ganancia >= 0 else "📉"
    print(f"  {emoji} Resultado    : ${ganancia:>+10.4f}  ({pct:+.2f}%)")
    print(f"{'='*48}")

    print(f"\n📊 HISTORIAL DE OPERACIONES ({total} total):")
    print(f"  ✅ TP           : {ops['TP']}")
    print(f"  🛑 SL           : {ops['SL']}")
    print(f"  🎯 Trailing SL  : {ops['TRAILING_SL']}")
    print(f"  🔴 Abiertas     : {ops['ABIERTA']}")
    win_rate = (ops['TP'] / (ops['TP'] + ops['SL'] + ops['TRAILING_SL'])) * 100 if (ops['TP'] + ops['SL'] + ops['TRAILING_SL']) > 0 else 0
    print(f"  🏆 Win Rate     : {win_rate:.1f}%")
    print("="*48 + "\n")

if __name__ == "__main__":
    main()
