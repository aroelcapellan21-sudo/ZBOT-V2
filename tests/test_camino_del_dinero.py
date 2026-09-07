"""L6 — tests de las funciones del camino del dinero.

Estas tres funciones deciden cuanta cripto se compra, cuanta se vende y cuanto
quedo en la cuenta. Cada una tiene detras un incidente real de produccion, y el
test existe para que ese incidente no vuelva:

  _truncar_cantidad  — si redondea hacia ARRIBA, se pide mas de lo que hay en
                       cuenta: rechazo -2010 de Binance, el cierre falla y la
                       posicion queda ABIERTA sin stop.
  _formatear_qty     — si devuelve notacion cientifica, Binance responde -1100
                       "Illegal characters found in parameter 'quantity'".
                       Pasa siempre con BTC: $5 a ~$80.000 da qty ~6.25e-05.
  _extraer_fill      — si no resta la comision, se persiste ~0.1% mas cripto de
                       la que realmente hay, y despues no se puede vender.

No tocan red, ni claves, ni archivos: solo aritmetica.
"""
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, "/home/ariel/bot-padre-v2")
import ejecutor  # noqa: E402


# ── _truncar_cantidad ────────────────────────────────────────────────────────

def test_truncar_nunca_redondea_hacia_arriba():
    """Lo esencial: el resultado NUNCA puede ser mayor que la entrada."""
    for symbol, dec in ejecutor.LOT_SIZE.items():
        for qty in (0.123456789, 1.999999999, 0.000019999, 123.456789):
            assert ejecutor._truncar_cantidad(symbol, qty) <= qty

def test_truncar_respeta_el_lot_size_de_cada_simbolo():
    assert ejecutor._truncar_cantidad("BTCUSDT", 0.123456789) == 0.12345   # 5 dec
    assert ejecutor._truncar_cantidad("ETHUSDT", 0.123456789) == 0.1234    # 4
    assert ejecutor._truncar_cantidad("SOLUSDT", 0.123456789) == 0.123     # 3
    assert ejecutor._truncar_cantidad("AVAXUSDT", 0.123456789) == 0.12     # 2

def test_truncar_no_se_come_un_tick_por_error_binario():
    """El caso que motivo usar Decimal: floor() sobre float daba 0.28.

    0.29 * 100 = 28.999999999999996 en coma flotante binaria.
    """
    assert ejecutor._truncar_cantidad("AVAXUSDT", 0.29) == 0.29
    assert ejecutor._truncar_cantidad("SOLUSDT", 0.291) == 0.291

def test_truncar_simbolo_desconocido_usa_6_decimales():
    assert ejecutor._truncar_cantidad("NOEXISTE", 0.1234567891) == 0.123456

def test_truncar_cantidad_menor_al_tick_da_cero():
    """Si la cantidad no llega ni a un tick, el resultado es 0 — y quien llame
    tiene que tratarlo, porque una orden de 0 no se puede mandar."""
    assert ejecutor._truncar_cantidad("AVAXUSDT", 0.009) == 0.0


# ── _formatear_qty ───────────────────────────────────────────────────────────

def test_formatear_nunca_devuelve_notacion_cientifica():
    """El bug -1100: str(5.994e-05) == '5.994e-05' y Binance lo rechaza."""
    for symbol in ejecutor.LOT_SIZE:
        for qty in (5.994e-05, 6.25e-05, 1e-05, 0.0000123):
            s = ejecutor._formatear_qty(symbol, qty)
            assert "e" not in s.lower(), f"{symbol} {qty} -> {s}"

def test_formatear_el_caso_real_de_btc():
    """$5 de BTC a ~$80.000 da ~6.25e-05, por debajo de 1e-4."""
    assert ejecutor._formatear_qty("BTCUSDT", 5 / 80000) == "0.00006"

def test_formatear_coincide_con_truncar():
    """Formatear y truncar tienen que dar el mismo numero."""
    for symbol in ejecutor.LOT_SIZE:
        for qty in (0.123456789, 5.994e-05, 1.5):
            assert float(ejecutor._formatear_qty(symbol, qty)) == \
                   ejecutor._truncar_cantidad(symbol, qty)


# ── _extraer_fill ────────────────────────────────────────────────────────────

