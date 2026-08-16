# =========================================
# centinela/estado/estado_global.py
# Variables compartidas thread-safe
# entre todos los modulos del Centinela
# High Water Mark para drawdown real
# BUG CORREGIDO: Lee capital real desde billetera.json
# Constitucion RESPETADA
# =========================================
import threading
import json
import os
from datetime import datetime

def _leer_capital_real():
    try:
        ruta = os.path.expanduser("~/bot-padre-v2/signals/billetera.json")
        with open(ruta, "r") as f:
            data = json.load(f)
        capital = float(data.get("capital_disponible", data.get("USDT", 1000.0)))
        print("[CENTINELA] Capital real leido desde billetera.json: $" + str(capital))
        return capital
    except:
        print("[CENTINELA] billetera.json no encontrada. Usando $1000.0 por defecto.")
        return 1000.0

_capital_inicial = _leer_capital_real()
_lock = threading.Lock()

_estado = {
    # --- CAPITAL ---
    "capital_actual": _capital_inicial,
    "capital_maximo_dia": _capital_inicial,      # High Water Mark diario
    "capital_maximo_semana": _capital_inicial,   # High Water Mark semanal
    "capital_inicio_dia": _capital_inicial,
    "capital_inicio_semana": _capital_inicial,
    # --- DRAWDOWN ---
    "drawdown_diario": 0.0,
    "drawdown_semanal": 0.0,
    "drawdown_por_activo": {},
    # --- OPERACIONES ---
    "operaciones_abiertas": 0,
    "operaciones_por_activo": {},
    # --- CONECTIVIDAD ---
    "fallos_conectividad": 0,
    "ultimo_ping": None,
    "exchange_online": True,
    # --- ALERTAS ---
    "nivel_alerta": "verde",
    "motivo_alerta": "",
    "sistema_pausado": False,
    "modo_panico": False,
    "timestamp_panico": None,
    # --- CONFIRMACION ---
    "contadores_confirmacion": {},
    # --- FECHA ---
    "fecha_inicio_dia": datetime.now().strftime("%Y-%m-%d"),
    "fecha_inicio_semana": datetime.now().strftime("%Y-%W"),
}

def get(clave):
    with _lock:
        return _estado.get(clave)

def set(clave, valor):
    with _lock:
        _estado[clave] = valor

def actualizar_capital(nuevo_capital):
    with _lock:
        _estado["capital_actual"] = nuevo_capital
        # Actualizar High Water Mark diario
        if nuevo_capital > _estado["capital_maximo_dia"]:
            _estado["capital_maximo_dia"] = nuevo_capital
        # Actualizar High Water Mark semanal
        if nuevo_capital > _estado["capital_maximo_semana"]:
            _estado["capital_maximo_semana"] = nuevo_capital
        # Calcular drawdown real sobre maximo alcanzado
        if _estado["capital_maximo_dia"] > 0:
            _estado["drawdown_diario"] = round(
                ((_estado["capital_maximo_dia"] - nuevo_capital) /
                 _estado["capital_maximo_dia"]) * 100, 4
            )
        if _estado["capital_maximo_semana"] > 0:
            _estado["drawdown_semanal"] = round(
                ((_estado["capital_maximo_semana"] - nuevo_capital) /
                 _estado["capital_maximo_semana"]) * 100, 4
            )

def resetear_dia():
    with _lock:
        _estado["capital_inicio_dia"] = _estado["capital_actual"]
        _estado["capital_maximo_dia"] = _estado["capital_actual"]
        _estado["drawdown_diario"] = 0.0
        _estado["fecha_inicio_dia"] = datetime.now().strftime("%Y-%m-%d")

def resetear_semana():
    with _lock:
        _estado["capital_inicio_semana"] = _estado["capital_actual"]
        _estado["capital_maximo_semana"] = _estado["capital_actual"]
        _estado["drawdown_semanal"] = 0.0
        _estado["fecha_inicio_semana"] = datetime.now().strftime("%Y-%W")

def get_resumen():
    with _lock:
        return {
            "capital_actual": _estado["capital_actual"],
            "capital_maximo_dia": _estado["capital_maximo_dia"],
            "drawdown_diario": _estado["drawdown_diario"],
            "drawdown_semanal": _estado["drawdown_semanal"],
            "operaciones_abiertas": _estado["operaciones_abiertas"],
            "nivel_alerta": _estado["nivel_alerta"],
            "sistema_pausado": _estado["sistema_pausado"],
            "modo_panico": _estado["modo_panico"],
            "exchange_online": _estado["exchange_online"],
        }
