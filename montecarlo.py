# =========================================
# montecarlo.py
# Simula diferentes secuencias de trades
# Prueba estabilidad del sistema
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
import random
from datetime import datetime

REPORTE = os.path.expanduser("~/bot-padre-v2/reports_historicos/montecarlo_resultado.json")

def ejecutar_montecarlo():
    print("🎲 Ejecutando Monte Carlo Simulation...\n")
    os.makedirs(os.path.dirname(REPORTE), exist_ok=True)

    # Parametros del sistema optimizado
    TP = 6.0
    SL = 3.5
    CAPITAL_INICIAL = 1000.0
    CAPITAL_POR_OP = 0.01
    WINRATE = 0.4048
    SIMULACIONES = 1000
    TRADES_POR_SIM = 100

    resultados_finales = []
    max_drawdowns = []
    rachas_perdidas = []
    simulaciones_rentables = 0

    print(f"  Parametros:")
    print(f"  TP            : {TP}%")
    print(f"  SL            : {SL}%")
    print(f"  Win Rate base : {WINRATE*100}%")
    print(f"  Simulaciones  : {SIMULACIONES}")
    print(f"  Trades/sim    : {TRADES_POR_SIM}\n")

    for sim in range(SIMULACIONES):
        capital = CAPITAL_INICIAL
        capital_max = CAPITAL_INICIAL
        max_dd = 0.0
        racha_perdida = 0
        racha_max = 0

        for _ in range(TRADES_POR_SIM):
            monto = capital * CAPITAL_POR_OP
            if random.random() < WINRATE:
                capital += monto * (TP / 100)
                racha_perdida = 0
            else:
                capital -= monto * (SL / 100)
                racha_perdida += 1
                racha_max = max(racha_max, racha_perdida)

            capital_max = max(capital_max, capital)
            dd = ((capital_max - capital) / capital_max) * 100
            max_dd = max(max_dd, dd)

        resultados_finales.append(round(capital, 4))
        max_drawdowns.append(round(max_dd, 4))
        rachas_perdidas.append(racha_max)
        if capital > CAPITAL_INICIAL:
            simulaciones_rentables += 1

    resultados_finales.sort()
    max_drawdowns.sort()

    capital_promedio = round(sum(resultados_finales) / len(resultados_finales), 4)
    capital_peor = resultados_finales[0]
    capital_mejor = resultados_finales[-1]
    capital_p10 = resultados_finales[int(SIMULACIONES * 0.10)]
    capital_p50 = resultados_finales[int(SIMULACIONES * 0.50)]
    capital_p90 = resultados_finales[int(SIMULACIONES * 0.90)]

    dd_promedio = round(sum(max_drawdowns) / len(max_drawdowns), 4)
    dd_peor = max_drawdowns[-1]
    dd_p90 = max_drawdowns[int(SIMULACIONES * 0.90)]

    racha_promedio = round(sum(rachas_perdidas) / len(rachas_perdidas), 2)
    racha_peor = max(rachas_perdidas)

    pct_rentable = round((simulaciones_rentables / SIMULACIONES) * 100, 2)

    print(f"📊 RESULTADOS MONTE CARLO ({SIMULACIONES} simulaciones)")
    print(f"\n  💰 Capital final (inicio: $1,000)")
    print(f"  Promedio      : ${capital_promedio}")
    print(f"  Mejor caso    : ${capital_mejor}")
    print(f"  Peor caso     : ${capital_peor}")
    print(f"  Percentil 10  : ${capital_p10}")
    print(f"  Percentil 50  : ${capital_p50}")
    print(f"  Percentil 90  : ${capital_p90}")
    print(f"\n  📉 Drawdown maximo")
    print(f"  Promedio      : {dd_promedio}%")
    print(f"  Peor caso     : {dd_peor}%")
    print(f"  Percentil 90  : {dd_p90}%")
    print(f"\n  🔴 Racha de perdidas")
    print(f"  Promedio      : {racha_promedio} trades")
    print(f"  Peor caso     : {racha_peor} trades")
    print(f"\n  ✅ Simulaciones rentables: {pct_rentable}%")

    if pct_rentable >= 55 and dd_p90 < 10:
        diagnostico = "SISTEMA ESTABLE"
        emoji = "✅"
    elif pct_rentable >= 45:
        diagnostico = "SISTEMA ACEPTABLE - necesita mas trades"
        emoji = "⚠️"
    else:
        diagnostico = "SISTEMA INESTABLE - revisar parametros"
        emoji = "❌"

    print(f"\n  {emoji} Diagnostico: {diagnostico}")

    reporte = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "parametros": {"tp": TP, "sl": SL, "winrate": WINRATE, "simulaciones": SIMULACIONES, "trades_por_sim": TRADES_POR_SIM},
        "capital": {"promedio": capital_promedio, "mejor": capital_mejor, "peor": capital_peor, "p10": capital_p10, "p50": capital_p50, "p90": capital_p90},
        "drawdown": {"promedio": dd_promedio, "peor": dd_peor, "p90": dd_p90},
        "rachas": {"promedio": racha_promedio, "peor": racha_peor},
        "pct_rentable": pct_rentable,
        "diagnostico": diagnostico
    }

    with open(REPORTE, "w") as f:
        json.dump(reporte, f, indent=2)

    print(f"\n✅ Reporte guardado en reports_historicos/montecarlo_resultado.json")

if __name__ == "__main__":
    ejecutar_montecarlo()
