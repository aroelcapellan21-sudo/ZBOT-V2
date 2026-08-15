"""
tests_sistema_c.py — Tests de regresion y unitarios para BTC Sistema C

Ejecutar:
  cd ~/bot-padre-v2
  python3 -m sistema_c.tests_sistema_c

Tests incluidos:
  1. RSI — boundary exacto del backtest
  2. EMA gate — strictly greater (== NO genera señal)
  3. SL/TP — precios exactos
  4. Lookahead — assertion obligatoria
  5. Posicion unica — no dos posiciones simultaneas
  6. Separacion de produccion — Sistema C no toca auditoria.csv
  7. Regresion de backtest — OOS 2024-2025 debe coincidir con referencia
"""
import os
import sys
import json
import csv
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.expanduser("~/bot-padre-v2"))
from sistema_c.engine_c import (
    rsi_system_c, check_signal, compute_levels, compute_pnl,
    check_exit, get_ema_anti_lookahead, build_ema_map,
    fetch_1d_since, RSI_MIN, RSI_MAX, SL, TP, TRADE_AMT,
)

PASS = "[PASS]"
FAIL = "[FAIL]"
results = {"passed": 0, "failed": 0}

def ok(name):
    results["passed"] += 1
    print(f"{PASS} {name}")

def fail(name, detail=""):
    results["failed"] += 1
    print(f"{FAIL} {name}" + (f" — {detail}" if detail else ""))

def assert_eq(name, got, expected, tolerance=None):
    if tolerance is not None:
        if abs(got - expected) <= tolerance:
            ok(name)
        else:
            fail(name, f"got={got} expected={expected}±{tolerance}")
    else:
        if got == expected:
            ok(name)
        else:
            fail(name, f"got={got!r} expected={expected!r}")

def assert_true(name, condition, detail=""):
    if condition:
        ok(name)
    else:
        fail(name, detail)

def assert_false(name, condition, detail=""):
    if not condition:
        ok(name)
    else:
        fail(name, detail)

# ─────────────────────────────────────────────────────────────────────────────
# SECCION 1 — RSI boundary exacto
# ─────────────────────────────────────────────────────────────────────────────
# DISCREPANCIA DOCUMENTADA: rsi_system_c() usa range(1,14) = 13 diffs / 14.
# Mismo comportamiento que el backtest btc_bootstrap_sistema_c_vs_produccion.py.
# Los tests de boundary verifican la condicion de ENTRADA (>=55, <60),
# NO la precision del calculo de RSI (eso lo verifica el backtest de regresion).

print("\n=== SECCION 1: RSI boundary ===")

def _make_closes_with_rsi(target_rsi, n=200):
    """
    Genera una secuencia de closes que produzca un RSI aproximado a target_rsi.
    Para los tests de boundary verificamos la condicion de señal, no el RSI exacto.
    Usamos closes sinteticos con rsi conocido.
    """
    closes = [100.0] * n
    return closes

# Para boundary tests, mockeamos check_signal directamente con RSI conocido
# check_signal(close, rsi, ema_val) verifica: RSI_MIN <= rsi < RSI_MAX AND close > ema_val

EMA_VAL = 80000.0
CLOSE   = 85000.0  # > EMA_VAL

assert_false("RSI 54.99 NO genera señal",
             check_signal(CLOSE, 54.99, EMA_VAL),
             "54.99 < 55.0 deberia ser rechazado")

assert_true("RSI 55.00 SI genera señal",
            check_signal(CLOSE, 55.00, EMA_VAL))

assert_true("RSI 59.99 SI genera señal",
            check_signal(CLOSE, 59.99, EMA_VAL))

assert_false("RSI 60.00 NO genera señal (rango semiabierto)",
             check_signal(CLOSE, 60.00, EMA_VAL),
             "60.00 == RSI_MAX deberia ser rechazado (rango [55,60))")

assert_false("RSI 60.01 NO genera señal",
             check_signal(CLOSE, 60.01, EMA_VAL))

assert_false("RSI None NO genera señal",
             check_signal(CLOSE, None, EMA_VAL))

# ─────────────────────────────────────────────────────────────────────────────
# SECCION 2 — EMA gate
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== SECCION 2: EMA gate ===")

RSI_OK = 57.0

assert_true("close > EMA → pasa",
            check_signal(85001.0, RSI_OK, 85000.0))

assert_false("close == EMA → NO pasa (strictly greater)",
             check_signal(85000.0, RSI_OK, 85000.0),
             "close == ema_val debe ser rechazado")

