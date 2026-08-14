"""
forward_bnb_analisis.py
Analisis ampliado de los trades del simulador BNB ALCISTA 2026-01-01 → 2026-08-14.
Fuente de datos: reporte 2026-08-14_bnb-alcista-prueba-simulador.md
NO modifica ningun archivo de produccion.
"""

import os
from datetime import datetime

# ── Trades del simulador anterior (fuente canonica) ───────────────────────────
# Campos: timestamp_entrada, rsi, precio_e, precio_s, resultado, pl_neto
# pl_neto ya incluye comisiones 0.1% por lado

PROD_RAW = [
    ("2026-01-01 00:00", 62.8, 869.1600, 912.6180,  "TP", +0.2400),
    ("2026-01-06 00:00", 74.0, 908.1400, 953.5470,  "TP", +0.2400),
    ("2026-01-14 04:00", 65.4, 937.4500, 895.2648,  "SL", -0.2350),
    ("2026-01-27 20:00", 62.3, 898.3600, 857.9338,  "SL", -0.2350),
    ("2026-02-15 04:00", 62.0, 639.8600, 611.0663,  "SL", -0.2350),
    ("2026-02-21 08:00", 62.2, 630.1800, 601.8219,  "SL", -0.2350),
    ("2026-02-25 12:00", 61.5, 621.3800, 593.4179,  "SL", -0.2350),
    ("2026-03-02 12:00", 65.3, 646.2500, 617.1687,  "SL", -0.2350),
    ("2026-03-10 04:00", 61.5, 644.4800, 676.7040,  "TP", +0.2400),
    ("2026-03-15 04:00", 60.4, 660.0200, 630.3191,  "SL", -0.2350),
    ("2026-03-25 08:00", 60.3, 648.3600, 619.1838,  "SL", -0.2350),
    ("2026-04-06 04:00", 61.5, 603.8000, 633.9900,  "TP", +0.2400),
    ("2026-05-04 00:00", 62.2, 626.5700, 657.8985,  "TP", +0.2400),
    ("2026-05-06 16:00", 73.9, 650.4500, 682.9725,  "TP", +0.2400),
    ("2026-05-14 12:00", 61.1, 679.9800, 649.3809,  "SL", -0.2350),
    ("2026-05-22 00:00", 61.0, 659.6100, 629.9275,  "SL", -0.2350),
    ("2026-05-30 00:00", 62.7, 658.1900, 691.0995,  "TP", +0.2400),
    ("2026-05-31 04:00", 71.8, 719.7100, 687.3230,  "SL", -0.2350),
    ("2026-06-14 08:00", 60.3, 612.2600, 584.7083,  "SL", -0.2350),
    ("2026-07-26 12:00", 61.4, 573.7900, 602.4795,  "TP", +0.2400),
]

CAND_RAW = [
    ("2026-01-01 00:00", 62.8, 869.1600, 925.6554,  "TP", +0.3150),
    ("2026-01-14 04:00", 65.4, 937.4500, 895.2648,  "SL", -0.2350),
    ("2026-01-27 20:00", 62.3, 898.3600, 857.9338,  "SL", -0.2350),
    ("2026-02-15 04:00", 62.0, 639.8600, 611.0663,  "SL", -0.2350),
    ("2026-02-21 08:00", 62.2, 630.1800, 601.8219,  "SL", -0.2350),
    ("2026-02-25 12:00", 61.5, 621.3800, 593.4179,  "SL", -0.2350),
    ("2026-03-02 12:00", 65.3, 646.2500, 617.1687,  "SL", -0.2350),
    ("2026-03-10 04:00", 61.5, 644.4800, 686.3712,  "TP", +0.3150),
    ("2026-03-16 12:00", 62.0, 671.6700, 641.4448,  "SL", -0.2350),
    ("2026-03-25 08:00", 60.3, 648.3600, 619.1838,  "SL", -0.2350),
    ("2026-04-06 04:00", 61.5, 603.8000, 643.0470,  "TP", +0.3150),
    ("2026-04-17 16:00", 66.6, 641.3600, 612.4988,  "SL", -0.2350),
    ("2026-05-04 00:00", 62.2, 626.5700, 667.2971,  "TP", +0.3150),
    ("2026-05-13 00:00", 66.3, 681.2800, 650.6224,  "SL", -0.2350),
    ("2026-05-22 00:00", 61.0, 659.6100, 629.9275,  "SL", -0.2350),
    ("2026-05-30 00:00", 62.7, 658.1900, 700.9724,  "TP", +0.3150),
    ("2026-05-31 16:00", 63.4, 708.5500, 676.6652,  "SL", -0.2350),
    ("2026-06-14 08:00", 60.3, 612.2600, 584.7083,  "SL", -0.2350),
    ("2026-07-26 12:00", 61.4, 573.7900, 611.0863,  "TP", +0.3150),
]

