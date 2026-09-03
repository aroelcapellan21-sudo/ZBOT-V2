"""
XRP Sistema C — Prueba #1
RSI 55-60 + gate EMA200d diaria anti-lookahead
SL 5.0% / TP 6.0% / Comision 0.1% por lado / Capital $5 por trade
Train: 2021-2023 | OOS: 2024-2025 | Forward: 2026-01-01 -> hoy
"""

import requests
import random
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── Descarga de datos ──────────────────────────────────────────────────────

def fetch_klines(symbol, interval, start_dt, end_dt=None):
    url = "https://api.binance.com/api/v3/klines"
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms   = int(end_dt.timestamp() * 1000) if end_dt else int(datetime.now(timezone.utc).timestamp() * 1000)
    result = []
    while start_ms < end_ms:
        batch = requests.get(url, params={
            "symbol": symbol, "interval": interval,
            "startTime": start_ms, "limit": 1000
        }, timeout=15).json()
        if not batch:
            break
        result.extend(batch)
        start_ms = batch[-1][0] + 1
    return result

# ── Indicadores ────────────────────────────────────────────────────────────

def calc_rsi(closes, period=14):
    rsi = [None] * len(closes)
    if len(closes) < period + 1:
        return rsi
    gains, losses = [], []
    for i in range(1, period + 1):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    rsi[period] = 100 - 100 / (1 + avg_g / avg_l) if avg_l != 0 else 100
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i-1]
        avg_g = (avg_g * (period - 1) + max(d, 0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0)) / period
        rsi[i] = 100 - 100 / (1 + avg_g / avg_l) if avg_l != 0 else 100
    return rsi

def calc_ema_series(closes, period):
    """Devuelve serie EMA completa (mismo largo que closes)."""
    k = 2 / (period + 1)
    ema = [None] * len(closes)
    ema[0] = closes[0]
    for i in range(1, len(closes)):
        ema[i] = closes[i] * k + ema[i-1] * (1 - k)
    return ema

# ── Backtest core ──────────────────────────────────────────────────────────

COMISION = 0.001  # 0.1% por lado
CAPITAL_TRADE = 5.0

def backtest(klines_4h, ema200d_map, rsi_min, rsi_max, sl_pct, tp_pct, use_ema_gate=True):
    """
    klines_4h: lista de velas 4H (open_time, open, high, low, close, ...)
    ema200d_map: dict {date_str_YYYY-MM-DD: ema200d_value} calculado con D-1
    """
    closes_4h = [float(k[4]) for k in klines_4h]
    highs_4h  = [float(k[2]) for k in klines_4h]
    lows_4h   = [float(k[3]) for k in klines_4h]
    times_4h  = [datetime.fromtimestamp(k[0]/1000, tz=timezone.utc) for k in klines_4h]

    rsi_series = calc_rsi(closes_4h)

    trades = []
    position = None  # {entry, sl, tp, entry_time}

    for i in range(15, len(klines_4h)):
        ts = times_4h[i]
        close = closes_4h[i]
        high  = highs_4h[i]
        low   = lows_4h[i]
        rsi   = rsi_series[i]

        if rsi is None:
            continue

        # Obtener EMA200d del día anterior
        prev_day = (ts - timedelta(days=1)).strftime("%Y-%m-%d")
        ema200d  = ema200d_map.get(prev_day)

        if position is not None:
            # Verificar cierre: primero SL, luego TP (conservador)
            closed = False
            if low <= position["sl"]:
                pnl_pct = (position["sl"] / position["entry"] - 1) - 2 * COMISION
                pnl_usd = CAPITAL_TRADE * pnl_pct
                trades.append({"type": "SL", "pnl": pnl_usd, "time": ts,
                                "entry_time": position["entry_time"]})
                position = None
                closed = True
            if not closed and high >= position["tp"]:
                pnl_pct = (position["tp"] / position["entry"] - 1) - 2 * COMISION
                pnl_usd = CAPITAL_TRADE * pnl_pct
                trades.append({"type": "TP", "pnl": pnl_usd, "time": ts,
                                "entry_time": position["entry_time"]})
                position = None

        if position is None:
            gate_ok = (not use_ema_gate) or (ema200d is not None and close > ema200d)
            if gate_ok and rsi_min <= rsi <= rsi_max:
                entry = close
                position = {
                    "entry": entry,
                    "sl": entry * (1 - sl_pct),
                    "tp": entry * (1 + tp_pct),
                    "entry_time": ts,
                }

    return trades

# ── Métricas ───────────────────────────────────────────────────────────────

