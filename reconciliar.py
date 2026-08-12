#!/usr/bin/env python3
"""
reconciliar.py — Z-Bot v2

Barre la cripto que quedo en billetera.json sin respaldar ninguna posicion:
el "polvo" del truncado al lot size mas residuo historico.

Barre FUERA del ciclo de trades y lo registra como fila RECONCILE propia, para
que ningun trade se lleve el credito del polvo ajeno (por eso NO se barre
dentro de cerrar_posicion).

Dos entradas, las dos manuales:
  - python3 reconciliar.py        -> reporte + confirmacion por teclado
  - /reconciliar en Telegram      -> reporte; /reconciliar confirmar ejecuta

NO hay version automatica: desde 2026-08-12 esto vende de verdad en Binance,
asi que es una accion con dinero y siempre exige confirmacion humana.
"""

import csv
import fcntl
import json
import os
import shutil
import urllib.request
import urllib.parse
from datetime import datetime

from ejecutor import cerrar_posicion, _truncar_cantidad
from gestor_billetera import (
    _billetera_lock, cargar_billetera as _cargar_billetera_gb,
    guardar_billetera, registrar_historial_billetera,
)

try:
    from engine import enviar_aviso as _aviso
except Exception:
    def _aviso(msg):
        print(f"[RECONCILE] Telegram no disponible: {msg}")

BASE           = os.path.expanduser("~/bot-padre-v2")
BILLETERA      = os.path.join(BASE, "signals/billetera.json")
AUDITORIA      = os.path.join(BASE, "auditoria.csv")
AUDITORIA_LOCK = AUDITORIA + ".lock"
BACKUP_DIR     = os.path.join(BASE, "signals")

CRYPTO_MAP = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "SOL":  "SOLUSDT",
    "BNB":  "BNBUSDT",
    "AVAX": "AVAXUSDT",
}

# Binance rechaza ordenes por debajo de este notional. Antes el umbral era
# CANTIDAD_MINIMA=0.000001, una cantidad de cripto sin relacion con lo que el
# exchange acepta: servia mientras esto no vendia de verdad.
MIN_NOTIONAL = 5.0

# Una fila RESERVADA ya tiene la cripto comprada (el fix #5 escribe la fila
# antes de mandar la orden). Si no se contara, el barrido podria vender la
# cripto de una compra recien ejecutada.
ESTADOS_COMPROMETIDOS = ("ABIERTA", "RESERVADA")


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


def calcular_comprometido():
    """
    Cripto que NO se puede tocar: la que respalda posiciones ABIERTA o
    RESERVADA. Devuelve {moneda: qty}.

    Se reserva exactamente lo que va a pedir cerrar_posicion: la columna 'qty'
    si existe (fill real, fix #4), y si no el estimado monto/precio_entrada.
    Ese estimado es >= la cantidad real (no descuenta comision), asi que
    reservamos de mas y nunca de menos.
    """
    comprometido = {}
    try:
        with open(AUDITORIA, newline="") as f:
            for linea in f.readlines()[1:]:
                p = linea.rstrip("\n").split(",")
                if len(p) < 7 or p[5] not in ESTADOS_COMPROMETIDOS:
                    continue
                moneda = p[2].replace("USDT", "")
                try:
                    if len(p) > 7 and p[7].strip():
                        qty = float(p[7])
                    else:
                        qty = float(p[6]) / float(p[3])
                except (ValueError, ZeroDivisionError) as e:
                    print(f"  [RECONCILE] Fila ilegible, se reserva todo {moneda}: {e}")
                    qty = float("inf")
                comprometido[moneda] = comprometido.get(moneda, 0.0) + qty
    except Exception as e:
        raise RuntimeError(f"[RECONCILE] No se pudo leer auditoria.csv: {e}")
    return comprometido