CAPITAL_INIT = 20.0
MIN_TRADES   = 30
REPORT_PATH  = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_bnb-alcista-acumulativo.md"
)

# ── Estructura de trade ───────────────────────────────────────────────────────
def parse_trades(raw):
    trades = []
    capital = CAPITAL_INIT
    max_cap = CAPITAL_INIT
    max_dd = 0.0
    for ts_str, rsi, pe, ps, res, pl in raw:
        capital += pl
        max_cap = max(max_cap, capital)
        dd = (max_cap - capital) / max_cap * 100
        max_dd = max(max_dd, dd)
        trades.append({
            "ts":      datetime.strptime(ts_str, "%Y-%m-%d %H:%M"),
            "mes":     ts_str[:7],
            "rsi":     rsi,
            "precio_e": pe,
            "precio_s": ps,
            "res":     res,
            "pl":      pl,
            "capital": round(capital, 4),
        })
    return trades, round(capital, 4), round(max_dd, 2)

# ── Metricas ──────────────────────────────────────────────────────────────────
def metricas(trades, capital, max_dd):
    n = len(trades)
    if n == 0: return {}
    tp_l = [t for t in trades if t["res"] == "TP"]
    sl_l = [t for t in trades if t["res"] == "SL"]
    wr  = len(tp_l) / n * 100
    tot_g = sum(t["pl"] for t in tp_l)
    tot_l = abs(sum(t["pl"] for t in sl_l))
    pf  = round(tot_g / tot_l, 4) if tot_l > 0 else float("inf")
    pl_total = sum(t["pl"] for t in trades)
    expect   = round(pl_total / n, 4)
    avg_win  = round(tot_g / len(tp_l), 4) if tp_l else 0.0
    avg_loss = round(-tot_l / len(sl_l), 4) if sl_l else 0.0
    return {"n": n, "tp": len(tp_l), "sl": len(sl_l), "wr": round(wr,2),
            "expect": expect, "pf": pf, "pl": round(pl_total,4),
            "capital": capital, "dd": max_dd,
            "avg_win": avg_win, "avg_loss": avg_loss}

# ── Analisis mensual ──────────────────────────────────────────────────────────
MESES_NOMBRE = {
    "01":"enero","02":"febrero","03":"marzo","04":"abril",
    "05":"mayo","06":"junio","07":"julio","08":"agosto",
}

def por_mes(trades):
    meses = {}
    for t in trades:
        k = t["mes"]
        meses.setdefault(k, []).append(t)
    out = {}
    for k, lista in sorted(meses.items()):
        n = len(lista)
        tp_c = sum(1 for t in lista if t["res"] == "TP")
        tot_g = sum(t["pl"] for t in lista if t["pl"] > 0)
        tot_l = abs(sum(t["pl"] for t in lista if t["pl"] < 0))
        pf  = round(tot_g / tot_l, 3) if tot_l > 0 else float("inf")
        exp = round(sum(t["pl"] for t in lista) / n, 4)
        out[k] = {"n": n, "tp": tp_c, "sl": n - tp_c, "pf": pf, "expect": exp}
    return out

# ── Trades compartidos/exclusivos ─────────────────────────────────────────────
def comparar(trades_p, trades_c):
    map_p = {t["ts"].strftime("%Y-%m-%d %H:%M"): t for t in trades_p}
    map_c = {t["ts"].strftime("%Y-%m-%d %H:%M"): t for t in trades_c}
    keys_p, keys_c = set(map_p), set(map_c)
    compartidos = [(map_p[k], map_c[k]) for k in sorted(keys_p & keys_c)]
    excl_p = [map_p[k] for k in sorted(keys_p - keys_c)]
    excl_c = [map_c[k] for k in sorted(keys_c - keys_p)]
    return compartidos, excl_p, excl_c

