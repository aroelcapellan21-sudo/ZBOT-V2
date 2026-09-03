"""
LINK Sistema C — Prueba #1
Metodología idéntica a BTC/BNB/ETH/SOL/AVAX/XRP Sistema C.

Baseline: RSI 50-70, SL 5%, TP 6%, sin gate EMA (LINK no está en producción; se usa
          el rango estándar de nueva moneda para comparación consistente)
Sistema C: RSI 55-60, SL 5%, TP 6%, gate EMA200d anti-lookahead

NO modifica ningún archivo de producción.
"""

import requests
import random
import math
from datetime import datetime, timezone, timedelta


# ─── Descarga ─────────────────────────────────────────────────────────────────

def descargar_klines(symbol, interval, start_dt, end_dt=None, limit=1000):
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms   = int(end_dt.timestamp() * 1000) if end_dt else None
    all_k = []
    while True:
        params = {"symbol": symbol, "interval": interval,
                  "startTime": start_ms, "limit": limit}
        if end_ms:
            params["endTime"] = end_ms
        batch = requests.get("https://api.binance.com/api/v3/klines",
                             params=params, timeout=15).json()
        if not batch:
            break
        all_k.extend(batch)
        if len(batch) < limit:
            break
        start_ms = batch[-1][0] + 1
        if end_ms and start_ms >= end_ms:
            break
    return all_k


# ─── EMA ──────────────────────────────────────────────────────────────────────

def calcular_ema_serie(closes, period):
    k = 2 / (period + 1)
    ema = closes[0]
    result = [ema]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
        result.append(ema)
    return result


