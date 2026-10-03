"""L6 — tests del libro de ordenes.

El libro es la unica fuente de verdad que guarda el order_id de Binance, la
comision realmente cobrada y el precio del fill. Su contrato tiene una sola
regla dura: NUNCA puede lanzar. Si lanzara, la excepcion subiria por
ejecutor.ejecutar_operacion / cerrar_posicion y podria frenar una orden o
dejarla a medio contabilizar — exactamente el tipo de fallo que el libro
existe para auditar.

Por eso cada caso de abajo es una respuesta deformada de Binance (vacia, None,
sin 'fills', simulada sin orderId) y lo que se verifica es que la anotacion no
levante nada y que la fila salga con el numero de columnas correcto.

No tocan red, ni claves, ni el libro real: LIBRO se redirige a tmp_path.
"""
import os
import sys
from datetime import datetime

import pytest

# La raiz sale de la ubicacion del propio test, NO de una ruta absoluta de la
# Dell: el CI corre en otro directorio (ver test_camino_del_dinero.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import libro_ordenes  # noqa: E402


RESPUESTA_COMPLETA = {
    "orderId": 123456789,
    "clientOrderId": "x-ZBOT-abc",
    "transactTime": 1759500000000,
    "status": "FILLED",
    "executedQty": "0.00300000",
    "cummulativeQuoteQty": "7.00500000",
    "fills": [
        {"commission": "0.00000300", "commissionAsset": "SOL"},
        {"commission": "0.00000100", "commissionAsset": "SOL"},
    ],
}

# La forma exacta que devuelve ejecutor._simular_fill: sin orderId, sin status.
RESPUESTA_SIMULADA = {
    "executedQty": "0.066",
    "cummulativeQuoteQty": "7.0",
    "price": "106.06",
    "fills": [{"commission": "0.000066", "commissionAsset": "SOL"}],
}

RESPUESTA_SIN_FILLS = {
    "orderId": 999,
    "status": "FILLED",
    "executedQty": "1.0",
    "cummulativeQuoteQty": "20.0",
}


@pytest.fixture
def libro(tmp_path, monkeypatch):
    """Redirige el libro a un archivo temporal. El real no se toca nunca."""
    destino = tmp_path / "libro_ordenes.csv"
    monkeypatch.setattr(libro_ordenes, "LIBRO", str(destino))
    return destino


def _filas(destino):
    """Devuelve (cabecera, filas) ya partidas por coma."""
    lineas = destino.read_text(encoding="utf-8").strip().split("\n")
    return lineas[0].split(","), [l.split(",") for l in lineas[1:]]


# ── la regla dura: nunca lanza ───────────────────────────────────────────────

@pytest.mark.parametrize("respuesta", [
    RESPUESTA_COMPLETA,
    RESPUESTA_SIMULADA,
    RESPUESTA_SIN_FILLS,
    {},
    None,
])
def test_anotar_orden_nunca_lanza(libro, respuesta):
    libro_ordenes.anotar_orden("APERTURA", "SOL", "BUY", respuesta, "SIMULADOR")


def test_anotar_contabilidad_nunca_lanza(libro):
    libro_ordenes.anotar_contabilidad("SOL", "TP", 100.0, 107.0, 0.35, fase="ALCISTA")
    libro_ordenes.anotar_contabilidad(None, None, None, None, None)


# ── las filas salen bien ─────────────────────────────────────────────────────

def test_cabecera_y_ancho_de_fila(libro):
    libro_ordenes.anotar_orden("APERTURA", "SOL", "BUY", RESPUESTA_COMPLETA, "REAL")
    cabecera, filas = _filas(libro)
    assert cabecera == libro_ordenes.COLUMNAS
    assert len(filas) == 1
    assert len(filas[0]) == len(libro_ordenes.COLUMNAS)


