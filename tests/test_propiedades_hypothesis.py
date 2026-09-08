"""L10 — property-based sobre el camino del dinero.

Los tests de L6 verifican CASOS: "0.29 no se come un tick", "5.994e-05 no sale
en notacion cientifica". Estos verifican PROPIEDADES que tienen que valer para
CUALQUIER entrada, y hypothesis busca activamente el contraejemplo.

La diferencia importa: un caso cubre lo que ya sabemos que salio mal. Una
propiedad cubre lo que todavia no sabemos.
"""
import sys

from hypothesis import assume, given, settings
from hypothesis import strategies as st

sys.path.insert(0, "/home/ariel/bot-padre-v2")
import ejecutor  # noqa: E402

SIMBOLOS = st.sampled_from(sorted(ejecutor.LOT_SIZE))
# cantidades realistas: desde polvo hasta posiciones grandes
CANTIDADES = st.floats(min_value=1e-9, max_value=1e6,
                       allow_nan=False, allow_infinity=False)


# ── _truncar_cantidad ────────────────────────────────────────────────────────

@given(SIMBOLOS, CANTIDADES)
def test_truncar_nunca_agranda(symbol, qty):
    """LA propiedad: pedir mas de lo que hay en cuenta es rechazo -2010 y la
    posicion queda ABIERTA sin stop. El resultado NUNCA puede superar la entrada."""
    assert ejecutor._truncar_cantidad(symbol, qty) <= qty


@given(SIMBOLOS, CANTIDADES)
def test_truncar_no_es_negativo(symbol, qty):
    assert ejecutor._truncar_cantidad(symbol, qty) >= 0


@given(SIMBOLOS, CANTIDADES)
def test_truncar_es_idempotente(symbol, qty):
    """Truncar algo ya truncado no lo cambia. Si fallara, dos pasadas por el
    mismo codigo darian cantidades distintas."""
    una = ejecutor._truncar_cantidad(symbol, qty)
    assert ejecutor._truncar_cantidad(symbol, una) == una


@given(SIMBOLOS, CANTIDADES)
def test_truncar_pierde_menos_de_un_tick(symbol, qty):
    """Lo que se descarta al truncar es siempre menor a un tick del LOT_SIZE.
    Si perdiera mas, estaria tirando cantidad vendible."""
    tick = 10 ** -ejecutor.LOT_SIZE[symbol]
    assert qty - ejecutor._truncar_cantidad(symbol, qty) < tick * 1.000001


@given(SIMBOLOS, CANTIDADES, CANTIDADES)
def test_truncar_respeta_el_orden(symbol, a, b):
    """Si a <= b, truncar(a) <= truncar(b). Una funcion de redondeo que
    invirtiera el orden seria un bug silencioso en cualquier comparacion."""
    assume(a <= b)
    assert ejecutor._truncar_cantidad(symbol, a) <= ejecutor._truncar_cantidad(symbol, b)


# ── _formatear_qty ───────────────────────────────────────────────────────────

@given(SIMBOLOS, CANTIDADES)
def test_formatear_nunca_usa_notacion_cientifica(symbol, qty):
    """El bug -1100 de Binance: str(5.994e-05) == '5.994e-05' y su regex para
    'quantity' no acepta la 'e'."""
    assert "e" not in ejecutor._formatear_qty(symbol, qty).lower()


@given(SIMBOLOS, CANTIDADES)
def test_formatear_y_truncar_dan_el_mismo_numero(symbol, qty):
    """Si divergieran, se mandaria a Binance una cantidad distinta de la que
    el bot cree que mando."""
    assert float(ejecutor._formatear_qty(symbol, qty)) == \
           ejecutor._truncar_cantidad(symbol, qty)


@given(SIMBOLOS, CANTIDADES)
def test_formatear_siempre_es_parseable(symbol, qty):
    float(ejecutor._formatear_qty(symbol, qty))


# ── _extraer_fill ────────────────────────────────────────────────────────────

MONTOS = st.floats(min_value=1e-6, max_value=1e6,
                   allow_nan=False, allow_infinity=False)
COMISIONES = st.floats(min_value=0.0, max_value=1e3,
                       allow_nan=False, allow_infinity=False)


@given(MONTOS, MONTOS, COMISIONES)
@settings(max_examples=200)
def test_extraer_fill_nunca_devuelve_mas_de_lo_ejecutado(qty, usdt, com):
    """La comision SIEMPRE resta. Si devolviera mas cantidad de la ejecutada,
    se persistiria cripto que no existe y el cierre fallaria."""
    assume(com <= qty)
    r = {"executedQty": str(qty), "cummulativeQuoteQty": str(usdt),
         "fills": [{"commission": str(com), "commissionAsset": "XXX"}]}
    qty_neta, usdt_neto, _ = ejecutor._extraer_fill(r, "XXX", 0, 0, 0)
    assert qty_neta <= qty + 1e-8
    assert usdt_neto <= usdt + 1e-8


@given(MONTOS, MONTOS)
def test_extraer_fill_sin_comision_no_cambia_nada(qty, usdt):
    r = {"executedQty": str(qty), "cummulativeQuoteQty": str(usdt), "fills": []}
    qty_neta, usdt_neto, _ = ejecutor._extraer_fill(r, "XXX", 0, 0, 0)
    assert abs(qty_neta - qty) < 1e-7
    assert abs(usdt_neto - usdt) < 1e-7


@given(MONTOS, MONTOS, COMISIONES)
def test_extraer_fill_comision_en_otro_activo_no_descuenta(qty, usdt, com):
    """Si la comision se pago en BNB, no puede restarse de la cripto operada
    ni del USDT recibido."""
    r = {"executedQty": str(qty), "cummulativeQuoteQty": str(usdt),
         "fills": [{"commission": str(com), "commissionAsset": "OTRA"}]}
    qty_neta, usdt_neto, _ = ejecutor._extraer_fill(r, "XXX", 0, 0, 0)
    assert abs(qty_neta - qty) < 1e-7
    assert abs(usdt_neto - usdt) < 1e-7


# ── el invariante que une las tres ───────────────────────────────────────────

@given(SIMBOLOS, MONTOS, MONTOS, COMISIONES)
@settings(max_examples=300)
def test_lo_que_se_manda_a_binance_nunca_supera_lo_que_hay(symbol, qty, usdt, com):
    """El invariante del camino del dinero, de punta a punta: lo que se
    persiste y despues se manda como 'quantity' nunca puede ser mayor que la
    cantidad neta realmente recibida."""
    assume(com <= qty)
    r = {"executedQty": str(qty), "cummulativeQuoteQty": str(usdt),
         "fills": [{"commission": str(com), "commissionAsset": "XXX"}]}
    qty_neta, _, _ = ejecutor._extraer_fill(r, "XXX", 0, 0, 0)
    assume(qty_neta > 0)
    enviado = float(ejecutor._formatear_qty(symbol, qty_neta))
    assert enviado <= qty_neta
