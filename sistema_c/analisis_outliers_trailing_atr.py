"""
Analisis de detalle de los casos "ganadores" (delta>0, k=1.0) del backtest
sistema_c/tp_postergado_atr.py -- reusa toda la logica de ese script (mismo
detector de vela fuerte, mismo ATR14, mismo mecanismo de piso), solo agrega
instrumentacion para reconstruir: nivel de ATR relativo al resto de la
moneda, magnitud de cuerpo/volumen vs el umbral minimo, velas hasta el pico
antes de revertir, fase de mercado (utils.detectar_fase) al momento de la
entrada, y fecha -- comparando los "ganadores" contra una muestra al azar de
trades delta=0 de la misma moneda.

Exploratorio -- no confirma ninguna regla, busca generar una hipotesis
especifica para backtestear despues con rigor completo (walk-forward,
n>=30) si corresponde.

No corre ningun backtest nuevo del mecanismo en si -- reusa exactamente los
mismos 44-68 trades "afectados" por moneda ya identificados en la corrida
anterior (tp_postergado_atr_2026-08-23.json), solo re-descarga 1h (no se
habia guardado en disco) para poder instrumentar el camino vela a vela.

Solo lectura. No toca config_cartera.py, francotiradores reales,
auditoria.csv. Sin commits.
"""
import sys, os, json, random
from datetime import datetime, timezone
sys.path.insert(0, "/home/ariel/bot-padre-v2")
sys.path.insert(0, "/home/ariel/bot-padre-v2/sistema_c")
import bisect
import numpy as np
import tp_postergado_atr as m
import utils

RAW_DIR = os.path.expanduser("~/bot-padre-v2/reports/raw")
K_FOCO = 1.0
random.seed(42)


def simular_con_instrumentacion(velas_1h, ts_1h_sorted, ts_salida_4h, precio_tp, maximo_semilla, atr_valor, k):
    """Igual que m.simular_postergacion pero ademas retorna: idx (velas 1h) donde
    se alcanzo el maximo final antes de revertir, y el precio de ese maximo."""
    piso_distancia = k * atr_valor
    maximo_visto = maximo_semilla
    idx_maximo = 0
    idx_1h = bisect.bisect_left(ts_1h_sorted, ts_salida_4h)
    n = len(ts_1h_sorted)
    velas_recorridas = 0
    while idx_1h < n:
        ts = ts_1h_sorted[idx_1h]
        v = velas_1h[ts]
        piso = max(precio_tp, maximo_visto - piso_distancia)
        if v["low"] <= piso:
            return piso, ts, velas_recorridas, idx_maximo, maximo_visto
        if v["high"] > maximo_visto:
            maximo_visto = v["high"]
            idx_maximo = velas_recorridas + 1
        idx_1h += 1
        velas_recorridas += 1
    return None, None, velas_recorridas, idx_maximo, maximo_visto


