# =========================================
# libro_ordenes.py
# Libro de ordenes: una fila por orden enviada a Binance (o simulada).
# Append-only, aislado y silencioso. Si falla, NO frena ni rompe una orden.
# No importa nada del bot, no lee la billetera, no usa locks, no lanza nunca.
# =========================================

import os
from datetime import datetime

LIBRO = os.path.expanduser("~/bot-padre-v2/signals/libro_ordenes.csv")

COLUMNAS = [
    "ts_local", "ts_binance", "regimen", "evento", "order_id", "client_order_id",
    "symbol", "moneda", "side", "status", "fase", "motivo", "precio_fill",
    "qty_bruta", "qty_neta", "usdt_bruto", "usdt_neto", "comision",
    "comision_activo", "precio_entrada", "resultado_usd", "nota",
]

def _campo(v):
    """Un campo sin comas ni saltos: el libro se puede leer con split(',')."""
    if v is None:
        return ""
    return str(v).replace("\n", " ").replace("\r", " ").replace(",", ";").strip()

def _escribir(fila):
    """
    Append atomico SIN lock: un unico write() sobre un fd abierto con O_APPEND.
    POSIX no entrelaza escrituras asi mientras la linea sea menor que PIPE_BUF
    (4096 bytes); una fila del libro ronda los 300. No se usa fcntl a proposito:
    un lock es justo lo que podria demorar o trabar una orden.
    """
    linea = (",".join(_campo(c) for c in fila) + "\n").encode("utf-8")
    if len(linea) > 4000:                      # salvaguarda del limite atomico
        linea = (",".join(_campo(c)[:120] for c in fila) + "\n").encode("utf-8")
    nuevo = not os.path.exists(LIBRO)
    fd = os.open(LIBRO, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        if nuevo:
            os.write(fd, (",".join(COLUMNAS) + "\n").encode("utf-8"))
        os.write(fd, linea)
    finally:
        os.close(fd)

def _comisiones(respuesta):
    """Suma la comision del array 'fills' por activo. Devuelve (total, activos)."""
    por_activo = {}
    for f in (respuesta.get("fills") or []):
        try:
            c = float(f.get("commission") or 0)
        except (TypeError, ValueError):
            continue
        a = f.get("commissionAsset") or "?"
        por_activo[a] = round(por_activo.get(a, 0.0) + c, 8)
    return round(sum(por_activo.values()), 8), "+".join(sorted(por_activo))

def anotar_orden(evento, moneda, side, respuesta, regimen, qty_neta=None,
                 usdt_neto=None, fase=None, motivo=None, precio_entrada=None,
                 nota=None):
    """
    Anota una orden ya ejecutada. evento: APERTURA | CIERRE.
    'respuesta' es el dict crudo de Binance (o de _simular_fill).
    Envuelta de punta a punta: cualquier fallo se imprime y se sigue.
    """
    try:
        qty_bruta  = respuesta.get("executedQty")
        usdt_bruto = respuesta.get("cummulativeQuoteQty")
        try:
            precio_fill = round(float(usdt_bruto) / float(qty_bruta), 8)
        except (TypeError, ValueError, ZeroDivisionError):
            precio_fill = respuesta.get("price")
        comision, activo = _comisiones(respuesta)
        ts_bin = respuesta.get("transactTime") or ""
        if ts_bin:
            try:
                ts_bin = datetime.fromtimestamp(int(ts_bin) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError, OSError):
                pass
        _escribir([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ts_bin, regimen, evento,
            respuesta.get("orderId"), respuesta.get("clientOrderId"),
            moneda + "USDT", moneda, side, respuesta.get("status"),
            fase, motivo or "NO_DECLARADO", precio_fill, qty_bruta, qty_neta,
            usdt_bruto, usdt_neto, comision, activo, precio_entrada, None, nota,
        ])
    except Exception as e:
        print(f"  [LIBRO] ⚠️ No se pudo anotar la orden {moneda} {side}: {e}")

def anotar_contabilidad(moneda, motivo, precio_entrada, precio_salida,
                        resultado_usd, fase=None, nota=None):
    """
    Segunda anotacion, la que trae el MOTIVO: la escribe la contabilidad
    (registrar_tp / registrar_sl), que corre despues de la orden. Fila aparte,
    nunca reescribe la anterior: el libro es append-only.
    """
    try:
        _escribir([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "", "", "CONTABILIDAD",
            None, None, moneda + "USDT", moneda, "", "", fase, motivo,
            precio_salida, None, None, None, None, None, "", precio_entrada,
            resultado_usd, nota,
        ])
    except Exception as e:
        print(f"  [LIBRO] ⚠️ No se pudo anotar la contabilidad {moneda} {motivo}: {e}")