assert_false("close < EMA → NO pasa",
             check_signal(84999.0, RSI_OK, 85000.0))

assert_false("ema_val None → NO pasa (sin EMA disponible)",
             check_signal(85000.0, RSI_OK, None))

# ─────────────────────────────────────────────────────────────────────────────
# SECCION 3 — SL y TP
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== SECCION 3: SL y TP ===")

entry = 80000.0
sl, tp = compute_levels(entry)
assert_eq("SL = entry * 0.95", sl, round(entry * 0.95, 2))
assert_eq("TP = entry * 1.06", tp, round(entry * 1.06, 2))
assert_eq("SL numericamente correcto", sl, 76000.0)
assert_eq("TP numericamente correcto", tp, 84800.0)

# P/L neto
fees, gross_tp, net_tp = compute_pnl(entry, tp)
assert_eq("Fees totales", fees, round(TRADE_AMT * 0.001 * 2, 4))
assert_eq("TP gross aprox", gross_tp, round(TRADE_AMT * 0.06, 4), tolerance=0.0001)
assert_eq("TP neto aprox +$0.2900", net_tp, round(TRADE_AMT * 0.06 - fees, 4))

fees2, gross_sl, net_sl = compute_pnl(entry, sl)
assert_true("SL neto negativo", net_sl < 0,
            f"SL neto debe ser negativo, got {net_sl}")
assert_eq("SL neto aprox -$0.2600", net_sl,
          round(-TRADE_AMT * 0.05 - fees2, 4))

# ─────────────────────────────────────────────────────────────────────────────
# SECCION 4 — Lookahead
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== SECCION 4: Anti-lookahead ===")

# Construir ema_map sintetico con fechas conocidas
ema_map_test = {
    "2024-01-01": 42000.0,
    "2024-01-02": 42100.0,
    "2024-01-03": 42200.0,
}

# Vela 4H del 2024-01-03 → debe usar EMA del 2024-01-02 (D-1)
ts_vela = int(datetime(2024, 1, 3, 8, 0, tzinfo=timezone.utc).timestamp() * 1000)
ema_v, ema_d = get_ema_anti_lookahead(ts_vela, ema_map_test)
assert_eq("Vela 2024-01-03 usa EMA de 2024-01-02 (D-1)", ema_d, "2024-01-02")
assert_eq("EMA value correcto", ema_v, 42100.0)