def detectar_polvo():
    """
    Devuelve (barrer, omitidas). 'barrer' son las monedas con excedente
    vendible; 'omitidas' las que tienen excedente pero por debajo del
    minNotional o sin precio.
    """
    billetera    = cargar_billetera()
    comprometido = calcular_comprometido()
    barrer, omitidas = [], []

    for moneda, symbol in CRYPTO_MAP.items():
        saldo = float(billetera.get(moneda, 0))
        if saldo <= 0:
            continue
        reservado = comprometido.get(moneda, 0.0)
        libre     = saldo - reservado
        if libre <= 0:
            continue

        cantidad = _truncar_cantidad(symbol, libre)
        if cantidad <= 0:
            continue

        precio = fetch_precio(symbol)
        if precio is None:
            omitidas.append({"moneda": moneda, "cantidad": cantidad,
                             "motivo": "sin precio de mercado"})
            continue

        valor = round(cantidad * precio, 4)
        item  = {"moneda": moneda, "symbol": symbol, "saldo": saldo,
                 "reservado": reservado, "cantidad": cantidad,
                 "precio": precio, "valor_usdt": valor}
        if valor < MIN_NOTIONAL:
            item["motivo"] = f"${valor:.2f} < minNotional ${MIN_NOTIONAL:.0f}"
            omitidas.append(item)
        else:
            barrer.append(item)

    return barrer, omitidas


def hacer_backup():
    """Backup con timestamp: antes el nombre era fijo y cada corrida pisaba
    el backup anterior."""
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    b1 = os.path.join(BACKUP_DIR, f"billetera_pre_reconciliacion_{sello}.json")
    b2 = os.path.join(BASE,       f"auditoria_pre_reconciliacion_{sello}.csv")
    shutil.copy2(BILLETERA, b1)
    shutil.copy2(AUDITORIA, b2)
    return b1, b2


def _append_fila_reconcile(ahora, symbol, precio, usdt, qty):
    """Fila de 8 columnas, bajo AUDITORIA_LOCK. Antes escribia 6 columnas y
    sin lock: quien reescribe el archivo entero podia perder la fila."""
    _lk = open(AUDITORIA_LOCK, "w")
    fcntl.flock(_lk, fcntl.LOCK_EX)
    try:
        with open(AUDITORIA, "a", newline="") as f:
            csv.writer(f).writerow(
                [ahora, "RECONCILE", symbol, round(precio, 4), "N/A",
                 "RECONCILE", round(usdt, 4), qty]
            )
    finally:
        fcntl.flock(_lk, fcntl.LOCK_UN)
        _lk.close()


def ejecutar_reconciliacion(barrer, origen="manual"):
    """
    Vende de verdad en Binance y recien despues actualiza la billetera.
    Antes esto ponia billetera[moneda] = 0.0 y sumaba el USDT teorico sin
    mandar ninguna orden: en REAL los libros decian USDT y la cripto seguia
    en la cuenta.

    Devuelve (lineas_reporte, total_usdt, fallidas).
    """
    if not barrer:
        return ["Sin polvo vendible."], 0.0, []

    hacer_backup()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lineas, fallidas, total = [], [], 0.0

    for h in barrer:
        # cerrar_posicion con tipo LATERAL => SELL de la cantidad indicada.
        # Ya trunca al stepSize, respeta BOT_REAL_CONFIRMADO y devuelve el fill.
        res, fill = cerrar_posicion(h["moneda"], "LATERAL", h["precio"],
                                    h["valor_usdt"], qty=h["cantidad"])
        if "❌" in res or not fill:
            print(f"  [RECONCILE] Venta fallida {h['moneda']}: {res}")
            fallidas.append(f"{h['moneda']}: {res}")
            lineas.append(f"  ✗ {h['moneda']}: NO vendido — {res}")
            continue

        qty_vendida = float(fill.get("qty") or h["cantidad"])
        usdt_neto   = float(fill.get("usdt") or 0.0)

        # La orden ya se ejecuto: registrar SIEMPRE, aunque la billetera falle.
        _append_fila_reconcile(ahora, h["symbol"], fill.get("precio", h["precio"]),
                               usdt_neto, qty_vendida)
        try:
            with _billetera_lock():
                billetera = _cargar_billetera_gb()
                billetera[h["moneda"]] = max(
                    0.0, round(float(billetera.get(h["moneda"], 0)) - qty_vendida, 8))
                billetera["USDT"] = round(float(billetera.get("USDT", 0)) + usdt_neto, 4)
                billetera["ultima_actualizacion"] = ahora[:10]
                guardar_billetera(billetera)
            registrar_historial_billetera(billetera, "RECONCILE")
        except Exception as e:
            print(f"  [RECONCILE] ⚠️ Venta ejecutada pero billetera no actualizada: {e}")
            fallidas.append(f"{h['moneda']}: vendido pero billetera sin actualizar ({e})")
            lineas.append(f"  ⚠️ {h['moneda']}: vendido ${usdt_neto:.2f} — BILLETERA NO ACTUALIZADA")
            continue

        total += usdt_neto
        lineas.append(f"  ✓ {h['moneda']}: {qty_vendida:.8f} → +${usdt_neto:.2f} USDT")
        print(f"  [RECONCILE] {h['moneda']}: {qty_vendida:.8f} → +${usdt_neto:.4f}")

    return lineas, round(total, 4), fallidas


