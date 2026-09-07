"""L6 — invariantes de auditoria.csv, el archivo del que el bot decide.

No es un archivo de log: es el ESTADO. `contar_operaciones_abiertas()` lo lee
para saber si puede abrir, y `revisar_cierres()` para saber que cerrar. Si su
forma se rompe, el bot opera mal en silencio.

Las reglas que se verifican salen de CLAUDE.md ("Camino de dinero — reglas de
oro") y de incidentes reales:

  · 8 columnas: timestamp,accion,symbol,precio,rsi,estado,monto,qty
  · los modulos indexan 0..6 con `len(partes) >= N`, asi que agregar columnas
    AL FINAL es seguro y en el MEDIO rompe todo
  · los estados son un conjunto cerrado; uno desconocido significa que algo
    escribio mal
  · una fila ABIERTA sin qty no se puede cerrar con la cantidad real

Estos tests corren sobre el auditoria.csv REAL de produccion: si fallan, hay un
problema de datos ahora mismo, no un problema de codigo.
"""
import csv
import os
from datetime import datetime

import pytest

AUDITORIA = "/home/ariel/bot-padre-v2/auditoria.csv"
CABECERA = ["timestamp", "accion", "symbol", "precio", "rsi", "estado", "monto", "qty"]
ESTADOS = {"ABIERTA", "RESERVADA", "ANULADA", "TP", "SL", "TRAILING_SL", "BE",
           "FASE_CAMBIO", "MANUAL_WIN", "MANUAL_LOSS"}
ACCIONES = {"ALCISTA", "BAJISTA", "LATERAL"}


@pytest.fixture(scope="module")
def filas():
    if not os.path.exists(AUDITORIA):
        pytest.skip("no hay auditoria.csv (entorno sin produccion)")
    with open(AUDITORIA) as f:
        return [r for r in csv.reader(f) if r]


def test_cabecera_exacta(filas):
    """Si cambia el orden o el nombre, todos los modulos que indexan por
    posicion leen la columna equivocada."""
    assert filas[0] == CABECERA


def test_todas_las_filas_tienen_al_menos_7_columnas(filas):
    """Los modulos hacen `len(partes) >= 7` antes de indexar 0..6."""
    malas = [(i, r) for i, r in enumerate(filas[1:], 2) if len(r) < 7]
    assert not malas, f"filas con menos de 7 columnas: {malas[:3]}"


def test_ninguna_fila_tiene_mas_columnas_que_la_cabecera(filas):
    """Agregar columnas al final es seguro, pero la cabecera tiene que
    declararlas: si no, nadie sabe que significan."""
    malas = [i for i, r in enumerate(filas[1:], 2) if len(r) > len(CABECERA)]
    assert not malas, f"filas con columnas de mas: {malas[:3]}"


def test_estados_conocidos(filas):
    vistos = {r[5] for r in filas[1:] if len(r) > 5}
    assert vistos <= ESTADOS, f"estados desconocidos: {vistos - ESTADOS}"


def test_acciones_conocidas(filas):
    vistas = {r[1] for r in filas[1:] if len(r) > 1}
    assert vistas <= ACCIONES, f"acciones desconocidas: {vistas - ACCIONES}"


def test_timestamps_parseables_y_ordenados(filas):
    ts = []
    for i, r in enumerate(filas[1:], 2):
        try:
            ts.append(datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            pytest.fail(f"timestamp ilegible en la fila {i}: {r[0]!r}")
    desordenadas = [i for i in range(1, len(ts)) if ts[i] < ts[i-1]]
    assert not desordenadas, f"filas fuera de orden: {desordenadas[:3]}"


def test_precio_y_monto_son_numeros_positivos(filas):
    for i, r in enumerate(filas[1:], 2):
        if len(r) < 7:
            continue
        assert float(r[3]) > 0, f"precio no positivo en la fila {i}"
        assert float(r[6]) > 0, f"monto no positivo en la fila {i}"


def test_las_filas_abiertas_tienen_qty(filas):
    """Sin qty no se puede cerrar con la cantidad real: se cae a un calculo
    teorico que no coincide con lo que hay en la cuenta."""
    sin_qty = [i for i, r in enumerate(filas[1:], 2)
               if len(r) > 5 and r[5] == "ABIERTA" and (len(r) < 8 or not r[7])]
    assert not sin_qty, f"filas ABIERTA sin qty: {sin_qty}"


def test_las_anuladas_no_tienen_qty(filas):
    """ANULADA significa que la orden no se ejecuto: no puede haber cantidad."""
    con_qty = [i for i, r in enumerate(filas[1:], 2)
               if len(r) > 7 and r[5] == "ANULADA" and r[7]]
    assert not con_qty, f"filas ANULADA con qty: {con_qty[:3]}"


def test_no_hay_duplicados_de_symbol_y_timestamp(filas):
    """Dos filas con la misma moneda y el mismo instante serian la misma
    operacion contada dos veces."""
    claves = [(r[2], r[0]) for r in filas[1:] if len(r) > 2]
    assert len(claves) == len(set(claves)), "hay symbol+timestamp duplicados"