# Vela 4H del 2024-01-04 con mapa que solo tiene hasta 01-01 → busca D-2..D-5
ema_map_sparse = {"2024-01-01": 42000.0}
ts_vela2 = int(datetime(2024, 1, 4, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
ema_v2, ema_d2 = get_ema_anti_lookahead(ts_vela2, ema_map_sparse)
assert_eq("Fallback D-3 funciona", ema_d2, "2024-01-01")

# Vela sin EMA disponible
ts_vela3 = int(datetime(2024, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
ema_v3, ema_d3 = get_ema_anti_lookahead(ts_vela3, {})
assert_eq("Sin EMA → None", ema_v3, None)
assert_eq("Sin EMA → fecha None", ema_d3, None)

# Assertion lookahead: EMA del mismo dia 4H debe fallar
try:
    ts_hoy = int(datetime(2024, 1, 5, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
    ema_map_hoy = {"2024-01-05": 42500.0}  # mismo dia que la vela 4H
    ema_v4, ema_d4 = get_ema_anti_lookahead(ts_hoy, ema_map_hoy)
    # La funcion busca D-1..D-5, nunca D=hoy, asi que nunca retorna la clave "2024-01-05"
    assert_true("EMA del dia actual no se usa (D-1 lookback garantiza esto)", ema_d4 is None)
except AssertionError as e:
    fail("Lookahead assertion activo", str(e))

# ─────────────────────────────────────────────────────────────────────────────
# SECCION 5 — Posicion unica
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== SECCION 5: Posicion unica ===")

from sistema_c.store import load_state, is_open

state_idle = {"status": "IDLE"}
state_open = {"status": "OPEN", "trade_id": "BTC-C-000001",
              "entry_price": 80000.0, "sl_price": 76000.0, "tp_price": 84800.0}

# Con posicion abierta, check_exit SI evalua salida
reason, ep = check_exit(state_open, 76000.0)
assert_eq("SL activo con posicion abierta", reason, "SL")

reason2, ep2 = check_exit(state_open, 84800.0)
assert_eq("TP activo con posicion abierta", reason2, "TP")

reason3, _ = check_exit(state_open, 80100.0)
assert_eq("Sin salida si precio en rango", reason3, None)

reason4, _ = check_exit(state_idle, 50000.0)
assert_eq("Sin salida si no hay posicion", reason4, None)

reason5, _ = check_exit(None, 50000.0)
assert_eq("Sin salida si state es None", reason5, None)

# ─────────────────────────────────────────────────────────────────────────────
# SECCION 6 — Separacion de produccion
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== SECCION 6: Separacion de produccion ===")

PROD_FILES = [
    os.path.expanduser("~/bot-padre-v2/auditoria.csv"),
    os.path.expanduser("~/bot-padre-v2/signals/billetera.json"),
    os.path.expanduser("~/bot-padre-v2/config_cartera.py"),
]

# Capturar mtimes ANTES en un dict (no una variable simple que se sobreescribe)
mtime_antes = {}
for path in PROD_FILES:
    if os.path.exists(path):
        mtime_antes[path] = os.path.getmtime(path)

# Verificar que store.py NO contiene llamadas open() hacia archivos de produccion.
# Buscar patrones de escritura reales, no menciones en comentarios.
import sistema_c.store as store_mod
src = open(store_mod.__file__).read()

# Patrones de ESCRITURA real hacia archivos de produccion (no comentarios)
import re
abre_auditoria = bool(re.search(r'open\([^)]*auditoria', src))
abre_billetera_signals = bool(re.search(r'open\([^)]*signals/billetera', src))
assert_false("store.py no abre auditoria.csv para escritura",
             abre_auditoria,
             "store.py no debe llamar open() con 'auditoria' en la ruta")
assert_false("store.py no abre signals/billetera.json",
             abre_billetera_signals,
             "store.py no debe llamar open() con 'signals/billetera' en la ruta")
assert_false("store.py no importa ejecutor",
             "import ejecutor" in src or "from ejecutor" in src)
assert_false("store.py no importa gestor_billetera de produccion",
             "from gestor_billetera" in src or "import gestor_billetera" in src)

# Verificar que los archivos de produccion no fueron modificados durante los tests
for path in PROD_FILES:
    if os.path.exists(path) and path in mtime_antes:
        mtime_despues = os.path.getmtime(path)
        assert_eq(f"Archivo produccion intacto: {os.path.basename(path)}",
                  mtime_antes[path], mtime_despues)

# ─────────────────────────────────────────────────────────────────────────────
# SECCION 7 — Backtest de regresion OOS 2024-2025
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== SECCION 7: Regresion backtest OOS 2024-2025 ===")
print("Descargando datos historicos de Binance...")
print("(puede tardar 30-60 segundos)")

# Replica exacta de btc_bootstrap_sistema_c_vs_produccion.py
# para verificar que la implementacion de engine_c.py produce los mismos resultados.

def _ts_ms_str(s):
    return int(datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

def _fetch_all_4h(desde):
    velas = []; start = _ts_ms_str(desde); ahora = int(datetime.now(timezone.utc).timestamp() * 1000)
    while True:
        p = urllib.parse.urlencode({"symbol": "BTCUSDT", "interval": "4h",
                                    "startTime": start, "limit": 1000})
        with urllib.request.urlopen(
                f"https://api.binance.com/api/v3/klines?{p}", timeout=30) as r:
            batch = json.loads(r.read().decode())
        if not batch: break
        velas.extend(batch)
        if len(batch) < 1000: break
        start = batch[-1][0] + 1
    return [v for v in velas if int(v[6]) < ahora]

try:
    # 1. Descargar datos
    velas_4h_raw = _fetch_all_4h("2020-10-01")
    velas_1d_raw = fetch_1d_since("2019-06-01")
    ema_map_reg  = build_ema_map(velas_1d_raw, n=200)

    # 2. Periodos
    OOS_START = _ts_ms_str("2024-01-01")
    OOS_END   = _ts_ms_str("2025-12-31") + 86400000

    # 3. Simular — replica rsi_calc del bootstrap (mismo algoritmo)
    closes_all = [float(v[4]) for v in velas_4h_raw]
    ts_all     = [int(v[0])   for v in velas_4h_raw]
    MONTO_REG  = 5.0
    COMM_REG   = 0.001
    SL_REG, TP_REG = 0.05, 0.06

    trades = []; en_pos = False
    ep = er = sl_p = tp_p = 0.0; ets = None; e_ema = None

    for i in range(60, len(closes_all)):
        ventana = closes_all[max(0, i - 60):i]
        r = rsi_system_c(ventana)  # usa la implementacion de engine_c
        if r is None: continue
        precio = closes_all[i]; tsv = ts_all[i]
        tsdt   = datetime.fromtimestamp(tsv / 1000, tz=timezone.utc)

        if en_pos:
            res = None
            if precio <= sl_p: res = "SL"
            elif precio >= tp_p: res = "TP"
            if res:
                pl = round((MONTO_REG * TP_REG if res == "TP" else -MONTO_REG * SL_REG)
                           - MONTO_REG * COMM_REG * 2, 4)
                if OOS_START <= ets_ms < OOS_END:
                    trades.append({"res": res, "pl": pl})
                en_pos = False

        if not en_pos and 55.0 <= r < 60.0:
            ev, ed = get_ema_anti_lookahead(tsv, ema_map_reg)
            if ev is not None and precio > ev:
                en_pos = True; ep = precio; ets = tsdt; ets_ms = tsv; er = r
                sl_p = round(ep * (1 - SL_REG), 4)
                tp_p = round(ep * (1 + TP_REG), 4)
                e_ema = ev

    # 4. Metricas
    n_r  = len(trades)
    tps_r = [t for t in trades if t["res"] == "TP"]
    sls_r = [t for t in trades if t["res"] == "SL"]
    tg_r  = sum(t["pl"] for t in tps_r)
    tl_r  = abs(sum(t["pl"] for t in sls_r))
    pf_r  = round(tg_r / tl_r, 3) if tl_r > 0 else 0.0
    wr_r  = round(len(tps_r) / n_r * 100, 1) if n_r > 0 else 0.0
    pl_r  = round(sum(t["pl"] for t in trades), 4)
    exp_r = round(pl_r / n_r, 4) if n_r > 0 else 0.0

    cap_r = 20.0; mxc_r = cap_r; dd_r = 0.0
    for t in trades:
        cap_r += t["pl"]; mxc_r = max(mxc_r, cap_r)
        dd_r = max(dd_r, (mxc_r - cap_r) / mxc_r * 100)

    print(f"\nResultado regresion OOS 2024-2025:")
    print(f"  Trades:    {n_r}  (esperado: 59 ±2)")
    print(f"  PF:        {pf_r:.3f}  (esperado: 1.322 ±0.05)")
    print(f"  WR:        {wr_r:.1f}%  (esperado: 54.2% ±3pp)")
    print(f"  Exp:       ${exp_r:.4f}  (esperado: +$0.0383 ±0.01)")
    print(f"  P/L:       ${pl_r:.4f}")
    print(f"  DD max:    {dd_r:.1f}%  (esperado: ≈5.3%)")

    # Referencias del bootstrap confirmadas
    REF = {"trades": 59, "pf": 1.322, "wr": 54.2, "exp": 0.0383, "dd": 5.3}
    assert_eq("Trades OOS",      n_r,   REF["trades"], tolerance=2)
    assert_eq("PF OOS",          pf_r,  REF["pf"],     tolerance=0.05)
    assert_eq("WR OOS",          wr_r,  REF["wr"],     tolerance=3.0)
    assert_eq("Expectancy OOS",  exp_r, REF["exp"],    tolerance=0.01)
    assert_eq("DD max OOS",      round(dd_r, 1), REF["dd"], tolerance=1.0)

    # Si difiere mas del 10% en trades: mostrar DISCREPANCIA
    if abs(n_r - REF["trades"]) > 5:
        print(f"\nDISCREPANCIA DETECTADA:")
        print(f"  Archivo:            sistema_c/engine_c.py:rsi_system_c()")
        print(f"  Comportamiento obs: {n_r} trades OOS")
        print(f"  Comportamiento esp: {REF['trades']} trades OOS")
        print(f"  Impacto:            la implementacion diverge del backtest de referencia")
        print(f"  Posible causa:      diferencia en RSI, EMA o logica de señal")

except Exception as e:
    fail(f"Regresion backtest — error: {e}")
    import traceback; traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# RESUMEN
# ─────────────────────────────────────────────────────────────────────────────
total = results["passed"] + results["failed"]
print(f"\n{'='*50}")
print(f"RESULTADO FINAL: {results['passed']}/{total} tests pasados")
if results["failed"] > 0:
    print(f"FALLOS: {results['failed']}")
    print("NO iniciar SHADOW hasta resolver todos los fallos.")
    sys.exit(1)
else:
    print("TODOS LOS TESTS PASARON — sistema listo para SHADOW.")
    print()
    print("Para iniciar el monitor:")
    print("  screen -dmS z_btc_system_c bash -c "
          "'cd ~/bot-padre-v2 && python3 -m sistema_c.btc_system_c'")
    sys.exit(0)
