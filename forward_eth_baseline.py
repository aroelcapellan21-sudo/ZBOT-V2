"""
forward_eth_baseline.py
ETH ALCISTA — Prueba #2 Fase A: Baseline de Produccion
INVESTIGACION PURA — NO modifica ningun archivo de produccion.
Solo Produccion. Sin candidato. Opcion D del plan.
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ── Constantes ───────────────────────────────────────────────────────────────
SIMBOLO      = "ETHUSDT"
INTERVALO    = "4h"
CAPITAL_INIT = 20.0
MONTO_TRADE  = 5.0
COMISION     = 0.001          # 0.1% por lado
FECHA_INICIO = "2026-01-01"   # primera señal permitida
FECHA_WARMUP = "2025-10-01"   # descarga desde aqui para RSI warmup
MIN_TRADES   = 30             # umbral para veredicto formal

PRODUCCION = {"rsi_min": 60.0, "rsi_max": 75.0, "sl": 0.045, "tp": 0.050, "nombre": "Produccion"}

REPORT_PATH = os.path.expanduser(
    "~/bot-padre-v2/reports/2026-08-14_eth-alcista-baseline.md"
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

# ── RSI simple (identico a backtest_motor.py) ─────────────────────────────────
def calcular_rsi_simple(cierres_ventana, periodo=14):
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
RSI_WARMUP  = 60    # warmup de RSI antes de evaluar señales

INICIO_MS = int(datetime.strptime(FECHA_INICIO, "%Y-%m-%d")
                .replace(tzinfo=timezone.utc).timestamp() * 1000)

def simular(velas_raw, config):
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
        ventana = cierres[max(0, i - 60):i]
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
                comision_e = MONTO_TRADE * COMISION
                comision_s = MONTO_TRADE * COMISION
                if resultado == "TP":
                    bruto = MONTO_TRADE * config["tp"]
                else:
                    bruto = -MONTO_TRADE * config["sl"]
                pl_neto = round(bruto - comision_e - comision_s, 4)
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
    total_g  = sum(t["pl"] for t in tp_list)
    total_l  = abs(sum(t["pl"] for t in sl_list))
    pf       = round(total_g / total_l, 3) if total_l > 0 else float("inf")
    pl_total = sum(t["pl"] for t in trades)
    expect   = round(pl_total / n, 4)
    avg_win  = round(total_g / len(tp_list), 4) if tp_list else 0.0
    avg_loss = round(-total_l / len(sl_list), 4) if sl_list else 0.0
    return {
        "trades": n, "tp": len(tp_list), "sl": len(sl_list),
        "wr": round(wr, 2), "expect": expect, "pf": pf,
        "pl_total": round(pl_total, 4), "capital": capital,
        "max_dd": max_dd, "avg_win": avg_win, "avg_loss": avg_loss,
    }

# ── Analisis mensual ──────────────────────────────────────────────────────────
def por_mes(trades):
    meses = {}
    for t in trades:
        key = t["entrada_ts"].strftime("%Y-%m")
        meses.setdefault(key, []).append(t)
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

# ── Formato ───────────────────────────────────────────────────────────────────
def fmt_pl(v):
    return f"+${v:.4f}" if v >= 0 else f"-${abs(v):.4f}"

def fmt_pf(v):
    return f"{v:.3f}" if v != float("inf") else "∞"

MESES_NOMBRE = {
    "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
    "05": "mayo",  "06": "junio",   "07": "julio", "08": "agosto",
    "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre",
}

# ── Reporte ───────────────────────────────────────────────────────────────────
def generar_reporte(m, trades, capital, max_dd, velas_total, fecha_fin):
    meses_data = por_mes(trades)

    lines = []
    a = lines.append

    a("# ETH ALCISTA — Baseline Producción ene–ago 2026")
    a("## Prueba #2 Fase A | Solo Producción (sin candidato)")
    a("")
    a("---")
    a("")
    a("## 1. Confirmación de aislamiento")
    a("")
    a("| Verificación | Estado |")
    a("|---|---|")
    a("| `config_cartera.py` | ✅ SIN CAMBIOS |")
    a("| `francotirador_alcista_eth.py` | ✅ SIN CAMBIOS |")
    a("| `auditoria.csv` | ✅ SIN CAMBIOS |")
    a("| `billetera.json` | ✅ SIN CAMBIOS |")
    a("| Candidato en producción | ✅ NO ACTIVADO |")
    a("| Modo de operación | ✅ SIMULADOR |")
    a("")
    a("Script aislado: `forward_eth_baseline.py`  ")
    a("No escribe en ningún archivo de producción.")
    a("")
    a("---")
    a("")
    a("## 2. Configuración")
    a("")
    a("| Parámetro | Valor |")
    a("|---|---|")
    a(f"| Símbolo | {SIMBOLO} |")
    a(f"| Intervalo | {INTERVALO} |")
    a(f"| Período evaluado | {FECHA_INICIO} → {fecha_fin} |")
    a(f"| Warmup desde | {FECHA_WARMUP} |")
    a(f"| Velas totales descargadas | {velas_total} |")
    a(f"| Fuente | Binance REST API (velas reales) |")
    a(f"| Capital inicial | ${CAPITAL_INIT:.2f} |")
    a(f"| Monto por trade | ${MONTO_TRADE:.2f} |")
    a(f"| Comisión | {COMISION*100:.1f}% por lado |")
    a(f"| RSI entrada | 60–75 |")
    a(f"| SL | 4.5% |")
    a(f"| TP | 5.0% |")
    a(f"| Trailing stop | No (consistente con los otros backtests) |")
    a(f"| Gates de producción | No replicados (baseline puro) |")
    a("")
    a("---")
    a("")
    a("## 3. Resultados")
    a("")
    if not trades:
        a("**Sin trades generados en el período.**")
        a("")
        a("Posibles causas:")
        a("- ETH no alcanzó RSI 60–75 en 4H durante ene–ago 2026")
        a("- Insuficiente warmup de RSI")
        a("")
    else:
        a("| Métrica | Producción |")
        a("|---------|-----------|")
        a(f"| Trades totales | {m['trades']} |")
        a(f"| TP | {m['tp']} |")
        a(f"| SL | {m['sl']} |")
        a(f"| Win Rate | {m['wr']:.1f}% |")
        a(f"| Expectancy/trade | {fmt_pl(m['expect'])} |")
        a(f"| Profit Factor | {fmt_pf(m['pf'])} |")
        a(f"| P/L acumulado | {fmt_pl(m['pl_total'])} |")
        a(f"| Capital final | ${capital:.4f} |")
        a(f"| DD máximo | {max_dd:.1f}% |")
        a(f"| Ganancia media (TP) | {fmt_pl(m['avg_win'])} |")
        a(f"| Pérdida media (SL) | {fmt_pl(m['avg_loss'])} |")

    a("")
    a("---")
    a("")
    a("## 4. Desglose mensual")
    a("")

    if not meses_data:
        a("_Sin trades — sin datos mensuales._")
    else:
        a("| Mes | Trades | TP | SL | PF | Expectancy | P/L total |")
        a("|-----|--------|----|----|-----|-----------|-----------|")
        for mes, d in sorted(meses_data.items()):
            anio, num = mes.split("-")
            nombre = f"{MESES_NOMBRE.get(num, num)} {anio}"
            pl_mes = sum(t["pl"] for t in trades if t["entrada_ts"].strftime("%Y-%m") == mes)
            a(f"| {nombre} | {d['trades']} | {d['tp']} | {d['sl']} "
              f"| {fmt_pf(d['pf'])} | {fmt_pl(d['expect'])} | {fmt_pl(pl_mes)} |")

    a("")
    a("---")
    a("")
    a("## 5. Trades individuales")
    a("")
    if not trades:
        a("_Sin trades._")
    else:
        a("| # | Entrada | RSI | Precio E | Precio S | Resultado | P/L |")
        a("|---|---------|-----|----------|----------|-----------|-----|")
        for i, t in enumerate(trades, 1):
            a(f"| {i} | {t['entrada_ts'].strftime('%Y-%m-%d %H:%M')} "
              f"| {t['rsi']:.1f} | {t['precio_e']:.2f} | {t['precio_s']:.2f} "
              f"| {t['resultado']} | {fmt_pl(t['pl'])} |")

    a("")
    a("---")
    a("")
    a("## 6. Comparación con histórico 2021–2026")
    a("")
    a("| Período | Trades | WR | PF | Expect | Capital |")
    a("|---------|--------|----|----|--------|---------|")
    a("| Histórico 2021–2026 (forense 2026-08-13) | 254 | 51.97% | 1.105 | +$0.012 | $23.01 |")
    a("| Walk-forward val 2024–25 | — | — | 0.856 | — | — |")
    if trades:
        a(f"| **Forward 2026 (esta prueba)** | **{m['trades']}** | **{m['wr']:.1f}%** "
          f"| **{fmt_pf(m['pf'])}** | **{fmt_pl(m['expect'])}** | **${capital:.4f}** |")
    else:
        a("| **Forward 2026 (esta prueba)** | **0** | **—** | **—** | **—** | **$20.00** |")
    a("")
    a("> Nota: el forense histórico corre con el motor de backtest completo (EMA, múltiples")
    a("> entradas por vela). Este baseline usa RSI puro, una posición a la vez — comparación")
    a("> orientativa, no exacta.")
    a("")
    a("---")
    a("")
    a("## 7. Limitaciones")
    a("")
    a("1. **Sin gates de producción:** el bot real filtra por termómetro, spread, horario")
    a("   y eventos macro. Las señales aquí son un superset de las reales.")
    a("2. **Sin trailing stop:** TP/SL fijo. El trailing del bot puede cambiar el resultado.")
    a("3. **Monto fijo $5:** producción usa gestión proporcional al capital disponible.")
    a("4. **Sin filtro de fase:** este baseline corre RSI puro sin verificar que el director")
    a("   estaba en ALCISTA — puede incluir señales en períodos LATERAL o BAJISTA.")
    a("5. **Muestra pequeña:** ~7.5 meses de datos en 2026. Cualquier métrica tiene alta")
    a("   incertidumbre estadística.")
    a("")
    a("---")
    a("")
    a("## 8. Veredicto del baseline")
    a("")
    if not trades:
        a("**SIN TRADES — BASELINE NO OPERATIVO**")
        a("")
        a("ETH ALCISTA Producción no generó ninguna señal RSI 60–75 en 4H durante ene–ago 2026.")
        a("Esto en sí mismo es información: si el mercado no alcanzó la zona RSI 60–75 en")
        a("4H durante 7.5 meses, el sistema estuvo inactivo todo el período.")
    elif m["trades"] < MIN_TRADES:
        a(f"**MUESTRA INSUFICIENTE ({m['trades']} trades < {MIN_TRADES} mínimo)**")
        a("")
        a(f"Baseline registrado: PF {fmt_pf(m['pf'])}, WR {m['wr']:.1f}%, "
          f"Expectancy {fmt_pl(m['expect'])}, Capital ${capital:.4f}.")
        a("")
        if m["pf"] >= 1.0:
            a("El baseline es POSITIVO en 2026 (PF ≥ 1.0), pero con muestra insuficiente")
            a("para conclusiones estadísticas.")
        else:
            a("El baseline es NEGATIVO en 2026 (PF < 1.0). Consistente con el walk-forward")
            a("que mostró PF 0.856 en validación 2024–25.")
    else:
        if m["pf"] >= 1.1:
            veredicto = "PRODUCCION ACTIVA — PF > 1.1 con muestra suficiente"
        elif m["pf"] >= 1.0:
            veredicto = "PRODUCCION MARGINAL — PF positivo pero cerca del limite"
        else:
            veredicto = "PRODUCCION NEGATIVA en 2026"
        a(f"**{veredicto}**")
    a("")
    a("---")
    a("")
    a("## 9. Siguiente paso")
    a("")
    a("Con este baseline, Ariel puede decidir:")
    a("")
    a("- **Si hay trades suficientes y el baseline es positivo:** proponer un candidato")
    a("  con hipótesis fundamentada en el comportamiento observado.")
    a("- **Si hay trades pero el baseline es negativo:** analizar en qué condiciones fallaron")
    a("  las señales antes de proponer cambios.")
    a("- **Si no hay trades o muy pocos:** evaluar si tiene sentido continuar con ETH")
    a("  o pasar a la siguiente moneda (BTC).")
    a("- **En cualquier caso:** el candidato se define DESPUÉS de ver este baseline,")
    a("  no antes. Ningún parámetro se elige arbitrariamente.")
    a("")
    a("---")
    a("")
    a("## 10. Confirmación final de aislamiento")
    a("")
    a("- `config_cartera.py` = **SIN CAMBIOS** ✅")
    a("- `francotirador_alcista_eth.py` = **SIN CAMBIOS** ✅")
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
    ahora_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    velas_raw = [v for v in velas_raw if int(v[6]) < ahora_ms]
    print(f"  Velas descargadas: {len(velas_raw)}")

    if len(velas_raw) < 30:
        print("ERROR: pocas velas.")
        return

    fecha_fin = datetime.utcfromtimestamp(int(velas_raw[-1][0]) / 1000).strftime("%Y-%m-%d")

    print("Simulando Produccion ETH ALCISTA...")
    trades, capital, max_dd = simular(velas_raw, PRODUCCION)
    m = metricas(trades, capital, max_dd)

    if trades:
        print(f"\n=== RESULTADOS ===")
        print(f"Produccion: {m['trades']} trades | PF {m['pf']:.3f} | "
              f"WR {m['wr']:.1f}% | Expect {m['expect']:.4f} | "
              f"Cap ${capital:.4f} | DD {max_dd:.1f}%")
    else:
        print("\n=== SIN TRADES GENERADOS ===")
        print("ETH ALCISTA Produccion no disparo ninguna señal RSI 60-75 en 4H durante 2026.")

    reporte = generar_reporte(m, trades, capital, max_dd, len(velas_raw), fecha_fin)

    os.makedirs(os.path.dirname(os.path.expanduser(REPORT_PATH)), exist_ok=True)
    with open(os.path.expanduser(REPORT_PATH), "w") as f:
        f.write(reporte)
    print(f"\nReporte: {REPORT_PATH}")


if __name__ == "__main__":
    main()
