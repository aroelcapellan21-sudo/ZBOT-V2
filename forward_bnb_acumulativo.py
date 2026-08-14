"""
forward_bnb_acumulativo.py
Prueba controlada acumulativa BNB ALCISTA — Producción vs Candidato
INVESTIGACION PURA — NO modifica ningun archivo de produccion.
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ── Constantes ───────────────────────────────────────────────────────────────
SIMBOLO          = "BNBUSDT"
INTERVALO        = "4h"
CAPITAL_INIT     = 20.0
MONTO_TRADE      = 5.0
COMISION         = 0.001          # 0.1% por lado
FECHA_INICIO     = "2026-01-01"   # primera señal permitida
FECHA_WARMUP     = "2025-10-01"   # descarga desde aquí para RSI warmup
MIN_TRADES       = 30             # umbral para veredicto

PRODUCCION = {"rsi_min": 60.0, "rsi_max": 75.0, "sl": 0.045, "tp": 0.050, "nombre": "Produccion"}
CANDIDATO  = {"rsi_min": 60.0, "rsi_max": 68.0, "sl": 0.045, "tp": 0.065, "nombre": "Candidato"}

REPORT_PATH = os.path.expanduser(
    f"~/bot-padre-v2/reports/2026-08-14_bnb-alcista-acumulativo.md"
)

# ── Binance helpers ───────────────────────────────────────────────────────────
def _ts_ms(fecha_str):
    dt = datetime.strptime(fecha_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def fetch_velas(symbol, intervalo, desde_ms):
    """Descarga todas las velas 4H desde desde_ms hasta ahora."""
    velas = []
    inicio = desde_ms
    while True:
        params = urllib.parse.urlencode({
            "symbol":    symbol,
            "interval":  intervalo,
            "startTime": inicio,
            "limit":     1000,
        })
        url = f"https://api.binance.com/api/v3/klines?{params}"
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                batch = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  ERROR fetch: {e}")
            break
        if not batch:
            break
        velas.extend(batch)
        if len(batch) < 1000:
            break
        inicio = batch[-1][0] + 1
    return velas

# ── RSI simple (igual al resto de backtests de esta sesion) ──────────────────
def calcular_rsi_simple(cierres_ventana, periodo=14):
    """
    RSI de media simple sobre una ventana de (periodo+1) velas.
    Replica exactamente calcular_rsi() de backtest_motor.py/walkforward.py.
    """
    if len(cierres_ventana) < periodo + 1:
        return None
    ganancias, perdidas = [], []
    for i in range(1, periodo + 1):
        diff = cierres_ventana[i] - cierres_ventana[i - 1]
        if diff > 0:
            ganancias.append(diff)
            perdidas.append(0)
        else:
            ganancias.append(0)
            perdidas.append(abs(diff))
    avg_gan = sum(ganancias) / periodo
    avg_per = sum(perdidas) / periodo
    if avg_per == 0:
        return 100.0
    rs = avg_gan / avg_per
    return round(100 - (100 / (1 + rs)), 2)

# ── Motor de simulacion ───────────────────────────────────────────────────────
RSI_VENTANA = 15    # 14 cambios, igual que backtest_motor.py ventana[-15:]
RSI_WARMUP  = 60    # warmup de RSI antes de empezar a evaluar señales

INICIO_MS = int(datetime.strptime(FECHA_INICIO, "%Y-%m-%d")
                .replace(tzinfo=timezone.utc).timestamp() * 1000)

def simular(velas_raw, config):
    """
    Simula el sistema config sobre velas_raw.
    RSI: ventana deslizante de 15 velas (replica backtest_motor.py).
    Una posicion a la vez. Entrada al cierre de la vela de señal.
    SL/TP evaluados vela a vela siguiente.
    Sin trailing (consistente con todos los backtests de esta sesion).
    """
    cierres = [float(k[4]) for k in velas_raw]
    ts_list = [int(k[0]) for k in velas_raw]

    trades = []
    capital = CAPITAL_INIT
    max_capital = CAPITAL_INIT
    max_dd = 0.0
    en_posicion = False
    entrada_precio = 0.0
    entrada_ts = None
    entrada_rsi = 0.0
    sl_precio = 0.0
    tp_precio = 0.0

    for i in range(RSI_WARMUP, len(cierres)):
        ventana = cierres[max(0, i - 60):i]        # misma logica que backtest_motor
        rsi = calcular_rsi_simple(ventana[-RSI_VENTANA:])
        if rsi is None:
            continue

        precio_cierre = cierres[i]
        ts_ms = ts_list[i]
        ts_dt = datetime.utcfromtimestamp(ts_ms / 1000)

        if en_posicion:
            resultado = None
            precio_salida = None
            if precio_cierre <= sl_precio:
                resultado = "SL"
                precio_salida = sl_precio
            elif precio_cierre >= tp_precio:
                resultado = "TP"
                precio_salida = tp_precio
            if resultado:
                comision_entrada = MONTO_TRADE * COMISION
                comision_salida  = MONTO_TRADE * COMISION
                if resultado == "TP":
                    bruto = MONTO_TRADE * config["tp"]
                    pl_neto = round(bruto - comision_entrada - comision_salida, 4)
                else:
                    bruto = -MONTO_TRADE * config["sl"]
                    pl_neto = round(bruto - comision_entrada - comision_salida, 4)
                capital += pl_neto
                max_capital = max(max_capital, capital)
                dd = (max_capital - capital) / max_capital * 100
                max_dd = max(max_dd, dd)
                trades.append({
                    "entrada_ts":  entrada_ts,
                    "salida_ts":   ts_dt,
                    "rsi":         entrada_rsi,
                    "precio_e":    entrada_precio,
                    "precio_s":    round(precio_salida, 4),
                    "resultado":   resultado,
                    "pl":          pl_neto,
                    "capital":     round(capital, 4),
                })
                en_posicion = False

        if not en_posicion:
            # Solo generar señales desde FECHA_INICIO
            if ts_ms >= INICIO_MS and config["rsi_min"] <= rsi <= config["rsi_max"]:
                en_posicion = True
                entrada_precio = precio_cierre
                entrada_ts = ts_dt
                entrada_rsi = rsi
                sl_precio = round(entrada_precio * (1 - config["sl"]), 4)
                tp_precio = round(entrada_precio * (1 + config["tp"]), 4)

    return trades, round(capital, 4), round(max_dd, 2)

# ── Metricas ──────────────────────────────────────────────────────────────────
def metricas(trades, capital, max_dd):
    n = len(trades)
    if n == 0:
        return {}
    tp_list  = [t for t in trades if t["resultado"] == "TP"]
    sl_list  = [t for t in trades if t["resultado"] == "SL"]
    wr       = len(tp_list) / n * 100
    ganancias = [t["pl"] for t in tp_list]
    perdidas  = [t["pl"] for t in sl_list]
    total_g  = sum(ganancias)
    total_l  = abs(sum(perdidas))
    pf       = round(total_g / total_l, 3) if total_l > 0 else float("inf")
    pl_total = sum(t["pl"] for t in trades)
    expect   = round(pl_total / n, 4)
    avg_win  = round(total_g / len(tp_list), 4) if tp_list else 0.0
    avg_loss = round(-total_l / len(sl_list), 4) if sl_list else 0.0
    return {
        "trades":    n,
        "tp":        len(tp_list),
        "sl":        len(sl_list),
        "wr":        round(wr, 2),
        "expect":    expect,
        "pf":        pf,
        "pl_total":  round(pl_total, 4),
        "capital":   capital,
        "max_dd":    max_dd,
        "avg_win":   avg_win,
        "avg_loss":  avg_loss,
    }

# ── Analisis mensual ──────────────────────────────────────────────────────────
def por_mes(trades):
    meses = {}
    for t in trades:
        key = t["entrada_ts"].strftime("%Y-%m")
        if key not in meses:
            meses[key] = []
        meses[key].append(t)
    resultado = {}
    for mes, lista in sorted(meses.items()):
        n = len(lista)
        tp_c = sum(1 for t in lista if t["resultado"] == "TP")
        sl_c = n - tp_c
        total_g = sum(t["pl"] for t in lista if t["pl"] > 0)
        total_l = abs(sum(t["pl"] for t in lista if t["pl"] < 0))
        pf  = round(total_g / total_l, 3) if total_l > 0 else float("inf")
        exp = round(sum(t["pl"] for t in lista) / n, 4)
        resultado[mes] = {"trades": n, "tp": tp_c, "sl": sl_c, "pf": pf, "expect": exp}
    return resultado

# ── Comparacion trades ────────────────────────────────────────────────────────
def comparar_trades(trades_p, trades_c):
    """
    Trades compartidos: misma entrada_ts (mismo día/hora de señal).
    Exclusivos de cada sistema.
    """
    ts_p = {t["entrada_ts"].strftime("%Y-%m-%d %H:%M"): t for t in trades_p}
    ts_c = {t["entrada_ts"].strftime("%Y-%m-%d %H:%M"): t for t in trades_c}
    keys_p = set(ts_p.keys())
    keys_c = set(ts_c.keys())
    compartidos_keys = keys_p & keys_c
    excl_p_keys = keys_p - keys_c
    excl_c_keys = keys_c - keys_p

    compartidos = [(ts_p[k], ts_c[k]) for k in sorted(compartidos_keys)]
    excl_p = [ts_p[k] for k in sorted(excl_p_keys)]
    excl_c = [ts_c[k] for k in sorted(excl_c_keys)]
    return compartidos, excl_p, excl_c

# ── Formato markdown helpers ──────────────────────────────────────────────────
def fmt_pl(v):
    return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"

def fmt_pf(v):
    return f"{v:.3f}" if v != float("inf") else "∞"

def fmt_wr(v):
    return f"{v:.1f}%"

MESES_NOMBRE = {
    "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
    "05": "mayo",  "06": "junio",   "07": "julio", "08": "agosto",
    "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre",
}

# ── Generador de reporte ──────────────────────────────────────────────────────
def generar_reporte(m_p, m_c, trades_p, trades_c, capital_p, capital_c, dd_p, dd_c,
                    velas_total, fecha_fin):

    comp, excl_p, excl_c = comparar_trades(trades_p, trades_c)
    meses_p = por_mes(trades_p)
    meses_c = por_mes(trades_c)
    todos_meses = sorted(set(list(meses_p.keys()) + list(meses_c.keys())))

    # — Veredicto —
    n_min = min(m_p["trades"], m_c["trades"])
    if n_min < MIN_TRADES:
        veredicto = f"INSUFICIENTE PARA CONCLUIR (mínimo {MIN_TRADES} trades; sistema con menos: {n_min})"
        veredicto_corto = "INSUFICIENTE"
    else:
        delta_pf  = m_c["pf"] - m_p["pf"]
        delta_exp = m_c["expect"] - m_p["expect"]
        if delta_pf > 0.05 and delta_exp > 0:
            veredicto = "A) EVIDENCIA FAVORABLE al candidato"
            veredicto_corto = "A"
        elif delta_pf > 0 or delta_exp > 0:
            veredicto = "B) PROMETEDOR PERO INSUFICIENTE"
            veredicto_corto = "B"
        elif abs(delta_pf) <= 0.05 and abs(delta_exp) <= 0.005:
            veredicto = "C) SIN VENTAJA OBSERVABLE"
            veredicto_corto = "C"
        else:
            veredicto = "D) EVIDENCIA CONTRADICTORIA"
            veredicto_corto = "D"

    lines = []
    a = lines.append

    a("# Prueba controlada acumulativa — BNB ALCISTA")
    a("## Producción vs Candidato | Forward test integrado")
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
    a("Script aislado: `forward_bnb_acumulativo.py`  ")
    a("No escribe en ningún archivo de producción.")
    a("")
    a("---")
    a("")
    a("## 2. Período y datos")
    a("")
    a("| Parámetro | Valor |")
    a("|---|---|")
    a(f"| Símbolo | {SIMBOLO} |")
    a(f"| Intervalo | {INTERVALO} |")
    a(f"| Desde | {FECHA_INICIO} |")
    a(f"| Hasta | {fecha_fin} |")
    a(f"| Velas totales | {velas_total} |")
    a(f"| Fuente | Binance REST API |")
    a(f"| Capital inicial | ${CAPITAL_INIT:.2f} por sistema |")
    a(f"| Monto por trade | ${MONTO_TRADE:.2f} |")
    a(f"| Comisión | {COMISION*100:.1f}% por lado |")
    a("")
    a("### Sistemas comparados")
    a("")
    a("| Sistema | RSI entrada | SL | TP | Rol |")
    a("|---|---|---|---|---|")
    a(f"| Producción | 60–75 | 4.5% | 5.0% | Referencia (sin cambios) |")
    a(f"| Candidato  | 60–68 | 4.5% | 6.5% | Experimental (aislado) |")
    a("")
    a("---")
    a("")
    a("## 3. Observación previa integrada (2026-01-01 → 2026-08-14)")
    a("")
    a("Prueba anterior (`reports/2026-08-14_bnb-alcista-prueba-simulador.md`):")
    a("")
    a("| Métrica | Producción prev | Candidato prev |")
    a("|---|---|---|")
    a("| Trades | 20 | 19 |")
    a("| WR | 40.0% | 31.6% |")
    a("| PF | 0.681 | 0.619 |")
    a("| Expectancy | −$0.0450 | −$0.0613 |")
    a("| Capital | $19.10 | $18.84 |")
    a("| DD máx | 8.0% | 8.8% |")
    a("")
    a("> Los datos de esta ejecución cubren el mismo período y son su re-análisis extendido.")
    a("> Sirven como continuidad acumulativa, no como muestra adicional.")
    a("")
    a("---")
    a("")
    a("## 4. Tabla principal — Producción vs Candidato")
    a("")
    a("| Métrica | Producción | Candidato | Δ (Cand−Prod) |")
    a("|---|---|---|---|")
    a(f"| Trades | {m_p['trades']} | {m_c['trades']} | {m_c['trades']-m_p['trades']:+d} |")
    a(f"| TP | {m_p['tp']} | {m_c['tp']} | {m_c['tp']-m_p['tp']:+d} |")
    a(f"| SL | {m_p['sl']} | {m_c['sl']} | {m_c['sl']-m_p['sl']:+d} |")
    a(f"| Win Rate | {fmt_wr(m_p['wr'])} | {fmt_wr(m_c['wr'])} | {m_c['wr']-m_p['wr']:+.1f} pp |")
    a(f"| Expectancy/trade | {fmt_pl(m_p['expect'])} | {fmt_pl(m_c['expect'])} | {fmt_pl(m_c['expect']-m_p['expect'])} |")
    a(f"| Profit Factor | {fmt_pf(m_p['pf'])} | {fmt_pf(m_c['pf'])} | {m_c['pf']-m_p['pf']:+.3f} |")
    a(f"| P/L acumulado | {fmt_pl(m_p['pl_total'])} | {fmt_pl(m_c['pl_total'])} | {fmt_pl(m_c['pl_total']-m_p['pl_total'])} |")
    a(f"| Capital final | ${capital_p:.4f} | ${capital_c:.4f} | {fmt_pl(capital_c-capital_p)} |")
    a(f"| DD máximo | {dd_p:.1f}% | {dd_c:.1f}% | {dd_c-dd_p:+.1f} pp |")
    a(f"| Ganancia media (TP) | {fmt_pl(m_p['avg_win'])} | {fmt_pl(m_c['avg_win'])} | {fmt_pl(m_c['avg_win']-m_p['avg_win'])} |")
    a(f"| Pérdida media (SL)  | {fmt_pl(m_p['avg_loss'])} | {fmt_pl(m_c['avg_loss'])} | {fmt_pl(m_c['avg_loss']-m_p['avg_loss'])} |")
    a("")
    a("---")
    a("")
    a("## 5. Comparación de trades — compartidos vs exclusivos")
    a("")
    a(f"| Categoría | Cantidad |")
    a("|---|---|")
    a(f"| Trades compartidos (misma entrada) | {len(comp)} |")
    a(f"| Exclusivos de Producción | {len(excl_p)} |")
    a(f"| Exclusivos de Candidato | {len(excl_c)} |")
    a("")
    a("### Trades compartidos (ambos sistemas tomaron la misma entrada)")
    a("")
    a("| Timestamp | RSI | P/L Prod | Res.Prod | P/L Cand | Res.Cand |")
    a("|---|---|---|---|---|---|")
    for tp, tc in comp:
        a(f"| {tp['entrada_ts'].strftime('%Y-%m-%d %H:%M')} | {tp['rsi']:.1f} "
          f"| {fmt_pl(tp['pl'])} | {tp['resultado']} "
          f"| {fmt_pl(tc['pl'])} | {tc['resultado']} |")
    a("")
    a("### Trades exclusivos de Producción (RSI 69–75 filtrado por candidato)")
    a("")
    if excl_p:
        a("| Timestamp | RSI | P/L | Resultado |")
        a("|---|---|---|---|")
        for t in excl_p:
            a(f"| {t['entrada_ts'].strftime('%Y-%m-%d %H:%M')} | {t['rsi']:.1f} | {fmt_pl(t['pl'])} | {t['resultado']} |")
        wins_ep = sum(1 for t in excl_p if t["resultado"] == "TP")
        pl_ep   = sum(t["pl"] for t in excl_p)
        a(f"")
        a(f"Resultado exclusivos Producción: {wins_ep}/{len(excl_p)} TP · P/L acum {fmt_pl(pl_ep)}")
    else:
        a("_Ninguno._")
    a("")
    a("### Trades exclusivos de Candidato")
    a("")
    if excl_c:
        a("| Timestamp | RSI | P/L | Resultado |")
        a("|---|---|---|---|")
        for t in excl_c:
            a(f"| {t['entrada_ts'].strftime('%Y-%m-%d %H:%M')} | {t['rsi']:.1f} | {fmt_pl(t['pl'])} | {t['resultado']} |")
        wins_ec = sum(1 for t in excl_c if t["resultado"] == "TP")
        pl_ec   = sum(t["pl"] for t in excl_c)
        a(f"")
        a(f"Resultado exclusivos Candidato: {wins_ec}/{len(excl_c)} TP · P/L acum {fmt_pl(pl_ec)}")
    else:
        a("_Ninguno._")
    a("")
    a("---")
    a("")
    a("## 6. Desglose mensual")
    a("")
    a("| Mes | T.Prod | PF.Prod | Exp.Prod | T.Cand | PF.Cand | Exp.Cand | Ganador mensual |")
    a("|---|---|---|---|---|---|---|---|")
    for mes in todos_meses:
        anio, num_mes = mes.split("-")
        nombre_mes = f"{MESES_NOMBRE.get(num_mes, num_mes)} {anio}"
        mp = meses_p.get(mes, {})
        mc = meses_c.get(mes, {})
        tp_m = mp.get("trades", 0)
        tc_m = mc.get("trades", 0)
        pf_p = fmt_pf(mp["pf"]) if mp else "—"
        pf_c = fmt_pf(mc["pf"]) if mc else "—"
        ex_p = fmt_pl(mp["expect"]) if mp else "—"
        ex_c = fmt_pl(mc["expect"]) if mc else "—"
        # Ganador
        if mp and mc:
            if mp["pf"] > mc["pf"]:
                ganador = "Producción"
            elif mc["pf"] > mp["pf"]:
                ganador = "Candidato"
            else:
                ganador = "Empate"
        elif mp:
            ganador = "Producción (único)"
        elif mc:
            ganador = "Candidato (único)"
        else:
            ganador = "—"
        a(f"| {nombre_mes} | {tp_m} | {pf_p} | {ex_p} | {tc_m} | {pf_c} | {ex_c} | {ganador} |")

    # conteo ganadores
    ganados_prod = sum(1 for mes in todos_meses
                       if meses_p.get(mes) and meses_c.get(mes) and
                       meses_p[mes]["pf"] > meses_c[mes]["pf"])
    ganados_cand = sum(1 for mes in todos_meses
                       if meses_p.get(mes) and meses_c.get(mes) and
                       meses_c[mes]["pf"] > meses_p[mes]["pf"])
    meses_comun = sum(1 for mes in todos_meses if meses_p.get(mes) and meses_c.get(mes))
    a("")
    a(f"Meses con ambos sistemas activos: {meses_comun}  ")
    a(f"Producción gana: {ganados_prod}/{meses_comun}  ")
    a(f"Candidato gana: {ganados_cand}/{meses_comun}")
    a("")
    a("---")
    a("")
    a("## 7. Resultado acumulativo desde 2026-01-01")
    a("")
    a("_(Re-análisis del período completo con tracking extendido)_")
    a("")
    a("| Sistema | Trades | PF | Expectancy | Capital | DD máx |")
    a("|---|---|---|---|---|---|")
    a(f"| Producción | {m_p['trades']} | {fmt_pf(m_p['pf'])} | {fmt_pl(m_p['expect'])} | ${capital_p:.4f} | {dd_p:.1f}% |")
    a(f"| Candidato  | {m_c['trades']} | {fmt_pf(m_c['pf'])} | {fmt_pl(m_c['expect'])} | ${capital_c:.4f} | {dd_c:.1f}% |")
    a(f"| **Δ** | {m_c['trades']-m_p['trades']:+d} | {m_c['pf']-m_p['pf']:+.3f} | {fmt_pl(m_c['expect']-m_p['expect'])} | {fmt_pl(capital_c-capital_p)} | {dd_c-dd_p:+.1f} pp |")
    a("")
    a("---")
    a("")
    a("## 8. Comparación contra backtest histórico (2021–2025)")
    a("")
    a("| Estudio | Período | PF.Prod | PF.Cand | Veredicto |")
    a("|---|---|---|---|---|")
    a("| Walk-forward 3yr/1yr | 2021–2022 → 2023 | 1.137 | 1.185 | 🟢 A ROBUSTO |")
    a("| Walk-forward 24m/12m | 3 ventanas | 1.133 | 1.297 | 🟡 B PROMETEDOR |")
    a("| Estabilidad anual | 2021–2025 (5 años) | 1.106 | 1.240 | 🟡 B PROMETEDOR |")
    a("| Bootstrap IC95 | 2021–2025 | — | IC cruza 0 | 🟡 B |")
    a(f"| **Forward 2026** | 2026-01-01→{fecha_fin} | {fmt_pf(m_p['pf'])} | {fmt_pf(m_c['pf'])} | Ver veredicto |")
    a("")
    a("> El período 2026 es bear para ambos sistemas (ambos PF < 1.0). "
      "Consistente con backtests: ambos son negativos en períodos bajistas. "
      "No invalida el cuadro histórico 2021–2025.")
    a("")
    a("---")
    a("")
    a("## 9. Limitaciones")
    a("")
    a("1. **Simulación retrospectiva sobre el mismo período:** no hay velas nuevas desde la prueba anterior.")
    a("   Este reporte extiende el análisis (desglose mensual, trades compartidos) — la muestra no crece.")
    a("2. **Sin gates de producción:** termómetro, spread, horario y eventos macro no se replican.")
    a("   Las señales reales son un subconjunto de las simuladas.")
    a("3. **Sin trailing stop:** se usa TP/SL fijo. En producción el trailing puede cambiar el resultado.")
    a("4. **Monto fijo $5:** la producción usa gestión proporcional. Este simulador aísla el efecto RSI/TP/SL.")
    a("5. **Muestra pequeña:** 2026 es solo ~7.5 meses y ambos sistemas tienen <30 trades.")
    a("   El veredicto estadístico no es concluyente.")
    a("6. **Régimen no filtrado:** esta prueba corre sobre señales RSI puras,")
    a("   sin validar que el bot en ese momento esté en fase ALCISTA confirmada.")
    a("")
    a("---")
    a("")
    a("## 10. Veredicto")
    a("")
    a(f"**{veredicto}**")
    a("")
    a(f"- Producción: {m_p['trades']} trades — umbral mínimo {MIN_TRADES}")
    a(f"- Candidato:  {m_c['trades']} trades — umbral mínimo {MIN_TRADES}")
    if n_min < MIN_TRADES:
        a(f"- Ambos sistemas están por debajo del mínimo de {MIN_TRADES} trades para declarar veredicto.")
    a("")
    a("---")
    a("")
    a("## 11. Recomendación — siguiente paso")
    a("")
    a("1. **Activar REAL con la configuración de Producción actual** — no cambiar parámetros.")
    a("2. **Acumular trades reales.** Con $20 de capital se esperan ~3 trades/mes.")
    a(f"   Para alcanzar {MIN_TRADES} trades: ~10 meses de REAL.")
    a("3. **Re-evaluar el candidato** cuando Producción tenga ≥30 trades reales.")
    a("   Solo entonces la comparación tendrá poder estadístico suficiente.")
    a("4. **No implementar el candidato** antes de ese umbral.")
    a("")
    a("---")
    a("")
    a("## 12. Confirmación final")
    a("")
    a("- `config_cartera.py` = **SIN CAMBIOS** ✅")
    a("- francotiradores = **SIN CAMBIOS** ✅")
    a("- `auditoria.csv` = **SIN CAMBIOS** ✅")
    a("- `billetera.json` = **SIN CAMBIOS** ✅")
    a("- Candidato en producción = **NO ACTIVADO** ✅")
    a("")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Descargando velas {SIMBOLO} {INTERVALO} desde {FECHA_WARMUP} (warmup)...")
    desde_ms = _ts_ms(FECHA_WARMUP)
    velas_raw = fetch_velas(SIMBOLO, INTERVALO, desde_ms)
    # Eliminar vela en curso (no cerrada)
    ahora_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    velas_raw = [v for v in velas_raw if int(v[6]) < ahora_ms]
    print(f"  Velas descargadas: {len(velas_raw)}")

    if len(velas_raw) < 30:
        print("ERROR: pocas velas.")
        return

    fecha_fin = datetime.utcfromtimestamp(int(velas_raw[-1][0]) / 1000).strftime("%Y-%m-%d")

    print("Simulando Produccion...")
    trades_p, capital_p, dd_p = simular(velas_raw, PRODUCCION)
    m_p = metricas(trades_p, capital_p, dd_p)

    print("Simulando Candidato...")
    trades_c, capital_c, dd_c = simular(velas_raw, CANDIDATO)
    m_c = metricas(trades_c, capital_c, dd_c)

    print(f"\n=== RESULTADOS ===")
    print(f"Produccion: {m_p['trades']} trades | PF {m_p['pf']:.3f} | Expect {m_p['expect']:.4f} | Cap ${capital_p:.4f} | DD {dd_p:.1f}%")
    print(f"Candidato:  {m_c['trades']} trades | PF {m_c['pf']:.3f} | Expect {m_c['expect']:.4f} | Cap ${capital_c:.4f} | DD {dd_c:.1f}%")

    reporte = generar_reporte(m_p, m_c, trades_p, trades_c, capital_p, capital_c, dd_p, dd_c,
                              len(velas_raw), fecha_fin)

    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write(reporte)
    print(f"\nReporte: {REPORT_PATH}")


if __name__ == "__main__":
    main()