def test_la_cabecera_se_escribe_una_sola_vez(libro):
    for _ in range(3):
        libro_ordenes.anotar_orden("APERTURA", "SOL", "BUY", RESPUESTA_COMPLETA, "REAL")
    cabecera, filas = _filas(libro)
    assert len(filas) == 3
    assert all(f[0] != "ts_local" for f in filas)


def test_respuesta_completa_guarda_order_id_comision_y_precio(libro):
    libro_ordenes.anotar_orden("CIERRE", "SOL", "SELL", RESPUESTA_COMPLETA, "REAL",
                               qty_neta=0.003, usdt_neto=6.998, fase="ALCISTA",
                               precio_entrada=2000.0)
    cabecera, filas = _filas(libro)
    f = dict(zip(cabecera, filas[0]))
    assert f["order_id"] == "123456789"
    assert f["client_order_id"] == "x-ZBOT-abc"
    assert f["evento"] == "CIERRE"
    assert f["regimen"] == "REAL"
    assert f["symbol"] == "SOLUSDT" and f["side"] == "SELL"
    assert f["status"] == "FILLED"
    assert f["fase"] == "ALCISTA"
    assert f["motivo"] == "NO_DECLARADO"      # el motivo fino llega en el paso 2
    assert float(f["comision"]) == pytest.approx(0.000004)   # suma los dos fills
    assert f["comision_activo"] == "SOL"
    assert float(f["precio_fill"]) == pytest.approx(2335.0)  # 7.005 / 0.003
    # transactTime (ms) traducido a hora local legible, sin inventar el año:
    # se compara contra la misma conversion hecha aqui.
    esperado = datetime.fromtimestamp(
        RESPUESTA_COMPLETA["transactTime"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
    assert f["ts_binance"] == esperado


def test_simulada_sin_order_id_queda_marcada_como_simulador(libro):
    libro_ordenes.anotar_orden("APERTURA", "SOL", "BUY", RESPUESTA_SIMULADA, "SIMULADOR")
    cabecera, filas = _filas(libro)
    f = dict(zip(cabecera, filas[0]))
    assert f["order_id"] == ""
    assert f["status"] == ""
    assert f["regimen"] == "SIMULADOR"
    assert f["ts_binance"] == ""
    assert float(f["precio_fill"]) == pytest.approx(106.0606, abs=1e-3)


def test_sin_fills_la_comision_es_cero_y_no_inventa_activo(libro):
    libro_ordenes.anotar_orden("APERTURA", "BTC", "BUY", RESPUESTA_SIN_FILLS, "REAL")
    cabecera, filas = _filas(libro)
    f = dict(zip(cabecera, filas[0]))
    assert float(f["comision"]) == 0.0
    assert f["comision_activo"] == ""


def test_respuesta_vacia_deja_fila_con_campos_vacios(libro):
    libro_ordenes.anotar_orden("APERTURA", "ETH", "BUY", {}, "REAL")
    cabecera, filas = _filas(libro)
    f = dict(zip(cabecera, filas[0]))
    assert f["order_id"] == "" and f["qty_bruta"] == "" and f["precio_fill"] == ""
    assert f["moneda"] == "ETH"            # lo que si se sabe, se guarda
    assert f["ts_local"].startswith("20")


def test_respuesta_none_no_escribe_fila(libro):
    libro_ordenes.anotar_orden("APERTURA", "ETH", "BUY", None, "REAL")
    assert not os.path.exists(libro) or libro.read_text(encoding="utf-8") == ""


def test_una_coma_en_un_campo_no_parte_la_fila(libro):
    libro_ordenes.anotar_orden("APERTURA", "SOL", "BUY", RESPUESTA_COMPLETA, "REAL",
                               nota="qty ajustada de 1,5 a 1,4")
    cabecera, filas = _filas(libro)
    assert len(filas) == 1
    assert len(filas[0]) == len(libro_ordenes.COLUMNAS)
    assert ";" in dict(zip(cabecera, filas[0]))["nota"]
