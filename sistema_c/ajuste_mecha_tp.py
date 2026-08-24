"""
Backtest de la hipotesis "ajuste por mecha en el TP", formulada en
reports/2026-08-24_analisis-outliers-trailing-atr.md a partir de un hallazgo
exploratorio (9 casos). Acá se prueba con la muestra COMPLETA de TP
historicos (no solo los que pasan el detector de "vela fuerte").

Hipotesis (decision de una sola vela, sin postergar nada, sin evaluacion a
1h): en la propia vela de 4h que dispara el TP, si
  high_vela - close_vela > k * ATR(14)_vela
cerrar en (high - k*ATR) en vez del TP nominal. Si no se cumple, cerrar en
el TP normal sin cambios -- por construccion, delta nunca puede ser
negativo (no hace falta floor adicional: la condicion misma garantiza
high-k*ATR > close cuando se activa).

Parametros: k en {1.0, 1.5, 2.0, 2.5}, con y sin prefiltro de volumen
extremo (vol_rel >= 5x, la pista del analisis de outliers).

Baseline (todos los TP, no solo vela fuerte) reusado de los mismos datasets
ya validados de 9/5.9 anios:
  - BTC: reports/raw/btc_fase2_variantes_2026-08-22.json -> "baseline"
  - ETH: reports/raw/eth_fase2_variantes_2026-08-23.json -> "baseline"
  - SOL: reports/raw/sol_lateral_evaluar_literal_2020_2026_baseline_2026-08-22.json

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits.
"""
import sys, os, json
from datetime import datetime, timedelta
sys.path.insert(0, "/home/ariel/bot-padre-v2")
sys.path.insert(0, "/home/ariel/bot-padre-v2/sistema_c")
import numpy as np
import tp_postergado_atr as m

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
K_VALUES = [1.0, 1.5, 2.0, 2.5]
VOL_REL_PREFILTRO = 5.0


def vol_rel_de_vela(velas_4h, ts_sorted, idx):
    if idx < 20:
        return None
    v = velas_4h[ts_sorted[idx]]
    vols_prev = [velas_4h[ts_sorted[i]]["volume"] for i in range(idx - 20, idx)]
    vol_prom = sum(vols_prev) / 20
    return v["volume"] / vol_prom if vol_prom > 0 else None


def neto_pct(entrada, salida):
    return ((salida * (1 - m.COMISION)) / (entrada * (1 + m.COMISION)) - 1) * 100


def bootstrap_media(deltas, n_boot=10000, seed=42):
    rng = np.random.default_rng(seed)
    d = np.array(deltas)
    n = len(d)
    boot = np.empty(n_boot)
    for i in range(n_boot):
        boot[i] = rng.choice(d, size=n, replace=True).mean()
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return dict(media=round(float(d.mean()), 4), mediana=round(float(np.median(d)), 4),
                ic95=[round(float(lo), 4), round(float(hi), 4)], cruza_cero=bool(lo < 0 < hi))


