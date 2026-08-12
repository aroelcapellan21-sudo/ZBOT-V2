#!/usr/bin/env python3
"""
validar_testnet.py — Validación del camino de dinero contra Binance TESTNET

Responde la pregunta que ninguna prueba anterior respondió: despues de un ciclo
completo con ordenes REALES, ¿billetera.json cuadra contra el saldo que reporta
el exchange?

Todo lo que se hizo hasta ahora fue SIMULADOR y sandbox. Los bugs #3 (round()
pedia mas cripto de la que hay) y #4 (executedQty bruto, sin descontar
comision) habrian aparecido solos con este test.

AISLADO A PROPOSITO:
  - No toca ningun modulo del bot. Solo redirige, en memoria y para este
    proceso, las rutas y la URL base de ejecutor/gestor_billetera.
  - Estado propio: signals/billetera_testnet.json e historial_testnet.csv.
    signals/billetera.json y auditoria.csv de produccion NO se abren.
  - Keys propias: keys_testnet.env. keys.env de produccion NO se lee.

Uso:
    python3 validar_testnet.py              # dry run: solo diagnostico
    python3 validar_testnet.py --ejecutar   # manda ordenes REALES a testnet
    python3 validar_testnet.py --ejecutar --monto 25 --moneda ETH
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE_TESTNET   = "https://testnet.binance.vision"
BASE_PRODUCCION = "https://api.binance.com"
HOME           = os.path.expanduser("~/bot-padre-v2")
KEYS_TESTNET   = os.path.join(HOME, "keys_testnet.env")
BILLETERA_TEST = os.path.join(HOME, "signals/billetera_testnet.json")
HISTORIAL_TEST = os.path.join(HOME, "historial_testnet.csv")
MONEDAS        = ["BTC", "ETH", "SOL", "BNB", "AVAX"]


# ----------------------------------------------------------------- utilidades
def _keys():
    api = sec = None
    with open(KEYS_TESTNET) as f:
        for l in f:
            if l.startswith("BINANCE_API_KEY="):
                api = l.strip().split("=", 1)[1]
            elif l.startswith("BINANCE_SECRET_KEY="):
                sec = l.strip().split("=", 1)[1]
    if not api or not sec:
        raise RuntimeError(f"Faltan keys en {KEYS_TESTNET}")
    return api, sec


def cuenta_testnet():
    """Saldos REALES de la cuenta de testnet, via /api/v3/account firmado."""
    api, sec = _keys()
    q   = urllib.parse.urlencode({"timestamp": int(time.time() * 1000), "recvWindow": 5000})
    sig = hmac.new(sec.encode(), q.encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{BASE_TESTNET}/api/v3/account?{q}&signature={sig}",
                                 headers={"X-MBX-APIKEY": api})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    return {b["asset"]: float(b["free"]) + float(b["locked"]) for b in data["balances"]}


def precio_testnet(symbol):
    url = f"{BASE_TESTNET}/api/v3/ticker/price?symbol={symbol}"
    with urllib.request.urlopen(url, timeout=10) as r:
        return float(json.loads(r.read())["price"])


# ------------------------------------------------------------------- blindaje
def blindar(ejecutor, gestor):
    """
    Redirige TODO a testnet y aborta si algo quedo apuntando a produccion.
    Se corre ANTES de habilitar el envio de ordenes reales: sin esto, activar
    el modo REAL con la URL de produccion moveria dinero de verdad.
    """
    ejecutor.BASE_URL  = BASE_TESTNET
    ejecutor.KEYS_FILE = KEYS_TESTNET
    ejecutor.BILLETERA = BILLETERA_TEST
    ejecutor.LOCK_FILE = BILLETERA_TEST + ".lock"
    gestor.BILLETERA           = BILLETERA_TEST
    gestor._LOCK_PATH          = BILLETERA_TEST + ".lock"
    gestor.HISTORIAL_BILLETERA = HISTORIAL_TEST

    fallos = []
    if ejecutor.BASE_URL != BASE_TESTNET:
        fallos.append("ejecutor.BASE_URL no es testnet")
    if BASE_PRODUCCION in ejecutor.BASE_URL:
        fallos.append("ejecutor.BASE_URL apunta a PRODUCCION")
    if ejecutor.KEYS_FILE != KEYS_TESTNET:
        fallos.append("ejecutor.KEYS_FILE no es el de testnet")
    if "billetera_testnet" not in ejecutor.BILLETERA:
        fallos.append("ejecutor.BILLETERA no es la de testnet")
    if "billetera_testnet" not in gestor.BILLETERA:
        fallos.append("gestor_billetera.BILLETERA no es la de testnet")
    if fallos:
        raise RuntimeError("BLINDAJE FALLIDO: " + "; ".join(fallos))
    return True


def sincronizar_billetera(saldos_api):
    """billetera_testnet.json arranca reflejando el saldo REAL de testnet."""
    b = {"USDT": round(saldos_api.get("USDT", 0.0), 8),
         "capital_inicial": round(saldos_api.get("USDT", 0.0), 8),
         "ultima_actualizacion": time.strftime("%Y-%m-%d")}
    for m in MONEDAS:
        b[m] = round(saldos_api.get(m, 0.0), 8)
    os.makedirs(os.path.dirname(BILLETERA_TEST), exist_ok=True)
    with open(BILLETERA_TEST, "w") as f:
        json.dump(b, f, indent=2)
    return b


def comparar(etiqueta, moneda, saldos_api):
    """Compara billetera_testnet.json contra el saldo real. Devuelve (dU, dC)."""
    libro = json.load(open(BILLETERA_TEST))
    lu, ru = libro.get("USDT", 0.0), saldos_api.get("USDT", 0.0)
    lc, rc = libro.get(moneda, 0.0), saldos_api.get(moneda, 0.0)
    du, dc = round(lu - ru, 6), round(lc - rc, 10)
    print(f"\n  --- {etiqueta} ---")
    print(f"    {'':<10} {'LIBRO':>18} {'EXCHANGE':>18} {'DESVIO':>16}")
    print(f"    {'USDT':<10} {lu:>18.6f} {ru:>18.6f} {du:>16.6f}")
    print(f"    {moneda:<10} {lc:>18.8f} {rc:>18.8f} {dc:>16.10f}")
    return du, dc


# ---------------------------------------------------------------------- ciclo
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecutar", action="store_true",
                    help="manda ordenes REALES a testnet (sin esto solo diagnostica)")
    ap.add_argument("--moneda", default="BTC", choices=MONEDAS)
    ap.add_argument("--monto", type=float, default=20.0)
    args = ap.parse_args()

    symbol = args.moneda + "USDT"
    print("=" * 72)
    print("  VALIDACION CONTRA BINANCE TESTNET")
    print("=" * 72)

    # --- 1. preflight
    if not os.path.exists(KEYS_TESTNET):
        sys.exit(f"  FALTA {KEYS_TESTNET}")
    try:
        saldos = cuenta_testnet()
    except Exception as e:
        sys.exit(f"  No se pudo leer la cuenta de testnet: {e}")

    precio = precio_testnet(symbol)
    print(f"\n  Endpoint  : {BASE_TESTNET}")
    print(f"  Keys      : {KEYS_TESTNET}")
    print(f"  Par       : {symbol} @ ${precio:,.2f} (precio de TESTNET)")
    print(f"  Monto     : ${args.monto}")
    print(f"\n  Saldo en la cuenta de testnet:")
    for a in ["USDT"] + MONEDAS:
        if saldos.get(a, 0) > 0:
            print(f"    {a:<6} {saldos[a]:.8f}")

    if saldos.get("USDT", 0) < args.monto:
        sys.exit(f"\n  USDT insuficiente en testnet ({saldos.get('USDT',0)} < {args.monto})")

    if not args.ejecutar:
        print(f"\n  DRY RUN — no se envio ninguna orden.")
        print(f"  Para ejecutar el ciclo real:  python3 validar_testnet.py --ejecutar")
        print("=" * 72)
        return

    # --- 2. blindaje ANTES de habilitar ordenes reales
    import ejecutor, gestor_billetera
    blindar(ejecutor, gestor_billetera)
    print(f"\n  Blindaje OK: ejecutor apunta a {ejecutor.BASE_URL}")
    print(f"  Estado en  : {BILLETERA_TEST}")

    # Recien ahora se habilita el envio real, ya con la URL de testnet fijada.
    ejecutor._leer_modo = lambda: "REAL"
    os.environ["BOT_REAL_CONFIRMADO"] = "true"

    sincronizar_billetera(saldos)
    print(f"  billetera_testnet.json sincronizada con el saldo real")

    # --- 3. APERTURA
    print("\n" + "=" * 72)
    print("  PASO 1 — APERTURA (orden real de compra en testnet)")
    print("=" * 72)
    res, fill = ejecutor.ejecutar_operacion(args.moneda, "COMPRA", precio, args.monto)
    print(f"  {res}")
    if not fill:
        sys.exit("  La compra fallo. Se aborta sin cerrar nada.")
    print(f"  fill: qty={fill['qty']}  usdt={fill['usdt']}  precio={fill['precio']}")

    time.sleep(2)
    du1, dc1 = comparar("TRAS LA APERTURA", args.moneda, cuenta_testnet())

    # --- 4. CIERRE (camino del SL)
    print("\n" + "=" * 72)
    print("  PASO 2 — CIERRE POR SL (orden real de venta en testnet)")
    print("=" * 72)
    res_c, fill_c = ejecutor.cerrar_posicion(args.moneda, "LATERAL",
                                             fill["precio"], args.monto, qty=fill["qty"])
    print(f"  {res_c}")
    if not fill_c:
        sys.exit("  El cierre fallo. La posicion queda abierta en testnet.")
    print(f"  fill: qty={fill_c['qty']}  usdt={fill_c['usdt']}  precio={fill_c['precio']}")

    gestor_billetera.registrar_sl(fill["precio"], fill_c["precio"], args.monto,
                                  args.moneda, "LATERAL",
                                  qty=fill_c["qty"], usdt=fill_c["usdt"])

    time.sleep(2)
    saldos_fin = cuenta_testnet()
    du2, dc2 = comparar("TRAS EL CIERRE", args.moneda, saldos_fin)

    # --- 5. veredicto
    print("\n" + "=" * 72)
    print("  VEREDICTO")
    print("=" * 72)
    libro = json.load(open(BILLETERA_TEST))
    costo_real = round(saldos["USDT"] - saldos_fin["USDT"], 6)
    nocional   = fill["qty"] * fill["precio"]
    print(f"  Costo real del round-trip : ${costo_real:.6f}"
          f"  ({costo_real / nocional * 100:.3f}% del nocional)")
    print(f"  Esperado por comision     : ~0.200% (0.1% por lado)")
    print(f"\n  Desvio final libro vs exchange:")
    print(f"    USDT        : {du2:+.6f}")
    print(f"    {args.moneda:<12}: {dc2:+.10f}")

    tol_u, tol_c = 0.01, 1e-8
    ok = abs(du2) <= tol_u and abs(dc2) <= tol_c
    print(f"\n  {'✅ CUADRA' if ok else '❌ NO CUADRA'}"
          f"   (tolerancia: ${tol_u} USDT, {tol_c} en cripto)")
    if not ok:
        print(f"\n  El libro y el exchange no coinciden. Revisar:")
        print(f"    - comision no descontada del fill (ver _extraer_fill)")
        print(f"    - truncado al stepSize (ver _truncar_cantidad)")
        print(f"    - polvo por el redondeo del lot size")

    # --- 6. invariante del bug #3, que el exchange NO puede delatar aca
    # La cuenta de testnet tiene saldo previo grande (1.0 BTC), asi que vender
    # de mas NUNCA daria -2010: hay de sobra para cubrirlo. Se verifica directo.
    print("\n" + "=" * 72)
    print("  CHEQUEOS QUE EL EXCHANGE NO PUEDE DELATAR EN ESTA CUENTA")
    print("=" * 72)
    qty_compra = fill["qty"]
    qty_venta  = fill_c["qty"]
    inv_ok = qty_venta <= qty_compra + 1e-12
    print(f"  Comprado : {qty_compra:.8f}")
    print(f"  Vendido  : {qty_venta:.8f}")
    print(f"  {'✅' if inv_ok else '❌'} vendido <= comprado"
          f"   (bug #3: round() pedia mas de lo que hay)")

    # Que habria hecho el codigo viejo con este mismo fill
    dec   = ejecutor.LOT_SIZE.get(symbol, 6)
    viejo = round(args.monto / fill["precio"], dec)
    print(f"\n  Con el codigo viejo (round) se habria intentado vender: {viejo:.8f}")
    print(f"  {'⚠️  habria excedido lo comprado' if viejo > qty_compra else '   no habria excedido en este caso'}")

    print(f"\n  ⚠️  PUNTOS CIEGOS DE ESTA VALIDACION:")
    print(f"    1. Testnet cobra comision CERO (takerCommission=0), asi que el")
    print(f"       descuento de comision de _extraer_fill NO se ejercito. El bug")
    print(f"       #4 (executedQty bruto) no se puede detectar aca.")
    print(f"    2. La cuenta tiene saldo previo grande ({saldos.get(args.moneda,0):.4f} {args.moneda}), asi que")
    print(f"       vender de mas no produce el rechazo -2010 que si daria una")
    print(f"       cuenta real con solo la posicion.")
    print("=" * 72)
    sys.exit(0 if (ok and inv_ok) else 1)


if __name__ == "__main__":
    main()