# ----------------------------------------------------------------- Telegram
def reporte_telegram():
    """Previo, sin tocar nada. Lo usa /reconciliar."""
    try:
        barrer, omitidas = detectar_polvo()
    except Exception as e:
        return f"⚠️ Error analizando: {e}"

    if not barrer and not omitidas:
        return "✅ Sin polvo para reconciliar. Todo el saldo respalda posiciones."

    l = ["🧹 <b>RECONCILIACIÓN — PREVIO</b>", ""]
    if barrer:
        l.append("<b>Se vendería:</b>")
        for h in barrer:
            l.append(f"  {h['moneda']}: {h['cantidad']:.8f} ≈ ${h['valor_usdt']:.2f}")
            if h["reservado"] > 0:
                l.append(f"     (saldo {h['saldo']:.8f} − {h['reservado']:.8f} en posición)")
        l.append("")
        l.append(f"<b>Total a recuperar: ${round(sum(h['valor_usdt'] for h in barrer), 2)}</b>")
    else:
        l.append("Nada vendible ahora mismo.")
    if omitidas:
        l.append("")
        l.append("<b>Omitido:</b>")
        for h in omitidas:
            l.append(f"  {h['moneda']}: {h.get('motivo','')}")
    if barrer:
        l.append("")
        l.append("Para ejecutar: <code>/reconciliar confirmar</code>")
    return "\n".join(l)


def ejecutar_telegram():
    """Ejecuta de verdad. Lo usa /reconciliar confirmar."""
    try:
        barrer, omitidas = detectar_polvo()
    except Exception as e:
        return f"⚠️ Error analizando: {e}"
    if not barrer:
        return "✅ Nada vendible. No se ejecutó ninguna orden."

    lineas, total, fallidas = ejecutar_reconciliacion(barrer, origen="telegram")
    salida = ["🧹 <b>RECONCILIACIÓN EJECUTADA</b>", ""] + lineas
    salida.append("")
    salida.append(f"<b>Recuperado: ${total}</b>")
    if fallidas:
        salida.append("")
        salida.append("⚠️ Con problemas:")
        salida += [f"  {f}" for f in fallidas]
    return "\n".join(salida)


# --------------------------------------------------------------- Interactivo
def main():
    sep = "=" * 62
    print(f"\n{sep}\n  RECONCILIACIÓN DE POLVO — Z-Bot v2\n{sep}")

    try:
        barrer, omitidas = detectar_polvo()
    except Exception as e:
        print(f"\n  ERROR: {e}\n")
        return

    billetera = cargar_billetera()
    print(f"\n  Fecha/Hora  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  USDT actual : ${float(billetera.get('USDT', 0)):,.4f}")

    if omitidas:
        print(f"\n  Omitidas:")
        for h in omitidas:
            print(f"    {h['moneda']:<5} {h.get('motivo','')}")

    if not barrer:
        print(f"\n  Sin polvo vendible.\n{sep}\n")
        return

    print(f"\n{sep}\n  A VENDER\n{sep}")
    print(f"  {'Moneda':<6} {'Cantidad':>18} {'Precio':>14} {'Valor USDT':>12}")
    print(f"  {'-'*54}")
    for h in barrer:
        print(f"  {h['moneda']:<6} {h['cantidad']:>18.8f} {h['precio']:>14,.2f} {h['valor_usdt']:>12,.4f}")
    total_est = round(sum(h["valor_usdt"] for h in barrer), 4)
    print(f"  {'-'*54}\n  {'TOTAL':>40} {total_est:>12,.4f}")

    print(f"\n{sep}\n  Escribe 'si' para VENDER en Binance. Cualquier otra cosa cancela.\n{sep}")
    if input("  > ").strip().lower() != "si":
        print("\n  Cancelado. No se modificó ningún archivo.\n")
        return

    lineas, total, fallidas = ejecutar_reconciliacion(barrer, origen="cli")
    print(f"\n{sep}\n  COMPLETADA\n{sep}")
    for l in lineas:
        print(l)
    print(f"\n  Recuperado: ${total}")
    if fallidas:
        print(f"  Con problemas: {fallidas}")
    print(f"{sep}\n")


if __name__ == "__main__":
    main()