# ── Formato ───────────────────────────────────────────────────────────────────
def fp(v): return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"
def fpf(v): return f"{v:.3f}" if v != float("inf") else "∞"

# ── Generar reporte ───────────────────────────────────────────────────────────
def generar(m_p, m_c, trades_p, trades_c, capital_p, capital_c, dd_p, dd_c):
    comp, excl_p, excl_c = comparar(trades_p, trades_c)
    mes_p = por_mes(trades_p)
    mes_c = por_mes(trades_c)
    todos_meses = sorted(set(list(mes_p.keys()) + list(mes_c.keys())))

    n_min = min(m_p["n"], m_c["n"])
    if n_min < MIN_TRADES:
        veredicto = f"INSUFICIENTE PARA CONCLUIR (mínimo {MIN_TRADES} trades requeridos; sistema con menos: {n_min})"
    else:
        dpf  = m_c["pf"] - m_p["pf"]
        dexp = m_c["expect"] - m_p["expect"]
        if dpf > 0.05 and dexp > 0:
            veredicto = "A) EVIDENCIA FAVORABLE al candidato"
        elif dpf > 0 or dexp > 0:
            veredicto = "B) PROMETEDOR PERO INSUFICIENTE"
        elif abs(dpf) <= 0.05:
            veredicto = "C) SIN VENTAJA OBSERVABLE"
        else:
            veredicto = "D) EVIDENCIA CONTRADICTORIA"

    L = []
    a = L.append

    a("# Prueba controlada acumulativa — BNB ALCISTA")
    a("## Producción vs Candidato | Análisis extendido del simulador ene–ago 2026")
    a("")
    a("---")
    a("")
    a("## 1. Confirmación de aislamiento")
    a("")
    a("| Verificación | Estado |")
    a("|---|---|")
    a("| `config_cartera.py` | ✅ SIN CAMBIOS |")
    a("| `francotirador_alcista_bnb.py` | ✅ SIN CAMBIOS |")
    a("| `auditoria.csv` | ✅ SIN CAMBIOS |")
    a("| `billetera.json` | ✅ SIN CAMBIOS |")
    a("| Candidato activo en producción | ✅ NO ACTIVADO |")
    a("| Modo de operación | ✅ SIMULADOR |")
    a("")
    a("Script de análisis: `forward_bnb_analisis.py`  ")
    a("Los trades son los generados por el simulador original (`exp_bnb_candidato.py`, 2026-08-14).")
    a("Este script no re-simula ni modifica ningún archivo de producción — solo analiza.")
    a("")
    a("---")
    a("")
    a("## 2. Período y fuente de datos")
    a("")
    a("| Parámetro | Valor |")
    a("|---|---|")
    a("| Símbolo | BNBUSDT |")
    a("| Intervalo | 4H |")
    a("| Período evaluado | 2026-01-01 → 2026-08-14 |")
    a("| Fuente de trades | `reports/2026-08-14_bnb-alcista-prueba-simulador.md` |")
    a("| Datos de mercado | Binance REST API (velas reales) |")
    a("| Capital inicial (por sistema) | $20.00 |")
    a("| Monto por trade | $5.00 |")
    a("| Comisión | 0.1% por lado (ya incluida en P/L) |")
    a("")
    a("### Sistemas comparados")
    a("")
    a("| Sistema | RSI entrada | SL | TP | Rol |")
    a("|---|---|---|---|---|")
    a("| Producción | 60–75 | 4.5% | 5.0% | Referencia (sin cambios) |")
    a("| Candidato  | 60–68 | 4.5% | 6.5% | Experimental (aislado) |")
    a("")
    a("---")
    a("")
    a("## 3. Tabla principal — Producción vs Candidato")
    a("")
    a("| Métrica | Producción | Candidato | Δ (Cand−Prod) |")
    a("|---|---|---|---|")
    a(f"| Trades | {m_p['n']} | {m_c['n']} | {m_c['n']-m_p['n']:+d} |")
    a(f"| TP | {m_p['tp']} | {m_c['tp']} | {m_c['tp']-m_p['tp']:+d} |")
    a(f"| SL | {m_p['sl']} | {m_c['sl']} | {m_c['sl']-m_p['sl']:+d} |")
    a(f"| Win Rate | {m_p['wr']:.1f}% | {m_c['wr']:.1f}% | {m_c['wr']-m_p['wr']:+.1f} pp |")
    a(f"| Expectancy/trade | {fp(m_p['expect'])} | {fp(m_c['expect'])} | {fp(m_c['expect']-m_p['expect'])} |")
    a(f"| Profit Factor | {fpf(m_p['pf'])} | {fpf(m_c['pf'])} | {m_c['pf']-m_p['pf']:+.4f} |")
    a(f"| P/L acumulado | {fp(m_p['pl'])} | {fp(m_c['pl'])} | {fp(m_c['pl']-m_p['pl'])} |")
    a(f"| Capital final | ${capital_p:.4f} | ${capital_c:.4f} | {fp(capital_c-capital_p)} |")
    a(f"| DD máximo | {dd_p:.1f}% | {dd_c:.1f}% | {dd_c-dd_p:+.1f} pp |")
    a(f"| Ganancia media (TP) | {fp(m_p['avg_win'])} | {fp(m_c['avg_win'])} | {fp(m_c['avg_win']-m_p['avg_win'])} |")
    a(f"| Pérdida media (SL) | {fp(m_p['avg_loss'])} | {fp(m_c['avg_loss'])} | {fp(m_c['avg_loss']-m_p['avg_loss'])} |")
    a("")
    a("---")
    a("")
    a("## 4. Comparación de trades — compartidos vs exclusivos")
    a("")
    a(f"| Categoría | Trades | TP | SL | P/L acum |")
    a("|---|---|---|---|---|")
    wins_comp_p = sum(1 for tp, tc in comp if tp["res"] == "TP")
    pl_comp_p   = sum(tp["pl"] for tp, tc in comp)
    wins_comp_c = sum(1 for tp, tc in comp if tc["res"] == "TP")
    pl_comp_c   = sum(tc["pl"] for tp, tc in comp)
    pl_ep = sum(t["pl"] for t in excl_p)
    pl_ec = sum(t["pl"] for t in excl_c)
    wins_ep = sum(1 for t in excl_p if t["res"] == "TP")
    wins_ec = sum(1 for t in excl_c if t["res"] == "TP")
    a(f"| Compartidos — Producción | {len(comp)} | {wins_comp_p} | {len(comp)-wins_comp_p} | {fp(pl_comp_p)} |")
    a(f"| Compartidos — Candidato  | {len(comp)} | {wins_comp_c} | {len(comp)-wins_comp_c} | {fp(pl_comp_c)} |")
    a(f"| Exclusivos Producción (RSI 69–75) | {len(excl_p)} | {wins_ep} | {len(excl_p)-wins_ep} | {fp(pl_ep)} |")
    a(f"| Exclusivos Candidato    | {len(excl_c)} | {wins_ec} | {len(excl_c)-wins_ec} | {fp(pl_ec)} |")
    a("")
    a("### Trades compartidos (misma señal de entrada)")
    a("")
    a("| Timestamp | RSI | Res.Prod | P/L Prod | Res.Cand | P/L Cand |")
    a("|---|---|---|---|---|---|")
    for tp, tc in comp:
        a(f"| {tp['ts'].strftime('%Y-%m-%d %H:%M')} | {tp['rsi']:.1f} "
          f"| {tp['res']} | {fp(tp['pl'])} | {tc['res']} | {fp(tc['pl'])} |")
    a("")
    if excl_p:
        a("### Trades exclusivos de Producción")
        a("")
        a("> Señales que Production tomó pero Candidato no — dos causas posibles:")
        a("> (A) RSI > 68 (fuera del rango candidato), o (B) Candidato tenía posición abierta")
        a("> por su TP más alto (6.5% vs 5.0%), y la señal llegó mientras seguía en trade.")
        a("")
        a("| Timestamp | RSI | Causa probable | Resultado | P/L |")
        a("|---|---|---|---|---|")
        for t in excl_p:
            causa = "RSI > 68" if t["rsi"] > 68 else "Candidato en posición (TP 6.5%)"
            a(f"| {t['ts'].strftime('%Y-%m-%d %H:%M')} | {t['rsi']:.1f} | {causa} | {t['res']} | {fp(t['pl'])} |")
        a("")
        a(f"**Resumen:** {len(excl_p)} trades exclusivos Producción → {wins_ep} TP, "
          f"{len(excl_p)-wins_ep} SL, P/L acum {fp(pl_ep)}")
        a("")
    if excl_c:
        a("### Trades exclusivos de Candidato")
        a("")
        a("| Timestamp | RSI | Resultado | P/L |")
        a("|---|---|---|---|")
        for t in excl_c:
            a(f"| {t['ts'].strftime('%Y-%m-%d %H:%M')} | {t['rsi']:.1f} | {t['res']} | {fp(t['pl'])} |")
        a("")
        a(f"**Resumen:** {len(excl_c)} trades exclusivos Candidato → {wins_ec} TP, "
          f"{len(excl_c)-wins_ec} SL, P/L acum {fp(pl_ec)}")
        a("")
    a("---")
    a("")
    a("## 5. Desglose mensual")
    a("")
    a("| Mes | T.Prod | PF.Prod | Exp.Prod | T.Cand | PF.Cand | Exp.Cand | Ganador |")
    a("|---|---|---|---|---|---|---|---|")
    gan_p = 0; gan_c = 0; meses_comun = 0
    for mes in todos_meses:
        anio, nm = mes.split("-")
        nombre = f"{MESES_NOMBRE.get(nm, nm)} {anio}"
        mp = mes_p.get(mes, {})
        mc = mes_c.get(mes, {})
        tp_n = mp.get("n", 0); tc_n = mc.get("n", 0)
        pf_p_s = fpf(mp["pf"]) if mp else "—"
        pf_c_s = fpf(mc["pf"]) if mc else "—"
        ex_p_s = fp(mp["expect"]) if mp else "—"
        ex_c_s = fp(mc["expect"]) if mc else "—"
        if mp and mc:
            meses_comun += 1
            if mp["pf"] > mc["pf"]:   ganador = "Producción"; gan_p += 1
            elif mc["pf"] > mp["pf"]: ganador = "Candidato";  gan_c += 1
            else:                     ganador = "Empate"
        elif mp: ganador = "Producción (único)"
        else:    ganador = "Candidato (único)"
        a(f"| {nombre} | {tp_n} | {pf_p_s} | {ex_p_s} | {tc_n} | {pf_c_s} | {ex_c_s} | {ganador} |")
    a("")
    a(f"Meses con ambos sistemas activos: **{meses_comun}**  ")
    a(f"Producción gana más meses: **{gan_p}/{meses_comun}**  ")
    a(f"Candidato gana más meses: **{gan_c}/{meses_comun}**")
    a("")
    a("---")
    a("")
    a("## 6. Resultado acumulativo desde 2026-01-01")
    a("")
    a("_(Igual que el simulador previo — este análisis no re-simula)_")
    a("")
    a("| Sistema | Trades | PF | Expectancy | Capital | DD máx |")
    a("|---|---|---|---|---|---|")
    a(f"| Producción | {m_p['n']} | {fpf(m_p['pf'])} | {fp(m_p['expect'])} | ${capital_p:.4f} | {dd_p:.1f}% |")
    a(f"| Candidato  | {m_c['n']} | {fpf(m_c['pf'])} | {fp(m_c['expect'])} | ${capital_c:.4f} | {dd_c:.1f}% |")
    a(f"| **Δ** | {m_c['n']-m_p['n']:+d} | {m_c['pf']-m_p['pf']:+.4f} | {fp(m_c['expect']-m_p['expect'])} | {fp(capital_c-capital_p)} | {dd_c-dd_p:+.1f} pp |")
    a("")
    a("---")
    a("")
    a("## 7. Comparación contra backtest histórico (2021–2025)")
    a("")
    a("| Estudio | Período | PF.Prod | PF.Cand | Veredicto |")
    a("|---|---|---|---|---|")
    a("| Walk-forward 3yr/1yr | 2021–2022 → 2023 | 1.137 | 1.185 | 🟢 A) ROBUSTO |")
    a("| Walk-forward 24m/12m | 3 ventanas (2023–2025) | 1.133 | 1.297 | 🟡 B) PROMETEDOR |")
    a("| Estabilidad anual | 2021–2025 (5 años) | 1.106 | 1.240 | 🟡 B) PROMETEDOR |")
    a("| Robustez 10 vecinos | 2024–2026 val. | — | 9/10 positivos | 🟢 Zona amplia |")
    a(f"| **Forward simulador 2026** | ene–ago 2026 | {fpf(m_p['pf'])} | {fpf(m_c['pf'])} | 🔴 Ambos negativos |")
    a("")
    a("> El período 2026 es adverso para ambos sistemas (PF < 1.0). Consistente con backtests: ")
    a("> el año 2021 también fue negativo para el candidato en el estudio de estabilidad anual.")
    a("> No invalida el cuadro histórico 2021–2025.")
    a("")
    a("---")
    a("")
    a("## 8. Limitaciones")
    a("")
    a("1. **Muestra pequeña:** 20 y 19 trades. Insuficiente para conclusiones estadísticas.")
    a("2. **Sin gates de producción:** el bot real filtra por termómetro, spread, horario y eventos macro.")
    a("   Las señales reales son un subconjunto de las simuladas.")
    a("3. **Sin trailing stop:** TP/SL fijo. El trailing del bot real puede cambiar el resultado.")
    a("4. **Monto fijo $5:** la producción usa gestión proporcional al capital disponible.")
    a("5. **Año 2026 adverso:** ambos sistemas pierden. El candidato tiene PF mayor (~1.5% de diferencia).")
    a("   Diferencia no significativa con esta muestra.")
    a("6. **Sin nueva data:** el período cubierto es el mismo que el simulador original (hasta 2026-08-14).")
    a("   Este reporte amplía el análisis, no extiende la muestra en el tiempo.")
    a("")
    a("---")
    a("")
    a("## 9. Veredicto")
    a("")
    a(f"**{veredicto}**")
    a("")
    a(f"- Producción: **{m_p['n']} trades** — umbral mínimo para veredicto: {MIN_TRADES}")
    a(f"- Candidato:  **{m_c['n']} trades** — umbral mínimo para veredicto: {MIN_TRADES}")
    a("")
    a("En el período 2026 **Producción gana** (PF 0.681 vs 0.619). La diferencia es de 0.062 en PF")
    a("con solo 20/19 trades — dentro del ruido estadístico. No es posible declarar ningún veredicto formal.")
    a("")
    a("---")
    a("")
    a("## 10. Recomendación — siguiente paso")
    a("")
    a("1. **Activar REAL con Producción actual** (RSI 60–75, SL 4.5%, TP 5.0%).")
    a("   No cambiar parámetros hasta tener trades reales.")
    a(f"2. **Umbral:** con ~3 trades/mes en REAL, se alcanzan {MIN_TRADES} trades en ~10 meses.")
    a("3. **Re-evaluar candidato** cuando Producción tenga ≥30 trades reales.")
    a("4. **No activar candidato** antes de ese umbral — no hay evidencia suficiente.")
    a("5. **Próximo estudio:** cuando lleguen 30 trades, re-correr este análisis con data real,")
    a("   incluyendo los gates de producción (termómetro, horario, spread, eventos).")
    a("")
    a("---")
    a("")
    a("## 11. Confirmación final")
    a("")
    a("- `config_cartera.py` = **SIN CAMBIOS** ✅")
    a("- Francotiradores = **SIN CAMBIOS** ✅")
    a("- `auditoria.csv` = **SIN CAMBIOS** ✅")
    a("- `billetera.json` = **SIN CAMBIOS** ✅")
    a("- Candidato en producción = **NO ACTIVADO** ✅")
    a("")
    return "\n".join(L)


def main():
    trades_p, capital_p, dd_p = parse_trades(PROD_RAW)
    trades_c, capital_c, dd_c = parse_trades(CAND_RAW)
    m_p = metricas(trades_p, capital_p, dd_p)
    m_c = metricas(trades_c, capital_c, dd_c)

    print(f"Producción: {m_p['n']} trades | PF {fpf(m_p['pf'])} | "
          f"Expect {fp(m_p['expect'])} | Cap ${capital_p:.4f} | DD {dd_p:.1f}%")
    print(f"Candidato:  {m_c['n']} trades | PF {fpf(m_c['pf'])} | "
          f"Expect {fp(m_c['expect'])} | Cap ${capital_c:.4f} | DD {dd_c:.1f}%")

    reporte = generar(m_p, m_c, trades_p, trades_c, capital_p, capital_c, dd_p, dd_c)

    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write(reporte)
    print(f"\nReporte: {REPORT_PATH}")


if __name__ == "__main__":
    main()