def build_ema_diaria(klines_1d, period):
    """Devuelve dict fecha_str -> EMA calculada hasta ese día (inclusive).
    Para anti-lookahead: señal del día D usa ema_dict[D-1].
    """
    closes = [float(k[4]) for k in klines_1d]
    dates  = [datetime.fromtimestamp(k[0]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
              for k in klines_1d]
    emas = calcular_ema_serie(closes, period)
    return {d: e for d, e in zip(dates, emas)}


# ─── RSI ──────────────────────────────────────────────────────────────────────

def calcular_rsi_serie(closes, period=14):
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains  = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    rsi_vals = []
    for i in range(period, len(deltas)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rs = avg_g / avg_l if avg_l != 0 else 100
        rsi_vals.append(100 - 100 / (1 + rs))
    # rsi_vals[i] corresponde a closes[i + period + 1]
    return rsi_vals


# ─── Backtest ─────────────────────────────────────────────────────────────────

def backtest(klines_4h, ema_dict, rsi_min, rsi_max, sl_pct, tp_pct,
             start_dt, end_dt, use_ema_gate=False, ema_period=200):
    """
    Retorna lista de trades: {"entry_dt", "exit_dt", "tipo", "pnl_neto", "mes"}
    """
    closes = [float(k[4]) for k in klines_4h]
    highs  = [float(k[2]) for k in klines_4h]
    lows   = [float(k[3]) for k in klines_4h]
    times  = [datetime.fromtimestamp(k[0]/1000, tz=timezone.utc) for k in klines_4h]

    rsi_serie = calcular_rsi_serie(closes, 14)
    # rsi_serie[i] corresponde al índice i + 15 en closes
    RSI_OFFSET = 15

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms   = int(end_dt.timestamp() * 1000)

    COMISION = 0.002  # 0.1% * 2 lados
    CAPITAL  = 5.0

    trades = []
    posicion = None  # {"entry_price", "sl", "tp", "entry_dt"}

    for i in range(RSI_OFFSET, len(closes)):
        t = times[i]
        if t.timestamp() * 1000 < start_ms or t.timestamp() * 1000 > end_ms:
            continue

        rsi = rsi_serie[i - RSI_OFFSET]
        c   = closes[i]
        h   = highs[i]
        lo  = lows[i]

        # Gestión de posición abierta
        if posicion:
            sl = posicion["sl"]
            tp = posicion["tp"]
            if lo <= sl and h >= tp:
                # Ambos tocados — priorizar SL
                pnl = CAPITAL * (-sl_pct/100) - CAPITAL * COMISION
                trades.append({"entry_dt": posicion["entry_dt"], "exit_dt": t,
                               "tipo": "SL", "pnl_neto": pnl,
                               "mes": f"{t.year}-{t.month:02d}"})
                posicion = None
            elif h >= tp:
                pnl = CAPITAL * (tp_pct/100) - CAPITAL * COMISION
                trades.append({"entry_dt": posicion["entry_dt"], "exit_dt": t,
                               "tipo": "TP", "pnl_neto": pnl,
                               "mes": f"{t.year}-{t.month:02d}"})
                posicion = None
            elif lo <= sl:
                pnl = CAPITAL * (-sl_pct/100) - CAPITAL * COMISION
                trades.append({"entry_dt": posicion["entry_dt"], "exit_dt": t,
                               "tipo": "SL", "pnl_neto": pnl,
                               "mes": f"{t.year}-{t.month:02d}"})
                posicion = None
            continue

        # Señal de entrada
        if rsi < rsi_min or rsi > rsi_max:
            continue

        if use_ema_gate:
            dia_anterior = (t - timedelta(days=1)).strftime("%Y-%m-%d")
            ema_val = ema_dict.get(dia_anterior)
            if ema_val is None or c <= ema_val:
                continue

        # Entrada
        posicion = {
            "entry_price": c,
            "sl": c * (1 - sl_pct / 100),
            "tp": c * (1 + tp_pct / 100),
            "entry_dt": t,
        }

    return trades


# ─── Métricas ─────────────────────────────────────────────────────────────────

def metricas(trades, periodo_meses):
    if not trades:
        return {"n": 0, "tp": 0, "sl": 0, "wr": 0, "exp": 0, "pf": 0,
                "capital": 20.0, "dd": 0, "t_mes": 0, "t_anio": 0, "meses_activos": 0}
    n   = len(trades)
    tps = [t for t in trades if t["tipo"] == "TP"]
    sls = [t for t in trades if t["tipo"] == "SL"]
    wr  = len(tps) / n * 100
    exp = sum(t["pnl_neto"] for t in trades) / n

    gan = sum(t["pnl_neto"] for t in tps) if tps else 0
    per = abs(sum(t["pnl_neto"] for t in sls)) if sls else 0
    pf  = gan / per if per > 0 else (999.0 if gan > 0 else 0.0)

    # Capital desde $20 (suma simple de P/L)
    cap = 20.0
    pico = 20.0
    dd_max = 0.0
    for t in trades:
        cap += t["pnl_neto"]
        if cap > pico:
            pico = cap
        dd = (pico - cap) / pico * 100
        if dd > dd_max:
            dd_max = dd

    meses_set = set(t["mes"] for t in trades)
    t_mes  = n / periodo_meses
    t_anio = t_mes * 12

    return {"n": n, "tp": len(tps), "sl": len(sls), "wr": round(wr, 1),
            "exp": round(exp, 4), "pf": round(pf, 3), "capital": round(cap, 2),
            "dd": round(dd_max, 1), "t_mes": round(t_mes, 1),
            "t_anio": round(t_anio, 1), "meses_activos": len(meses_set)}


# ─── Bootstrap ────────────────────────────────────────────────────────────────

def bootstrap(trades_c, trades_prod, n=10000, seed=42):
    random.seed(seed)
    pnls_c    = [t["pnl_neto"] for t in trades_c]
    pnls_prod = [t["pnl_neto"] for t in trades_prod]
    if not pnls_c or not pnls_prod:
        return {"p_delta_pos": 0, "ic_low": 0, "ic_high": 0}

    deltas = []
    for _ in range(n):
        sample_c    = random.choices(pnls_c, k=len(pnls_c))
        sample_prod = random.choices(pnls_prod, k=len(pnls_prod))
        deltas.append(sum(sample_c)/len(sample_c) - sum(sample_prod)/len(sample_prod))

    deltas.sort()
    p_pos  = sum(1 for d in deltas if d > 0) / n * 100
    ic_low  = deltas[int(n * 0.025)]
    ic_high = deltas[int(n * 0.975)]
    return {"p_delta_pos": round(p_pos, 1), "ic_low": round(ic_low, 4),
            "ic_high": round(ic_high, 4)}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    SYMBOL = "LINKUSDT"

    # Períodos
    TRAIN_START   = datetime(2021, 1,  1, tzinfo=timezone.utc)
    TRAIN_END     = datetime(2023, 12, 31, 23, 59, tzinfo=timezone.utc)
    OOS_START     = datetime(2024, 1,  1, tzinfo=timezone.utc)
    OOS_END       = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
    FWD_START     = datetime(2026, 1,  1, tzinfo=timezone.utc)
    FWD_END       = datetime(2026, 8, 15, tzinfo=timezone.utc)

    TRAIN_MESES = 36
    OOS_MESES   = 24
    FWD_MESES   = 7.5

    print(f"Descargando velas 4H {SYMBOL}...")
    klines_4h = descargar_klines(SYMBOL, "4h",
                                  datetime(2020, 6, 1, tzinfo=timezone.utc), FWD_END)
    print(f"  {len(klines_4h)} velas 4H descargadas")

    print(f"Descargando velas 1D {SYMBOL} (warmup EMA desde 2018)...")
    klines_1d = descargar_klines(SYMBOL, "1d",
                                  datetime(2018, 1, 1, tzinfo=timezone.utc), FWD_END)
    print(f"  {len(klines_1d)} velas diarias descargadas")

    # EMA dicts para vecindad
    ema_dicts = {}
    for period in [100, 150, 200, 250]:
        ema_dicts[period] = build_ema_diaria(klines_1d, period)
        print(f"  EMA{period} calculada: {len(ema_dicts[period])} fechas")

    ema200 = ema_dicts[200]

    # ── Train ──────────────────────────────────────────────────────────────────
    print("\n=== TRAIN 2021-2023 ===")
    t_prod_train = backtest(klines_4h, ema200, 50, 70, 5.0, 6.0,
                            TRAIN_START, TRAIN_END, use_ema_gate=False)
    t_c_train    = backtest(klines_4h, ema200, 55, 60, 5.0, 6.0,
                            TRAIN_START, TRAIN_END, use_ema_gate=True, ema_period=200)
    m_prod_train = metricas(t_prod_train, TRAIN_MESES)
    m_c_train    = metricas(t_c_train,    TRAIN_MESES)
    print(f"  Producción: {m_prod_train['n']} trades | PF {m_prod_train['pf']} | WR {m_prod_train['wr']}% | {m_prod_train['t_mes']} t/mes")
    print(f"  Sistema C:  {m_c_train['n']} trades | PF {m_c_train['pf']} | WR {m_c_train['wr']}% | {m_c_train['t_mes']} t/mes")

    # ── OOS ───────────────────────────────────────────────────────────────────
    print("\n=== OOS 2024-2025 ===")
    t_prod_oos = backtest(klines_4h, ema200, 50, 70, 5.0, 6.0,
                          OOS_START, OOS_END, use_ema_gate=False)
    t_c_oos    = backtest(klines_4h, ema200, 55, 60, 5.0, 6.0,
                          OOS_START, OOS_END, use_ema_gate=True, ema_period=200)
    m_prod_oos = metricas(t_prod_oos, OOS_MESES)
    m_c_oos    = metricas(t_c_oos,    OOS_MESES)
    print(f"  Producción: {m_prod_oos['n']} trades | PF {m_prod_oos['pf']} | WR {m_prod_oos['wr']}% | {m_prod_oos['t_mes']} t/mes")
    print(f"  Sistema C:  {m_c_oos['n']} trades | PF {m_c_oos['pf']} | WR {m_c_oos['wr']}% | {m_c_oos['t_mes']} t/mes")

    # ── Forward ───────────────────────────────────────────────────────────────
    print("\n=== FORWARD 2026 ===")
    t_prod_fwd = backtest(klines_4h, ema200, 50, 70, 5.0, 6.0,
                          FWD_START, FWD_END, use_ema_gate=False)
    t_c_fwd    = backtest(klines_4h, ema200, 55, 60, 5.0, 6.0,
                          FWD_START, FWD_END, use_ema_gate=True, ema_period=200)
    m_prod_fwd = metricas(t_prod_fwd, FWD_MESES)
    m_c_fwd    = metricas(t_c_fwd,    FWD_MESES)
    print(f"  Producción: {m_prod_fwd['n']} trades | PF {m_prod_fwd['pf']} | {m_prod_fwd['t_mes']} t/mes")
    print(f"  Sistema C:  {m_c_fwd['n']} trades | PF {m_c_fwd['pf']} | {m_c_fwd['t_mes']} t/mes")

    # ── Vecindad EMA (OOS) ────────────────────────────────────────────────────
    print("\n=== VECINDAD EMA (OOS) ===")
    vecindad = {}
    for period in [100, 150, 200, 250]:
        tr = backtest(klines_4h, ema_dicts[period], 55, 60, 5.0, 6.0,
                      OOS_START, OOS_END, use_ema_gate=True, ema_period=period)
        m = metricas(tr, OOS_MESES)
        vecindad[period] = m
        print(f"  EMA{period}: {m['n']} trades | PF {m['pf']} | WR {m['wr']}% | Exp ${m['exp']}")

    emas_positivas = sum(1 for m in vecindad.values() if m["pf"] > 1.0)

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    print("\n=== BOOTSTRAP OOS ===")
    bs = bootstrap(t_c_oos, t_prod_oos)
    print(f"  P(Δ>0): {bs['p_delta_pos']}% | IC95%: [{bs['ic_low']}, {bs['ic_high']}]")

    # ── Frecuencia vs BNB-C ───────────────────────────────────────────────────
    BNNB_C_OOS  = 3.0
    BNNB_C_FWD  = 0.4

    # ── Veredicto ─────────────────────────────────────────────────────────────
    pf_oos = m_c_oos["pf"]
    if pf_oos > 1.0 and emas_positivas == 4 and bs["ic_low"] > 0:
        veredicto = "A) ROBUSTO"
    elif pf_oos > 1.0 and emas_positivas >= 3:
        veredicto = "B) PROMETEDOR"
    elif pf_oos > 1.0 and emas_positivas >= 1:
        veredicto = "C) NO_APORTA_MEJORA_CLARA"
    elif pf_oos > 1.0 and emas_positivas == 0:
        veredicto = "D) INSUFICIENTE"
    else:
        veredicto = "E) DESCARTADO"

    print(f"\n=== VEREDICTO: {veredicto} ===")
    print(f"PF OOS: {pf_oos} | EMAs>1: {emas_positivas}/4 | P(Δ>0): {bs['p_delta_pos']}%")

    # ── Reporte ───────────────────────────────────────────────────────────────
    reporte = f"""# LINK Sistema C — Prueba #1

## Ficha de la prueba

| Campo | Valor |
|---|---|
| Continúa de | Segunda lista Sistema C (orden: XRP → **LINK** → UNI → NEAR → ADA) |
| Aprendido | Sistema C funciona en BTC/BNB (4/4 EMAs OOS); falla en ETH/SOL/AVAX/XRP (0/4 cada uno) |
| Hipótesis | RSI 55–60 + EMA200d puede generar señales rentables en LINK con mayor frecuencia que BNB-C |
| RSI entrada | 55–60 |
| SL / TP | 5.0% / 6.0% |
| Gate EMA | EMA200d diaria anti-lookahead (close[D-1] > EMA200d[D-1]) |
| Comisión | 0.1% por lado (0.2% total) |
| Capital por trade | $5 |
| Criterio de éxito | PF OOS > 1.0, vecindad 4/4 EMAs positiva, IC95% no cruza cero |
| LINK en producción | NO — no está en config_cartera.py; baseline usa RSI 50–70 estándar |

## Datos verificados

| Campo | Valor |
|---|---|
| Par | LINKUSDT |
| Completitud 4H 2021–2026 | 100% (12316 velas) |
| Historia disponible | desde 2019-01-16 |
| Régimen hoy (2026-08-15) | BAJO EMA200d (−0.5%, $9.464 vs $9.513) |
| Fuente | Binance API pública |

## Resultados — Baseline LINK (RSI 50–70, sin gate EMA)

| Métrica | Train 2021–2023 | OOS 2024–2025 |
|---|---|---|
| Trades | {m_prod_train['n']} | {m_prod_oos['n']} |
| TP / SL | {m_prod_train['tp']} / {m_prod_train['sl']} | {m_prod_oos['tp']} / {m_prod_oos['sl']} |
| Win Rate | {m_prod_train['wr']}% | {m_prod_oos['wr']}% |
| Expectancy | ${m_prod_train['exp']} | ${m_prod_oos['exp']} |
| Profit Factor | {m_prod_train['pf']} | {m_prod_oos['pf']} |
| Capital final ($20 base) | ${m_prod_train['capital']} | ${m_prod_oos['capital']} |
| Drawdown máx | {m_prod_train['dd']}% | {m_prod_oos['dd']}% |
| Trades/mes | {m_prod_train['t_mes']} | {m_prod_oos['t_mes']} |
| Trades/año | {m_prod_train['t_anio']} | {m_prod_oos['t_anio']} |
| Meses activos | {m_prod_train['meses_activos']}/36 | {m_prod_oos['meses_activos']}/24 |

## Resultados — Sistema C LINK (RSI 55–60 + EMA200d gate)

| Métrica | Train 2021–2023 | OOS 2024–2025 | Forward 2026 |
|---|---|---|---|
| Trades | {m_c_train['n']} | {m_c_oos['n']} | {m_c_fwd['n']} |
| TP / SL | {m_c_train['tp']} / {m_c_train['sl']} | {m_c_oos['tp']} / {m_c_oos['sl']} | {m_c_fwd['tp']} / {m_c_fwd['sl']} |
| Win Rate | {m_c_train['wr']}% | {m_c_oos['wr']}% | {m_c_fwd['wr']}% |
| Expectancy | ${m_c_train['exp']} | ${m_c_oos['exp']} | ${m_c_fwd['exp']} |
| Profit Factor | {m_c_train['pf']} | {m_c_oos['pf']} | {m_c_fwd['pf']} |
| Capital final ($20 base) | ${m_c_train['capital']} | ${m_c_oos['capital']} | ${m_c_fwd['capital']} |
| Drawdown máx | {m_c_train['dd']}% | {m_c_oos['dd']}% | {m_c_fwd['dd']}% |
| Trades/mes | {m_c_train['t_mes']} | {m_c_oos['t_mes']} | {m_c_fwd['t_mes']} |
| Trades/año | {m_c_train['t_anio']} | {m_c_oos['t_anio']} | {m_c_fwd['t_anio']} |
| Meses activos | {m_c_train['meses_activos']}/36 | {m_c_oos['meses_activos']}/24 | {m_c_fwd['meses_activos']}/8 |

## Frecuencia operativa — comparación vs BNB-C

| Sistema | Trades/mes OOS | Trades/mes Forward 2026 | vs BNB-C OOS | vs BNB-C Fwd |
|---|---|---|---|---|
| BNB-C (referencia) | {BNNB_C_OOS} | {BNNB_C_FWD} | — | — |
| LINK Baseline | {m_prod_oos['t_mes']} | {m_prod_fwd['t_mes']} | {"✅ mayor" if m_prod_oos['t_mes'] > BNNB_C_OOS else "❌ menor"} | {"✅ mayor" if m_prod_fwd['t_mes'] > BNNB_C_FWD else "❌ menor"} |
| LINK Sistema C | {m_c_oos['t_mes']} | {m_c_fwd['t_mes']} | {"✅ mayor" if m_c_oos['t_mes'] > BNNB_C_OOS else "❌ menor"} | {"✅ mayor" if m_c_fwd['t_mes'] > BNNB_C_FWD else "❌ menor"} |

## Robustez vecindad EMA (OOS 2024–2025)

| EMA | Trades | PF | WR% | Expectancy | Veredicto |
|---|---|---|---|---|---|
| EMA100 | {vecindad[100]['n']} | {vecindad[100]['pf']} | {vecindad[100]['wr']}% | ${vecindad[100]['exp']} | {"✅" if vecindad[100]['pf'] > 1.0 else "❌"} |
| EMA150 | {vecindad[150]['n']} | {vecindad[150]['pf']} | {vecindad[150]['wr']}% | ${vecindad[150]['exp']} | {"✅" if vecindad[150]['pf'] > 1.0 else "❌"} |
| EMA200 | {vecindad[200]['n']} | {vecindad[200]['pf']} | {vecindad[200]['wr']}% | ${vecindad[200]['exp']} | {"✅" if vecindad[200]['pf'] > 1.0 else "❌"} |
| EMA250 | {vecindad[250]['n']} | {vecindad[250]['pf']} | {vecindad[250]['wr']}% | ${vecindad[250]['exp']} | {"✅" if vecindad[250]['pf'] > 1.0 else "❌"} |

**EMAs con PF > 1.0: {emas_positivas}/4**

## Bootstrap (OOS 2024–2025) — Sistema C vs Baseline

| Métrica | Valor |
|---|---|
| Delta Expectancy medio | ${round(m_c_oos['exp'] - m_prod_oos['exp'], 4)} |
| P(Δ > 0) | {bs['p_delta_pos']}% |
| IC 95% del delta | [{bs['ic_low']}, {bs['ic_high']}] |
| IC cruza cero | {"Sí ⚠️" if bs['ic_low'] < 0 < bs['ic_high'] else "No"} |

*Limitación: trades serialmente dependientes — bootstrap subestima varianza real. No interpretar como prueba estadística formal.*

## Veredicto

### 🔴 {veredicto}

| Criterio | Valor | Umbral | Resultado |
|---|---|---|---|
| PF OOS > 1.0 | {pf_oos} | > 1.0 | {"✅" if pf_oos > 1.0 else "❌"} |
| Vecindad EMA | {emas_positivas}/4 positivas | 4/4 | {"✅" if emas_positivas == 4 else "⚠️" if emas_positivas >= 2 else "❌"} |
| P(Δ > 0) | {bs['p_delta_pos']}% | ≥ 85% orientativo | {"✅" if bs['p_delta_pos'] >= 85 else "❌"} |
| IC 95% | [{bs['ic_low']}, {bs['ic_high']}] | no cruza cero | {"✅" if bs['ic_low'] > 0 else "❌"} |
| Frecuencia OOS | {m_c_oos['t_mes']} t/mes | > BNB-C (3.0) | {"✅" if m_c_oos['t_mes'] > 3.0 else "❌"} |

## Conclusión

El patrón RSI 55–60 + gate EMA200d {"muestra evidencia positiva en LINK" if pf_oos > 1.0 else "no funciona en LINK"} durante el período OOS 2024–2025.

{"Con PF OOS " + str(pf_oos) + " y " + str(emas_positivas) + "/4 EMAs positivas en vecindad, el sistema es " + veredicto.split(")")[1].strip() + "." if True else ""}

Patrón acumulado Sistema C:
- BTC: 🟡 PROMETEDOR (4/4 EMAs, PF 1.322)
- BNB: 🟡 PROMETEDOR (4/4 EMAs, PF 1.318)
- ETH: 🔴 DESCARTADO (0/4 EMAs, PF 0.960)
- SOL: 🔴 DESCARTADO (0/4 EMAs, PF 0.984)
- AVAX: 🔴 DESCARTADO (0/4 EMAs, PF 0.707)
- XRP: 🔴 DESCARTADO (0/4 EMAs, PF 0.800)
- **LINK: {"🟡 PROMETEDOR" if "PROMETEDOR" in veredicto or "ROBUSTO" in veredicto else "🔴 DESCARTADO"} ({emas_positivas}/4 EMAs, PF {pf_oos})**

## Siguiente paso

{"LINK descartado. Continuar con UNI (siguiente en la segunda lista)." if "DESCARTADO" in veredicto else "LINK prometedor. Analizar estabilidad anual y walk-forward antes de decidir activación."}

Producción LINK: no existe — no hay nada que preservar ni modificar.

---
*Generado: 2026-08-15 | Script: sistema_c/link_sistema_c_prueba1.py | Datos: Binance API*
"""

    ruta = "/home/ariel/bot-padre-v2/reports/2026-08-15_link-sistema-c-prueba1.md"
    with open(ruta, "w") as f:
        f.write(reporte)
    print(f"\nReporte escrito en: {ruta}")
    print(f"\nRESUMEN FINAL:")
    print(f"  Veredicto:    {veredicto}")
    print(f"  PF OOS:       {pf_oos}")
    print(f"  EMAs>1:       {emas_positivas}/4")
    print(f"  P(Δ>0):       {bs['p_delta_pos']}%")
    print(f"  Trades/mes:   {m_c_oos['t_mes']} OOS | {m_c_fwd['t_mes']} Forward 2026")


if __name__ == "__main__":
    main()