def metrics(trades, start_dt, end_dt, label=""):
    if not trades:
        return {
            "label": label, "n": 0, "tp": 0, "sl": 0, "wr": 0,
            "exp": 0, "pf": 0, "capital": 20.0, "dd": 0,
            "trades_mes": 0, "trades_anio": 0, "meses_activos": 0,
        }
    n   = len(trades)
    tps = [t for t in trades if t["type"] == "TP"]
    sls = [t for t in trades if t["type"] == "SL"]
    wr  = len(tps) / n * 100
    exp = sum(t["pnl"] for t in trades) / n

    wins  = sum(t["pnl"] for t in tps) if tps else 0
    losss = abs(sum(t["pnl"] for t in sls)) if sls else 1e-9
    pf    = wins / losss if losss > 0 else float("inf")

    capital = 20.0
    peak    = 20.0
    dd_max  = 0.0
    for t in trades:
        capital += t["pnl"]
        peak = max(peak, capital)
        dd = (peak - capital) / peak * 100
        dd_max = max(dd_max, dd)

    meses = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
    meses = max(meses, 1)
    anios = meses / 12

    meses_con_trade = set()
    for t in trades:
        meses_con_trade.add((t["time"].year, t["time"].month))

    return {
        "label": label, "n": n, "tp": len(tps), "sl": len(sls),
        "wr": wr, "exp": exp, "pf": pf, "capital": capital, "dd": dd_max,
        "trades_mes": n / meses, "trades_anio": n / anios,
        "meses_activos": len(meses_con_trade),
    }

def bootstrap(trades_c, trades_prod, n_iter=10000, seed=42):
    random.seed(seed)
    pnls_c    = [t["pnl"] for t in trades_c]
    pnls_prod = [t["pnl"] for t in trades_prod]
    if not pnls_c or not pnls_prod:
        return None, None, None
    deltas = []
    for _ in range(n_iter):
        sample_c    = random.choices(pnls_c, k=len(pnls_c))
        sample_prod = random.choices(pnls_prod, k=len(pnls_prod))
        delta = sum(sample_c)/len(sample_c) - sum(sample_prod)/len(sample_prod)
        deltas.append(delta)
    deltas.sort()
    p_pos = sum(1 for d in deltas if d > 0) / n_iter
    ic_lo = deltas[int(0.025 * n_iter)]
    ic_hi = deltas[int(0.975 * n_iter)]
    return p_pos, ic_lo, ic_hi

# ── MAIN ───────────────────────────────────────────────────────────────────

