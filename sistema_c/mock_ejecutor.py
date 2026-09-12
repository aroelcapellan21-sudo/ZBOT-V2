"""Mock de `ejecutor` para los sandboxes de sistema_c/, con el gate de sl_pct.

POR QUE EXISTE (12-sep-2026, item 0b). El 31-ago `ejecutar_operacion()` sumo el
parametro `sl_pct` y con el un rechazo nuevo: si la posicion valdria menos que
el minimo de Binance al tocar su stop, la orden NO se manda. Los 13 sandboxes
de sistema_c/ mockeaban la firma vieja, asi que desde entonces (a) reventaban
con TypeError contra los francotiradores que ya pasan el argumento, y (b) de
haber seguido corriendo habrian medido un bot que acepta operaciones que el
real rechaza.

La logica vive UNA vez, aca, y los 13 la importan. Los valores que dependen de
produccion (LOT_SIZE, MONTO_MINIMO_BINANCE) se leen del propio `ejecutor.py`
con `ast`, sin importarlo — importarlo tocaria keys.env y la API. Si manana
cambian alla, cambian aca solos.

⚠️ MEDIDO ANTES DE ESCRIBIR ESTO (reporte del 12-sep): con el monto de $5 que
simulo el torneo, este gate rechaza el 100 % de las entradas — es aritmetica,
no truncamiento: $5 con un SL de 3,5 % valen $4,83 al stop, bajo el minimo de
$5. El monto minimo viable es $5,18. Con los montos de produccion ($7, y $10
en BTC) el rechazo cae al 0,6 % y mueve el PF entre 0,000 y +0,033.
**Un sandbox que use este mock tiene que simular el monto real, no $5.**
"""

import ast
import os

_EJECUTOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ejecutor.py")


def _constantes_de_produccion():
    """LOT_SIZE y MONTO_MINIMO_BINANCE leidos de ejecutor.py sin importarlo."""
    with open(_EJECUTOR, encoding="utf-8") as fh:
        arbol = ast.parse(fh.read(), _EJECUTOR)
    vals = {}
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and isinstance(nodo.targets[0], ast.Name):
            nombre = nodo.targets[0].id
            if nombre in ("LOT_SIZE", "MONTO_MINIMO_BINANCE", "COMISION_SPOT"):
                try:
                    vals[nombre] = ast.literal_eval(nodo.value)
                except (ValueError, TypeError, SyntaxError):
                    pass
    faltan = {"LOT_SIZE", "MONTO_MINIMO_BINANCE"} - set(vals)
    if faltan:
        raise RuntimeError(f"no se pudieron leer de ejecutor.py: {sorted(faltan)}")
    return vals


_C = _constantes_de_produccion()
LOT_SIZE = _C["LOT_SIZE"]
MONTO_MINIMO_BINANCE = _C["MONTO_MINIMO_BINANCE"]
COMISION_SPOT = _C.get("COMISION_SPOT", 0.001)


def truncar_cantidad(symbol, qty):
    """Trunca al LOT_SIZE, igual que ejecutor._truncar_cantidad."""
    from decimal import Decimal, ROUND_DOWN
    paso = Decimal(1).scaleb(-LOT_SIZE.get(symbol, 6))
    return float(Decimal(str(qty)).quantize(paso, rounding=ROUND_DOWN))


def valor_estimado_al_stop(symbol, monto, precio, sl_pct):
    """Copia de ejecutor._valor_estimado_al_stop: truncar, comision, truncar."""
    qty = truncar_cantidad(symbol, monto / precio)
    qty = truncar_cantidad(symbol, qty * (1 - COMISION_SPOT))
    return qty * precio * (1 - sl_pct / 100.0)


def rechazo_por_sl(symbol, monto, precio, sl_pct):
    """El mensaje de rechazo si el SL seria inejecutable, o None si pasa."""
    if not sl_pct:
        return None
    valor = valor_estimado_al_stop(symbol, monto, precio, sl_pct)
    if valor >= MONTO_MINIMO_BINANCE:
        return None
    return (f"❌ RECHAZADO: SL inejecutable — con ${monto:.2f} de entrada y SL {sl_pct}%, "
            f"la posicion valdria ${valor:.2f} al tocar el stop, bajo el minimo de Binance "
            f"(${MONTO_MINIMO_BINANCE})")