if __name__ == "__main__":
    reporte = {}
    for moneda, cfg in m.MONEDAS.items():
        print(f"\n{'='*70}\n{moneda}\n{'='*70}")
        velas_4h, ts_4h_sorted = m.cargar_4h(cfg["symbol"], cfg["backup"], cfg["fecha_desde"])
        velas_1h, ts_1h_sorted = m.cargar_1h(cfg["symbol"], cfg["fecha_desde"])
        closes_4h = [velas_4h[ts]["close"] for ts in ts_4h_sorted]
        idx_4h_map = {ts: i for i, ts in enumerate(ts_4h_sorted)}

        # Reconstruir lista de "afectados" (igual que tp_postergado_atr.py)
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
                dt_salida = dt_entrada + __import__("datetime").timedelta(hours=4 * int(t["velas"]))
                t2 = dict(t); t2["ts_salida"] = dt_salida.strftime("%Y-%m-%d %H:%M:%S")
                tps_raw.append(t2)

        afectados = []
        for t in tps_raw:
            ts_salida = t["ts_salida"]
            if ts_salida not in idx_4h_map:
                continue
            idx = idx_4h_map[ts_salida]
            es_fuerte, cuerpo_pct, vol_rel = m.clasificar_vela_fuerte(velas_4h, ts_4h_sorted, idx, cfg["umbral_x"], cfg["umbral_pct"])
            if not es_fuerte:
                continue
            atr_valor = m.calcular_atr14(velas_4h, ts_4h_sorted, idx)
            if atr_valor is None:
                continue
            precio_tp = t["salida"]; precio_entrada = t["entrada"]
            maximo_semilla = velas_4h[ts_salida]["high"]
            atr_pct = atr_valor / precio_tp * 100
            afectados.append(dict(ts_entrada=t["ts_entrada"], ts_salida=ts_salida, precio_entrada=precio_entrada,
                                   precio_tp=precio_tp, maximo_semilla=maximo_semilla, atr_valor=atr_valor,
                                   atr_pct=atr_pct, cuerpo_pct=cuerpo_pct, vol_rel=vol_rel, idx_4h=idx))

        print(f"  {len(afectados)} trades afectados (vela fuerte)")

        # Simular con instrumentacion, k=1.0
        detalle = []
        for a in afectados:
            precio_cierre, ts_cierre, velas_1h_totales, idx_maximo, maximo_final = simular_con_instrumentacion(
                velas_1h, ts_1h_sorted, a["ts_salida"], a["precio_tp"], a["maximo_semilla"], a["atr_valor"], K_FOCO)
            if precio_cierre is None:
                continue
            neto_orig = m.neto_pct(a["precio_entrada"], a["precio_tp"])
            neto_nuevo = m.neto_pct(a["precio_entrada"], precio_cierre)
            delta = neto_nuevo - neto_orig
            # fase de mercado al momento de la vela fuerte -- ventana de 210 cierres
            # terminando ahi (aproximacion, no la entrada del trade que fue antes)
            ventana_fase = closes_4h[max(0, a["idx_4h"] - 209): a["idx_4h"] + 1]
            fase = utils.detectar_fase(ventana_fase, symbol=cfg["symbol"]) if len(ventana_fase) >= 55 else "DESCONOCIDA"
            avance_sobre_semilla_pct = round((maximo_final - a["maximo_semilla"]) / a["maximo_semilla"] * 100, 3)
            detalle.append(dict(ts_entrada=a["ts_entrada"], ts_salida_tp=a["ts_salida"],
                                 atr_pct=round(a["atr_pct"], 3), cuerpo_pct=round(a["cuerpo_pct"], 1),
                                 vol_rel=round(a["vol_rel"], 3), delta=round(delta, 4),
                                 velas_1h_hasta_cierre=velas_1h_totales, velas_1h_hasta_pico=idx_maximo,
                                 avance_sobre_semilla_pct=avance_sobre_semilla_pct, fase=fase))

        ganadores = [d for d in detalle if d["delta"] > 1e-9]
        neutros = [d for d in detalle if abs(d["delta"]) <= 1e-9]
        muestra_neutros = random.sample(neutros, min(15, len(neutros)))

        print(f"  Ganadores (delta>0): {len(ganadores)}")
        for g in ganadores:
            print(f"    {g}")
        print(f"  Muestra de referencia (delta=0, n={len(muestra_neutros)}):")
        atr_ref = [x["atr_pct"] for x in muestra_neutros]
        cuerpo_ref = [x["cuerpo_pct"] for x in muestra_neutros]
        vol_ref = [x["vol_rel"] for x in muestra_neutros]
        pico_ref = [x["velas_1h_hasta_pico"] for x in muestra_neutros]
        print(f"    ATR%: mediana={np.median(atr_ref):.3f} rango=[{min(atr_ref):.3f},{max(atr_ref):.3f}]")
        print(f"    cuerpo%: mediana={np.median(cuerpo_ref):.1f} rango=[{min(cuerpo_ref):.1f},{max(cuerpo_ref):.1f}]")
        print(f"    vol_rel: mediana={np.median(vol_ref):.2f} rango=[{min(vol_ref):.2f},{max(vol_ref):.2f}]")
        print(f"    velas_hasta_pico: mediana={np.median(pico_ref):.1f} rango=[{min(pico_ref)},{max(pico_ref)}]")
        fases_ref = {}
        for x in muestra_neutros:
            fases_ref[x["fase"]] = fases_ref.get(x["fase"], 0) + 1
        print(f"    fases: {fases_ref}")

        # tambien stats de TODOS los delta=0 (no solo la muestra), para tener el panorama completo
        atr_all = [x["atr_pct"] for x in neutros]
        cuerpo_all = [x["cuerpo_pct"] for x in neutros]
        vol_all = [x["vol_rel"] for x in neutros]
        pico_all = [x["velas_1h_hasta_pico"] for x in neutros]

        reporte[moneda] = dict(n_afectados=len(afectados), n_evaluados=len(detalle),
                                ganadores=ganadores, muestra_referencia=muestra_neutros,
                                stats_todos_neutros=dict(
                                    atr_pct_mediana=round(float(np.median(atr_all)), 3) if atr_all else None,
                                    cuerpo_pct_mediana=round(float(np.median(cuerpo_all)), 1) if cuerpo_all else None,
                                    vol_rel_mediana=round(float(np.median(vol_all)), 2) if vol_all else None,
                                    velas_pico_mediana=round(float(np.median(pico_all)), 1) if pico_all else None,
                                    n=len(neutros)))

    ruta = os.path.join(RAW_DIR, f"analisis_outliers_trailing_atr_{datetime.now().strftime('%Y-%m-%d')}.json")
    with open(ruta, "w") as f:
        json.dump(reporte, f, indent=2, default=str)
    print(f"\n[output] {ruta}")