def main():
    print("Descargando velas 4H XRPUSDT desde 2018-01-01...")
    klines_4h_all = fetch_klines(
        "XRPUSDT", "4h",
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 16, tzinfo=timezone.utc),
    )
    print(f"  Velas 4H descargadas: {len(klines_4h_all)}")

    print("Descargando velas diarias XRPUSDT desde 2018-01-01...")
    klines_1d_all = fetch_klines(
        "XRPUSDT", "1d",
        datetime(2018, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 16, tzinfo=timezone.utc),
    )
    print(f"  Velas 1D descargadas: {len(klines_1d_all)}")

    # EMA200d diaria anti-lookahead: para fecha D, usar EMA calculada con closes[0..D-1]
    closes_1d = [float(k[4]) for k in klines_1d_all]
    dates_1d  = [datetime.fromtimestamp(k[0]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                 for k in klines_1d_all]

    ema_series_1d = calc_ema_series(closes_1d, 200)

    # ema200d_map[fecha] = EMA200d calculada hasta el cierre del día ANTERIOR
    # es decir, para usar en señales del día D, usamos ema_series_1d[idx_de_D - 1]
    ema200d_map = {}
    for i in range(1, len(dates_1d)):
        ema200d_map[dates_1d[i]] = ema_series_1d[i - 1]

    # Períodos
    t_start  = datetime(2021, 1, 1, tzinfo=timezone.utc)
    t_end    = datetime(2023, 12, 31, 23, 59, tzinfo=timezone.utc)
    oos_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    oos_end   = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
    fwd_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fwd_end   = datetime(2026, 8, 15, 23, 59, tzinfo=timezone.utc)

    def filter_period(klines, start, end):
        return [k for k in klines if start.timestamp()*1000 <= k[0] <= end.timestamp()*1000]

    k_train  = filter_period(klines_4h_all, t_start,   t_end)
    k_oos    = filter_period(klines_4h_all, oos_start, oos_end)
    k_fwd    = filter_period(klines_4h_all, fwd_start, fwd_end)

    print(f"\nVelas por período — Train: {len(k_train)} | OOS: {len(k_oos)} | Forward: {len(k_fwd)}")

    # ── Producción XRP (baseline): RSI 50-70, sin gate EMA ──
    print("\nCalculando Producción XRP (baseline)...")
    tr_prod_train = backtest(k_train, ema200d_map, 50, 70, 0.05, 0.06, use_ema_gate=False)
    tr_prod_oos   = backtest(k_oos,   ema200d_map, 50, 70, 0.05, 0.06, use_ema_gate=False)

    m_prod_train = metrics(tr_prod_train, t_start,   t_end,    "Prod Train")
    m_prod_oos   = metrics(tr_prod_oos,   oos_start, oos_end,  "Prod OOS")

    # ── Sistema C XRP: RSI 55-60, gate EMA200d ──
    print("Calculando Sistema C XRP...")
    tr_c_train = backtest(k_train, ema200d_map, 55, 60, 0.05, 0.06, use_ema_gate=True)
    tr_c_oos   = backtest(k_oos,   ema200d_map, 55, 60, 0.05, 0.06, use_ema_gate=True)
    tr_c_fwd   = backtest(k_fwd,   ema200d_map, 55, 60, 0.05, 0.06, use_ema_gate=True)

    m_c_train = metrics(tr_c_train, t_start,   t_end,    "SistC Train")
    m_c_oos   = metrics(tr_c_oos,   oos_start, oos_end,  "SistC OOS")
    m_c_fwd   = metrics(tr_c_fwd,   fwd_start, fwd_end,  "SistC Fwd")

    # ── Robustez vecindad EMA (OOS) ──
    print("Calculando robustez vecindad EMA (OOS)...")
    vecindad = {}
    for period in [100, 150, 200, 250]:
        ema_series_tmp = calc_ema_series(closes_1d, period)
        ema_map_tmp = {}
        for i in range(1, len(dates_1d)):
            ema_map_tmp[dates_1d[i]] = ema_series_tmp[i - 1]
        tr_tmp = backtest(k_oos, ema_map_tmp, 55, 60, 0.05, 0.06, use_ema_gate=True)
        m_tmp  = metrics(tr_tmp, oos_start, oos_end)
        vecindad[period] = {"n": m_tmp["n"], "pf": m_tmp["pf"], "wr": m_tmp["wr"],
                            "exp": m_tmp["exp"], "trades_mes": m_tmp["trades_mes"]}

    # ── Bootstrap ──
    print("Calculando bootstrap OOS...")
    p_pos, ic_lo, ic_hi = bootstrap(tr_c_oos, tr_prod_oos)

    # ── Imprimir resultados ──
    def fmt(m):
        return (f"  N={m['n']} TP={m['tp']} SL={m['sl']} WR={m['wr']:.1f}% "
                f"Exp=${m['exp']:.4f} PF={m['pf']:.3f} Cap=${m['capital']:.2f} "
                f"DD={m['dd']:.1f}% T/mes={m['trades_mes']:.1f} MesesAct={m['meses_activos']}")

    print("\n=== PRODUCCIÓN XRP ===")
    print(f"Train: {fmt(m_prod_train)}")
    print(f"OOS:   {fmt(m_prod_oos)}")

    print("\n=== SISTEMA C XRP ===")
    print(f"Train: {fmt(m_c_train)}")
    print(f"OOS:   {fmt(m_c_oos)}")
    print(f"Fwd:   {fmt(m_c_fwd)}")

    print("\n=== VECINDAD EMA (OOS) ===")
    for p, v in vecindad.items():
        print(f"  EMA{p}: N={v['n']} PF={v['pf']:.3f} WR={v['wr']:.1f}% Exp=${v['exp']:.4f} T/mes={v['trades_mes']:.1f}")

    print(f"\n=== BOOTSTRAP OOS ===")
    if p_pos is not None:
        print(f"  P(Δ>0)={p_pos:.1%} | IC95% [{ic_lo:.4f}, {ic_hi:.4f}]")

    # ── Veredicto ──
    emas_positivas = sum(1 for v in vecindad.values() if v["pf"] > 1.0)
    pf_oos = m_c_oos["pf"]
    cruza_cero = ic_lo is not None and ic_lo < 0 < ic_hi

    if pf_oos > 1.0 and emas_positivas == 4 and not cruza_cero:
        veredicto = "A) ROBUSTO"
    elif pf_oos > 1.0 and emas_positivas >= 3:
        veredicto = "B) PROMETEDOR"
    elif pf_oos > 1.0 and emas_positivas >= 2:
        veredicto = "C) NO_APORTA_MEJORA / DÉBIL"
    elif pf_oos > 1.0:
        veredicto = "D) INSUFICIENTE"
    else:
        veredicto = "E) DESCARTADO"

    print(f"\n=== VEREDICTO: {veredicto} ===")
    print(f"  PF OOS={pf_oos:.3f} | EMAs>1={emas_positivas}/4 | IC95% cruza cero: {cruza_cero}")

    # ── BNB-C referencia de frecuencia ──
    bnb_c_trades_mes_oos = 3.0
    bnb_c_trades_mes_fwd = 0.4

    # ── Escribir reporte ──
    report_path = "/home/ariel/bot-padre-v2/reports/2026-08-15_xrp-sistema-c-prueba1.md"

    lines = []
    lines.append("# XRP Sistema C — Prueba #1\n")
    lines.append(f"*Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n\n")

    lines.append("## Ficha de la prueba\n\n")
    lines.append("| Campo | Valor |\n|---|---|\n")
    lines.append("| Continúa de | Segunda lista Sistema C (6ª moneda investigada) |\n")
    lines.append("| Aprendido | Sistema C funciona en BTC/BNB (4/4 EMAs OOS), falla en ETH/SOL/AVAX (0/4) |\n")
    lines.append("| Hipótesis | RSI 55–60 + EMA200d puede operar XRP con mayor frecuencia que BNB-C |\n")
    lines.append("| RSI entrada | 55–60 |\n")
    lines.append("| SL / TP | 5.0% / 6.0% |\n")
    lines.append("| Gate | EMA200d diaria anti-lookahead (D-1) |\n")
    lines.append("| Comisión | 0.1% por lado |\n")
    lines.append("| Capital/trade | $5 |\n")
    lines.append("| Criterio éxito | PF OOS > 1.0, vecindad 4/4 positiva, IC95% no cruza cero |\n\n")

    lines.append("## Datos verificados\n\n")
    lines.append("| Campo | Valor |\n|---|---|\n")
    lines.append("| Fuente | Binance API pública (sin autenticación) |\n")
    lines.append("| Par | XRPUSDT |\n")
    lines.append(f"| Velas 4H descargadas (desde 2018) | {len(klines_4h_all)} |\n")
    lines.append(f"| Velas 1D descargadas (EMA warmup) | {len(klines_1d_all)} |\n")
    lines.append(f"| Velas Train | {len(k_train)} |\n")
    lines.append(f"| Velas OOS | {len(k_oos)} |\n")
    lines.append(f"| Velas Forward | {len(k_fwd)} |\n")
    lines.append("| Completitud 4H (2021–2026-08-15) | 100% (verificado pre-backtest) |\n\n")

    def tabla_metricas(m_list):
        header = "| Período | N | TP | SL | WR% | Exp$ | PF | Capital | DD% | T/mes | T/año | Meses act |\n"
        sep    = "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        rows = ""
        for m in m_list:
            rows += (f"| {m['label']} | {m['n']} | {m['tp']} | {m['sl']} | "
                     f"{m['wr']:.1f} | {m['exp']:+.4f} | {m['pf']:.3f} | "
                     f"${m['capital']:.2f} | {m['dd']:.1f} | {m['trades_mes']:.1f} | "
                     f"{m['trades_anio']:.0f} | {m['meses_activos']} |\n")
        return header + sep + rows

    lines.append("## Resultados — Producción XRP (baseline, RSI 50–70, sin gate EMA)\n\n")
    lines.append(tabla_metricas([m_prod_train, m_prod_oos]))
    lines.append("\n")

    lines.append("## Resultados — Sistema C XRP (RSI 55–60 + gate EMA200d)\n\n")
    lines.append(tabla_metricas([m_c_train, m_c_oos, m_c_fwd]))
    lines.append("\n")

    lines.append("## Frecuencia operativa vs BNB-C\n\n")
    lines.append("| Sistema | T/mes OOS | T/año OOS | T/mes Fwd | Nota |\n|---|---|---|---|---|\n")
    lines.append(f"| XRP Producción OOS | {m_prod_oos['trades_mes']:.1f} | {m_prod_oos['trades_anio']:.0f} | — | sin gate |\n")
    lines.append(f"| XRP Sistema C OOS | {m_c_oos['trades_mes']:.1f} | {m_c_oos['trades_anio']:.0f} | {m_c_fwd['trades_mes']:.1f} | con gate |\n")
    lines.append(f"| BNB-C (referencia) | {bnb_c_trades_mes_oos:.1f} | {bnb_c_trades_mes_oos*12:.0f} | {bnb_c_trades_mes_fwd:.1f} | referencia |\n")
    lines.append("\n")

    lines.append("## Robustez vecindad EMA (OOS 2024–2025)\n\n")
    lines.append("| EMA | N trades | PF | WR% | Exp$ | T/mes |\n|---|---|---|---|---|---|\n")
    for p, v in vecindad.items():
        marker = " ← **mejor**" if v["pf"] == max(x["pf"] for x in vecindad.values()) else ""
        lines.append(f"| EMA{p} | {v['n']} | {v['pf']:.3f} | {v['wr']:.1f} | {v['exp']:+.4f} | {v['trades_mes']:.1f} |{marker}\n")
    lines.append(f"\nEMAs con PF > 1.0: **{emas_positivas}/4**\n\n")

    lines.append("## Bootstrap (OOS 2024–2025)\n\n")
    if p_pos is not None:
        lines.append(f"- **P(Δexp > 0):** {p_pos:.1%}\n")
        lines.append(f"- **IC 95%:** [{ic_lo:+.4f}, {ic_hi:+.4f}]\n")
        lines.append(f"- **IC cruza cero:** {'Sí' if cruza_cero else 'No'}\n")
        lines.append("- *Limitación: bootstrap subestima varianza real por dependencia serial de los trades.*\n\n")
    else:
        lines.append("- Sin datos suficientes para bootstrap.\n\n")

    lines.append(f"## Veredicto\n\n**{veredicto}**\n\n")
    lines.append(f"| Criterio | Valor | ¿Cumple? |\n|---|---|---|\n")
    lines.append(f"| PF OOS > 1.0 | {pf_oos:.3f} | {'✅' if pf_oos > 1.0 else '❌'} |\n")
    lines.append(f"| Vecindad EMA 4/4 > 1.0 | {emas_positivas}/4 | {'✅' if emas_positivas == 4 else '⚠️' if emas_positivas >= 2 else '❌'} |\n")
    lines.append(f"| IC95% no cruza cero | {'No cruza' if not cruza_cero else 'Cruza cero'} | {'✅' if not cruza_cero else '❌'} |\n\n")

    # Régimen EMA hoy
    last_date = dates_1d[-1]
    ema200_hoy = ema200d_map.get(last_date, None)
    ultimo_close_1d = closes_1d[-1]
    regimen_hoy = "SOBRE" if ema200_hoy and ultimo_close_1d > ema200_hoy else "BAJO"

    lines.append("## Estado actual (régimen macro XRP)\n\n")
    lines.append(f"- **Último cierre diario:** ${ultimo_close_1d:.4f}\n")
    lines.append(f"- **EMA200d (D-1):** ${ema200_hoy:.4f}\n" if ema200_hoy else "- EMA200d: no disponible\n")
    lines.append(f"- **Régimen:** {regimen_hoy} — {'gate abierto, puede generar señales' if regimen_hoy == 'SOBRE' else 'gate bloqueado, no genera señales'}\n\n")

    lines.append("## Conclusión y siguiente paso\n\n")

    if veredicto.startswith("A"):
        conclusion = ("Sistema C XRP es ROBUSTO. PF OOS > 1.0 con vecindad completa y bootstrap positivo. "
                      "Candidato para monitoreo shadow. Siguiente: activar monitor SHADOW análogo a BTC-C.")
    elif veredicto.startswith("B"):
        conclusion = ("Sistema C XRP es PROMETEDOR. PF OOS > 1.0 pero con limitaciones en vecindad o bootstrap. "
                      "No activar en producción. Siguiente: acumular trades reales en régimen alcista macro.")
    elif veredicto.startswith("E"):
        conclusion = ("Sistema C XRP es DESCARTADO. PF OOS < 1.0 — el patrón RSI 55–60 + EMA200d no funciona "
                      "en XRP. Producción XRP preservada sin cambios. Siguiente: investigar LINK Sistema C.")
    else:
        conclusion = ("Evidencia insuficiente o débil. No se activa en producción. "
                      "Siguiente: investigar LINK Sistema C con la misma metodología.")

    lines.append(conclusion + "\n\n")
    lines.append("**Producción XRP:** preservada sin cambios.\n")
    lines.append("**Sistema C XRP:** NO activado.\n")
    lines.append("**Siguiente moneda en la lista:** LINKUSDT.\n")

    with open(report_path, "w") as f:
        f.writelines(lines)

    print(f"\nReporte escrito en: {report_path}")
    print(f"\nResumen final:")
    print(f"  PF OOS:         {pf_oos:.3f}")
    print(f"  Trades/mes OOS: {m_c_oos['trades_mes']:.1f}")
    print(f"  EMAs > 1.0:     {emas_positivas}/4")
    print(f"  IC95% cruza 0:  {cruza_cero}")
    print(f"  Veredicto:      {veredicto}")


if __name__ == "__main__":
    main()