def test_extraer_fill_resta_la_comision_en_compra():
    """En COMPRA la comision se cobra en el activo BASE: se recibe menos cripto."""
    r = {"executedQty": "1.0", "cummulativeQuoteQty": "100.0",
         "fills": [{"commission": "0.001", "commissionAsset": "BTC"}]}
    qty, usdt, precio = ejecutor._extraer_fill(r, "BTC", 0, 0, 0)
    assert qty == 0.999
    assert usdt == 100.0
    assert precio == 100.0

def test_extraer_fill_resta_la_comision_en_venta():
    """En VENTA se cobra en USDT: se recibe menos USDT."""
    r = {"executedQty": "1.0", "cummulativeQuoteQty": "100.0",
         "fills": [{"commission": "0.1", "commissionAsset": "USDT"}]}
    qty, usdt, _ = ejecutor._extraer_fill(r, "BTC", 0, 0, 0)
    assert qty == 1.0
    assert usdt == 99.9

def test_extraer_fill_suma_varios_fills():
    r = {"executedQty": "2.0", "cummulativeQuoteQty": "200.0",
         "fills": [{"commission": "0.001", "commissionAsset": "ETH"},
                   {"commission": "0.002", "commissionAsset": "ETH"}]}
    qty, _, _ = ejecutor._extraer_fill(r, "ETH", 0, 0, 0)
    assert qty == 1.997

def test_extraer_fill_sin_fills_usa_los_valores_brutos():
    """El SIMULADOR no devuelve 'fills': la comision es 0."""
    r = {"executedQty": "1.0", "cummulativeQuoteQty": "100.0"}
    qty, usdt, precio = ejecutor._extraer_fill(r, "BTC", 0, 0, 0)
    assert (qty, usdt, precio) == (1.0, 100.0, 100.0)

def test_extraer_fill_comision_ilegible_no_rompe():
    """Un fill con comision no numerica se saltea, no tira excepcion:
    perder la comision de un fill es mejor que perder la operacion entera."""
    r = {"executedQty": "1.0", "cummulativeQuoteQty": "100.0",
         "fills": [{"commission": "no-es-un-numero", "commissionAsset": "BTC"},
                   {"commission": "0.001", "commissionAsset": "BTC"}]}
    qty, _, _ = ejecutor._extraer_fill(r, "BTC", 0, 0, 0)
    assert qty == 0.999

def test_extraer_fill_qty_cero_usa_el_precio_de_respaldo():
    """Sin cantidad no se puede dividir: tiene que caer al fallback, no romper."""
    r = {"executedQty": "0", "cummulativeQuoteQty": "0"}
    qty, usdt, precio = ejecutor._extraer_fill(r, "BTC", 0, 0, 12345.0)
    assert precio == 12345.0

def test_extraer_fill_usa_fallback_si_falta_el_campo():
    r = {}
    qty, usdt, precio = ejecutor._extraer_fill(r, "BTC", 0.5, 50.0, 100.0)
    assert (qty, usdt) == (0.5, 50.0)

def test_extraer_fill_ignora_comision_en_otro_activo():
    """Si la comision se pago en BNB, no se descuenta ni de la cripto ni del USDT."""
    r = {"executedQty": "1.0", "cummulativeQuoteQty": "100.0",
         "fills": [{"commission": "0.01", "commissionAsset": "BNB"}]}
    qty, usdt, _ = ejecutor._extraer_fill(r, "BTC", 0, 0, 0)
    assert (qty, usdt) == (1.0, 100.0)


# ── invariante que une las tres ──────────────────────────────────────────────

@pytest.mark.parametrize("symbol", sorted(ejecutor.LOT_SIZE))
def test_lo_que_se_persiste_siempre_es_vendible(symbol):
    """El invariante que importa: la cantidad que se guarda, truncada al
    LOT_SIZE, nunca puede superar la que realmente se recibio."""
    r = {"executedQty": "1.23456789", "cummulativeQuoteQty": "100.0",
         "fills": [{"commission": "0.00123456", "commissionAsset": "XXX"}]}
    qty_neta, _, _ = ejecutor._extraer_fill(r, "XXX", 0, 0, 0)
    assert ejecutor._truncar_cantidad(symbol, qty_neta) <= qty_neta
