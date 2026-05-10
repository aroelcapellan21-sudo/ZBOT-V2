#!/usr/bin/env python3
"""
reconciliar.py — Z-Bot v2
Detecta crypto huerfana en billetera.json (sin fila ABIERTA en auditoria.csv),
muestra un reporte detallado y pide confirmacion antes de modificar nada.

Uso: python3 reconciliar.py
"""

import csv
import json
import os
import shutil
import urllib.request
import urllib.parse
from datetime import datetime

BASE       = os.path.expanduser("~/bot-padre-v2")
BILLETERA  = os.path.join(BASE, "signals/billetera.json")
AUDITORIA  = os.path.join(BASE, "auditoria.csv")
BACKUP_BIL = os.path.join(BASE, "signals/billetera_pre_reconciliacion.json")
BACKUP_AUD = os.path.join(BASE, "auditoria_pre_reconciliacion.csv")

CRYPTO_MAP = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "SOL":  "SOLUSDT",
    "BNB":  "BNBUSDT",
    "AVAX": "AVAXUSDT",
}
CANTIDAD_MINIMA = 0.000001


def fetch_precio(symbol):
    params = urllib.parse.urlencode({"symbol": symbol})
    url    = f"https://api.binance.com/api/v3/ticker/price?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return float(json.loads(resp.read().decode())["price"])
    except Exception as e:
        print(f"  [ERROR] Precio {symbol}: {e}")
        return None


def cargar_billetera():
    with open(BILLETERA) as f:
        return json.load(f)


def symbols_con_posicion_abierta():
    abiertas = set()
    try:
        with open(AUDITORIA, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("estado", "").strip() == "ABIERTA":
                    abiertas.add(row.get("symbol", "").strip())
    except Exception as e:
        print(f"  [ERROR] Leyendo auditoria: {e}")
    return abiertas


def hacer_backup():
    shutil.copy2(BILLETERA, BACKUP_BIL)
    shutil.copy2(AUDITORIA, BACKUP_AUD)
    print(f"  Backups creados:")
    print(f"    {BACKUP_BIL}")
    print(f"    {BACKUP_AUD}")


def main():
    sep = "=" * 62
    print(f"\n{sep}")
    print("  RECONCILIACIÓN DE POSICIONES HUÉRFANAS — Z-Bot v2")
    print(sep)

    billetera    = cargar_billetera()
    monitoreados = symbols_con_posicion_abierta()
    ahora        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    usdt_actual  = float(billetera.get("USDT", 0))

    print(f"\n  Fecha/Hora  : {ahora}")
    print(f"  USDT actual : ${usdt_actual:,.4f}")
    print(f"  Posiciones monitoreadas en auditoria: {monitoreados or 'ninguna'}")

    huerfanas = []
    errores   = []

    print(f"\n  Analizando billetera...\n")
    for moneda, symbol in CRYPTO_MAP.items():
        cantidad = float(billetera.get(moneda, 0))

        if cantidad <= CANTIDAD_MINIMA:
            print(f"  {moneda:<5} {cantidad:.8f} — sin saldo significativo. Omitida.")
            continue

        if symbol in monitoreados:
            print(f"  {moneda:<5} {cantidad:.8f} — posición ABIERTA en auditoria. Omitida.")
            continue

        print(f"  {moneda:<5} {cantidad:.8f} — HUÉRFANA. Obteniendo precio...")
        precio = fetch_precio(symbol)
        if precio is None:
            errores.append(moneda)
            print(f"         ⚠️  Sin precio. Se omite por seguridad.")
            continue

        valor_usdt = round(cantidad * precio, 4)
        huerfanas.append({
            "moneda":     moneda,
            "symbol":     symbol,
            "cantidad":   cantidad,
            "precio":     precio,
            "valor_usdt": valor_usdt,
        })
        print(f"         Precio: ${precio:,.2f} | Valor: ${valor_usdt:,.4f} USDT")

    if not huerfanas:
        print(f"\n  Sin posiciones huérfanas detectadas.")
        if errores:
            print(f"  Monedas con error de precio (no procesadas): {errores}")
        print(f"\n{sep}\n")
        return

    total_recuperar = round(sum(h["valor_usdt"] for h in huerfanas), 4)
    usdt_final      = round(usdt_actual + total_recuperar, 4)

    print(f"\n{sep}")
    print("  REPORTE")
    print(sep)
    print(f"  {'Moneda':<6} {'Cantidad':>18} {'Precio':>14} {'Valor USDT':>12}")
    print(f"  {'-'*54}")
    for h in huerfanas:
        print(f"  {h['moneda']:<6} {h['cantidad']:>18.8f} {h['precio']:>14,.2f} {h['valor_usdt']:>12,.4f}")
    print(f"  {'-'*54}")
    print(f"  {'TOTAL':>40} {total_recuperar:>12,.4f}")
    print()
    print(f"  USDT antes   : ${usdt_actual:,.4f}")
    print(f"  USDT después : ${usdt_final:,.4f}  (+${total_recuperar:,.4f})")

    if errores:
        print(f"\n  ⚠️  Monedas NO procesadas por error de precio: {errores}")

    print(f"\n{sep}")
    print("  Escribe 'si' para confirmar, cualquier otra cosa cancela.")
    print(sep)
    respuesta = input("  > ").strip().lower()

    if respuesta != "si":
        print("\n  Cancelado. No se modificó ningún archivo.\n")
        return

    print("\n  Creando backups...")
    hacer_backup()

    print("\n  Aplicando cambios...")
    for h in huerfanas:
        billetera[h["moneda"]] = 0.0
        billetera["USDT"] = round(float(billetera.get("USDT", 0)) + h["valor_usdt"], 4)

        with open(AUDITORIA, "a", newline="") as f:
            csv.writer(f).writerow([
                ahora,
                "RECONCILE",
                h["symbol"],
                round(h["precio"], 4),
                "N/A",
                "RECONCILE",
            ])

        print(f"  ✅ {h['moneda']}: {h['cantidad']:.8f} → 0.0 | +${h['valor_usdt']:,.4f} USDT @ ${h['precio']:,.2f}")

    billetera["ultima_actualizacion"] = ahora[:10]
    with open(BILLETERA, "w") as f:
        json.dump(billetera, f, indent=2)

    print(f"\n{sep}")
    print("  RECONCILIACIÓN COMPLETADA")
    print(sep)
    print(f"  USDT final : ${billetera['USDT']:,.4f}")
    print(f"  Monedas zereadas : {[h['moneda'] for h in huerfanas]}")
    print(f"  Filas añadidas a auditoria.csv : {len(huerfanas)}")
    print(f"\n  Para verificar:")
    print(f"    cat signals/billetera.json")
    print(f"    tail -6 auditoria.csv")
    print(f"{sep}\n")


if __name__ == "__main__":
    main()
