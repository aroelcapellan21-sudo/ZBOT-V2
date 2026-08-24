"""
Fase 2 -- backtest de la hipotesis "volatilidad elevada como aviso"
(reports/2026-08-24_antecedentes-multiples-umbrales.md, umbral 5%, unico con
n>=30 en las 3 monedas).

Hipotesis: en el momento de la ENTRADA real del bot (no del TP), si
  ATR%(14)_entrada >= k_entrada * mediana_historica_ATR%_moneda
la posicion queda marcada para "dejar correr" -- si mas adelante llega a su
TP, en vez de cerrar ahi se aplica el mismo mecanismo de piso ya validado en
reports/2026-08-23_tp-postergado-trailing-atr.md (piso = max(TP,
maximo_visto - k_salida*ATR_TP), semilla = high de la vela del TP, ATR de
esa misma vela, evaluacion con velas de 1h). k_salida queda FIJO en 1.0 (el
valor identificado como "menos malo" en esa investigacion) -- lo unico que
varia acá es k_entrada (el umbral de la condicion de aviso), no el mecanismo
de salida en si, que se reutiliza sin modificar.

k_entrada a probar: 1.16, 1.2, 1.31 (vecindad de los ratios observados en la
exploracion de Fase 1).

Solo se simula postergacion para trades que en el baseline SI llegaron a TP
(un trade que cerro en SL nunca llega al punto de decision del TP, la
condicion de entrada solo determina si queda "marcado", no cambia su
resultado si no llega a TP).

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits.
"""
import sys, os, json
from datetime import datetime, timedelta
sys.path.insert(0, "/home/ariel/bot-padre-v2")
sys.path.insert(0, "/home/ariel/bot-padre-v2/sistema_c")
import numpy as np
import tp_postergado_atr as m
import antecedentes_movimientos_grandes as a

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
K_ENTRADA_VALUES = [1.16, 1.2, 1.31]
K_SALIDA_FIJO = 1.0


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
    velas_por_moneda, ts_por_moneda = {}, {}
    velas_1h_por_moneda, ts_1h_por_moneda = {}, {}
    atr_hist_por_moneda = {}

    for moneda, cfg in m.MONEDAS.items():
        print(f"\n[cargar] {moneda}...")
        velas_4h, ts_4h_sorted = m.cargar_4h(cfg["symbol"], cfg["backup"], cfg["fecha_desde"])
        velas_por_moneda[moneda] = velas_4h
        ts_por_moneda[moneda] = ts_4h_sorted
        velas_1h, ts_1h_sorted = m.cargar_1h(cfg["symbol"], cfg["fecha_desde"])
        velas_1h_por_moneda[moneda] = velas_1h
        ts_1h_por_moneda[moneda] = ts_1h_sorted

        muestreo = range(14, len(ts_4h_sorted), 6)
        vals = [a.atr_pct_de(velas_4h, ts_4h_sorted, i) for i in muestreo]
        vals = [v for v in vals if v is not None]
        atr_hist_por_moneda[moneda] = float(np.median(vals))
        print(f"  ATR% historico mediano: {atr_hist_por_moneda[moneda]:.3f}%")

    resultados = {}
    for k_entrada in K_ENTRADA_VALUES:
        clave = f"k_entrada_{k_entrada}"
        print(f"\n{'='*70}\nk_entrada = {k_entrada}\n{'='*70}")
        resultados[clave] = {}
        fechas_todas = set()

        for moneda, cfg in m.MONEDAS.items():
            velas_4h, ts_sorted = velas_por_moneda[moneda], ts_por_moneda[moneda]
            velas_1h, ts_1h_sorted = velas_1h_por_moneda[moneda], ts_1h_por_moneda[moneda]
            idx_map = {ts: i for i, ts in enumerate(ts_sorted)}

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

            afectados = []
            for t in tps_raw:
                ts_entrada, ts_salida = t["ts_entrada"], t["ts_salida"]
                if ts_entrada not in idx_map or ts_salida not in idx_map:
                    continue
                idx_entrada = idx_map[ts_entrada]
                idx_salida = idx_map[ts_salida]
                atr_pct_entrada = a.atr_pct_de(velas_4h, ts_sorted, idx_entrada)
                if atr_pct_entrada is None or atr_pct_entrada < k_entrada * atr_hist_por_moneda[moneda]:
                    continue  # no calificado como "aviso" -- se comporta igual que siempre (delta=0)
                atr_valor_tp = m.calcular_atr14(velas_4h, ts_sorted, idx_salida)
                if atr_valor_tp is None:
                    continue
                maximo_semilla = velas_4h[ts_salida]["high"]
                afectados.append(dict(ts_entrada=ts_entrada, ts_salida=ts_salida,
                                       precio_entrada=t["entrada"], precio_tp=t["salida"],
                                       maximo_semilla=maximo_semilla, atr_valor_tp=atr_valor_tp,
                                       atr_pct_entrada=round(atr_pct_entrada, 3)))

            deltas, trades_detalle, flips = [], [], 0
            for af in afectados:
                precio_cierre, ts_cierre, velas_1h_totales = m.simular_postergacion(
                    velas_1h, ts_1h_sorted, af["ts_salida"], af["precio_tp"], af["maximo_semilla"],
                    af["atr_valor_tp"], K_SALIDA_FIJO)
                if precio_cierre is None:
                    continue
                neto_orig = m.neto_pct(af["precio_entrada"], af["precio_tp"])
                neto_nuevo = m.neto_pct(af["precio_entrada"], precio_cierre)
                delta = neto_nuevo - neto_orig
                if neto_orig > 0 and neto_nuevo <= 0:
                    flips += 1
                deltas.append(delta)
                trades_detalle.append(dict(ts_entrada=af["ts_entrada"], delta=round(delta, 4)))

            n = len(deltas)
            pos = sum(1 for d in deltas if d > 1e-9)
            neg = sum(1 for d in deltas if d < -1e-9)
            cero = n - pos - neg
            boot = bootstrap_media(deltas) if n >= 5 else None
            deltas_sorted = sorted(deltas, reverse=True)
            total = sum(deltas)
            top5 = sum(deltas_sorted[:5])
            pct_top5 = round(top5 / total * 100, 1) if abs(total) > 1e-9 else None

            fechas_todas.update(af["ts_salida"] for af in afectados)

            trades_sorted = sorted(trades_detalle, key=lambda x: x["ts_entrada"])
            wf = []
            if len(trades_sorted) >= 6:
                tercio = len(trades_sorted) // 3
                for i in range(3):
                    lo, hi = i * tercio, (i + 1) * tercio if i < 2 else len(trades_sorted)
                    sub = trades_sorted[lo:hi]
                    if sub:
                        wf.append(dict(rango=f"{sub[0]['ts_entrada'][:10]}->{sub[-1]['ts_entrada'][:10]}",
                                        n=len(sub), suma_delta=round(sum(x['delta'] for x in sub), 3),
                                        positivos=sum(1 for x in sub if x['delta'] > 1e-9)))

            resultados[clave][moneda] = dict(
                n_tp_total=len(tps_raw), n_afectados=len(afectados), n_evaluado=n,
                delta_pos=pos, delta_neg=neg, delta_cero=cero, flips=flips,
                bootstrap=boot, pnl_delta_total=round(total, 3), pct_top5=pct_top5,
                walkforward=wf, trades=trades_detalle)

            print(f"  {moneda}: n_afectados={len(afectados)} n_evaluado={n} "
                  f"media={boot['media'] if boot else 'NA'} mediana={boot['mediana'] if boot else 'NA'} "
                  f"top5%={pct_top5} flips={flips}")

        print(f"  >> eventos de calendario unicos (3 monedas): {len(fechas_todas)}")
        resultados[clave]["_fechas_unicas"] = len(fechas_todas)

    ruta = os.path.join(RAW_DIR, f"backtest_volatilidad_aviso_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(ruta, "w") as f:
        json.dump(resultados, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