if __name__ == "__main__":
    datos_por_moneda = {}
    for moneda, cfg in m.MONEDAS.items():
        print(f"\n[cargar] {moneda}...")
        velas_4h, ts_4h_sorted = m.cargar_4h(cfg["symbol"], cfg["backup"], cfg["fecha_desde"])
        idx_4h_map = {ts: i for i, ts in enumerate(ts_4h_sorted)}

        if cfg["baseline_key"]:
            raw = json.load(open(cfg["baseline_json"]))[cfg["baseline_key"]]
            tps_raw = [t for t in raw if t["estado"] == "TP"]
        else:
            raw = json.load(open(cfg["baseline_json"]))
            tps_raw = []
            for t in raw:
                if t["estado"] != "TP":
                    continue
                dt_entrada = datetime.strptime(t["ts_entrada"], "%Y-%m-%d %H:%M:%S")
                dt_salida = dt_entrada + timedelta(hours=4 * int(t["velas"]))
                t2 = dict(t); t2["ts_salida"] = dt_salida.strftime("%Y-%m-%d %H:%M:%S")
                tps_raw.append(t2)

        # Precalcular, para CADA TP, high/close/ATR14/vol_rel de su propia vela
        info_trades = []
        for t in tps_raw:
            ts_salida = t["ts_salida"]
            if ts_salida not in idx_4h_map:
                continue
            idx = idx_4h_map[ts_salida]
            v = velas_4h[ts_salida]
            atr = m.calcular_atr14(velas_4h, ts_4h_sorted, idx)
            if atr is None:
                continue
            vol_rel = vol_rel_de_vela(velas_4h, ts_4h_sorted, idx)
            wick = v["high"] - v["close"]
            info_trades.append(dict(ts_entrada=t["ts_entrada"], ts_salida=ts_salida,
                                     precio_entrada=t["entrada"], precio_tp=t["salida"],
                                     high=v["high"], close=v["close"], wick=wick, atr=atr,
                                     vol_rel=vol_rel, neto_original=neto_pct(t["entrada"], t["salida"])))
        print(f"  {len(info_trades)}/{len(tps_raw)} TP con datos completos (ATR14+vol_rel)")
        datos_por_moneda[moneda] = info_trades

    resultados = {}
    resumen_calendario = {}  # (k, prefiltro) -> set de fechas across monedas
    for prefiltro in [False, True]:
        for k in K_VALUES:
            clave_global = f"k{k}_prefiltro{prefiltro}"
            fechas_globales = set()
            resultados[clave_global] = {}
            for moneda in m.MONEDAS:
                info_trades = datos_por_moneda[moneda]
                afectados, no_afectados = [], []
                for tr in info_trades:
                    cumple_wick = tr["wick"] > k * tr["atr"]
                    cumple_prefiltro = (tr["vol_rel"] is not None and tr["vol_rel"] >= VOL_REL_PREFILTRO) if prefiltro else True
                    if cumple_wick and cumple_prefiltro:
                        precio_cierre = tr["high"] - k * tr["atr"]
                        neto_nuevo = neto_pct(tr["precio_entrada"], precio_cierre)
                        delta = neto_nuevo - tr["neto_original"]
                        afectados.append(dict(ts_entrada=tr["ts_entrada"], ts_salida=tr["ts_salida"],
                                               neto_original=round(tr["neto_original"], 4),
                                               neto_nuevo=round(neto_nuevo, 4), delta=round(delta, 4),
                                               vol_rel=round(tr["vol_rel"], 2) if tr["vol_rel"] else None))
                    else:
                        no_afectados.append(tr["ts_entrada"])

                deltas = [a["delta"] for a in afectados]
                n = len(deltas)
                pos = sum(1 for d in deltas if d > 1e-9)
                cero = n - pos  # nunca puede ser negativo por construccion
                boot = bootstrap_media(deltas) if n >= 5 else None
                deltas_sorted = sorted(deltas, reverse=True)
                total = sum(deltas)
                top3 = sum(deltas_sorted[:3])
                top5 = sum(deltas_sorted[:5])
                pct_top3 = round(top3 / total * 100, 1) if total > 1e-9 else None
                pct_top5 = round(top5 / total * 100, 1) if total > 1e-9 else None

                # walk-forward 3 ventanas sobre los afectados (unicos con informacion no nula)
                af_sorted = sorted(afectados, key=lambda x: x["ts_entrada"])
                wf = []
                if len(af_sorted) >= 6:
                    tercio = len(af_sorted) // 3
                    for i in range(3):
                        lo, hi = i * tercio, (i + 1) * tercio if i < 2 else len(af_sorted)
                        sub = af_sorted[lo:hi]
                        if sub:
                            wf.append(dict(rango=f"{sub[0]['ts_entrada'][:10]}->{sub[-1]['ts_entrada'][:10]}",
                                            n=len(sub), suma_delta=round(sum(x['delta'] for x in sub), 3),
                                            positivos=sum(1 for x in sub if x['delta'] > 1e-9)))

                fechas_globales.update(a["ts_salida"] for a in afectados)

                resultados[clave_global][moneda] = dict(
                    n_tp_total=len(info_trades), n_afectados=n, n_no_afectados=len(no_afectados),
                    delta_pos=pos, delta_cero=cero, media=boot["media"] if boot else None,
                    mediana=boot["mediana"] if boot else None, ic95=boot["ic95"] if boot else None,
                    cruza_cero=boot["cruza_cero"] if boot else None,
                    pnl_total_delta=round(total, 3), pct_top3=pct_top3, pct_top5=pct_top5,
                    walkforward=wf, afectados=afectados)

                print(f"[k={k} prefiltro={prefiltro}] {moneda}: n_afectados={n}/{len(info_trades)} "
                      f"media={boot['media'] if boot else 'NA'} mediana={boot['mediana'] if boot else 'NA'} "
                      f"top3%={pct_top3} top5%={pct_top5} pnl_delta={round(total,3)}")

            resumen_calendario[clave_global] = len(fechas_globales)
            print(f"  >> eventos de calendario unicos combinando las 3 monedas: {len(fechas_globales)}")

    ruta = os.path.join(RAW_DIR, f"ajuste_mecha_tp_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(ruta, "w") as f:
        json.dump(dict(resultados=resultados, calendario=resumen_calendario), f, indent=2, default=str)
    print(f"\n[output] {ruta}")
