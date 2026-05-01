# =========================================
# DIAGNOSTICO RAPIDO - francotirador_alcista_btc.py
# Copiar y pegar ENTERO en la terminal
# NO modifica nada de tu bot
# =========================================

import sys
import os

# Agregar ruta del proyecto
sys.path.append(os.path.expanduser("~/bot-padre-v2"))

from utils import fetch_velas, calcular_rsi, calcular_ema, detectar_fase, puede_operar_memoria, aplicar_filtro_estadistico
from filtro_calidad import señal_tiene_calidad
from gestor_correlacion import puede_operar
from termometro import puede_operar_termometro
from medidor_spread import spread_aceptable
from filtro_horario import puede_operar_horario
from limitador_diario import puede_operar_hoy
from filtro_eventos import puede_operar_eventos
from guardian_riesgo import esta_bloqueado

SYMBOL = "BTCUSDT"

print("\n" + "="*60)
print("🔍 DIAGNOSTICO FRANCOTIRADOR ALCISTA BTC")
print("="*60 + "\n")

# 1. Datos de mercado
cierres = fetch_velas(SYMBOL, limite=210)
if not cierres:
    print("❌ ERROR: No se pudieron obtener velas")
    sys.exit(1)

precio_actual = cierres[-1]
rsi = calcular_rsi(cierres[-15:])
ema_c = calcular_ema(cierres, 20)
ema_l = calcular_ema(cierres, 50)
fase = detectar_fase(cierres, symbol=SYMBOL)

print(f"📊 DATOS ACTUALES:")
print(f"   Precio: ${precio_actual}")
print(f"   RSI: {rsi}")
print(f"   EMA20: {ema_c} | EMA50: {ema_l}")
print(f"   EMA20 > EMA50: {'✅ SI' if ema_c > ema_l else '❌ NO'}")
print(f"   Fase detectada: '{fase}'\n")

# 2. Verificar cada filtro
print("🔬 VERIFICANDO FILTROS:\n")

checks = []

# Guardian
ok = not esta_bloqueado()
checks.append(("Guardian riesgo", ok))
print(f"   {'✅' if ok else '❌'} Guardian riesgo: {'OK' if ok else 'BLOQUEADO'}")

# Termometro
ok = puede_operar_termometro()
checks.append(("Termometro", ok))
print(f"   {'✅' if ok else '❌'} Termometro: {'OK' if ok else 'ACTIVO'}")

# Spread
ok = spread_aceptable(SYMBOL)
checks.append(("Spread", ok))
print(f"   {'✅' if ok else '❌'} Spread: {'OK' if ok else 'ALTO'}")

# Horario
ok = puede_operar_horario()
checks.append(("Horario", ok))
print(f"   {'✅' if ok else '❌'} Horario: {'OK' if ok else 'FUERA'}")

# Limite diario
ok = puede_operar_hoy()
checks.append(("Limite diario", ok))
print(f"   {'✅' if ok else '❌'} Limite diario: {'OK' if ok else 'ALCANZADO'}")

# Eventos macro
ok = puede_operar_eventos()
checks.append(("Eventos macro", ok))
print(f"   {'✅' if ok else '❌'} Eventos macro: {'OK' if ok else 'BLOQUEANTE'}")

# Fase ALCISTA
ok = (fase == "ALCISTA")
checks.append(("Fase = ALCISTA", ok))
print(f"   {'✅' if ok else '❌'} Fase ALCISTA: {'OK' if ok else f'NO (es {fase})'}")

# Tendencia multi-timeframe
ok = False
try:
    from detector_multitimeframe import confirmar_tendencia_multitf
    ok = confirmar_tendencia_multitf(SYMBOL, "ALCISTA")
except:
    ok = True  # si no existe, asumir OK
checks.append(("Tendencia multiTF", ok))
print(f"   {'✅' if ok else '❌'} Tendencia multiTF: {'OK' if ok else 'NO CONFIRMADA'}")

# Calidad de señal
ok = señal_tiene_calidad(SYMBOL, "ALCISTA")
checks.append(("Calidad señal", ok))
print(f"   {'✅' if ok else '❌'} Calidad señal: {'OK' if ok else 'BAJA CALIDAD'}")

# Filtro estadistico
ok_stats, motivo_stats = aplicar_filtro_estadistico(cierres)
checks.append(("Filtro estadistico", ok_stats))
print(f"   {'✅' if ok_stats else '❌'} Filtro estadistico: {'OK' if ok_stats else f'NO - {motivo_stats}'}")

# Memoria propia
try:
    ok_mem, motivo_mem, factor_mem = puede_operar_memoria(SYMBOL, rsi)
    checks.append(("Memoria propia", ok_mem))
    print(f"   {'✅' if ok_mem else '❌'} Memoria propia: {'OK' if ok_mem else f'NO - {motivo_mem}'} (factor: {factor_mem:.2f})")
except:
    print(f"   ⚠️ Memoria propia: No disponible o error")

# Correlacion
ok = puede_operar("ALCISTA", SYMBOL)
checks.append(("Correlacion", ok))
print(f"   {'✅' if ok else '❌'} Correlacion: {'OK' if ok else 'BLOQUEADA'}")

# RSI en rango
rsi_ok = (50 <= rsi <= 70) if rsi is not None else False
checks.append(("RSI 50-70", rsi_ok))
print(f"   {'✅' if rsi_ok else '❌'} RSI 50-70: {rsi} {'✅' if rsi_ok else '❌'}")

# 3. Resumen final
print("\n" + "="*60)
print("📋 RESUMEN FINAL:")
print("="*60)

fallaron = [nombre for nombre, ok in checks if not ok]

if not fallaron:
    print("\n✅ TODOS LOS FILTROS PASARON")
    print("🎯 El bot DEBERIA estar operando!")
    print("   Si no opera, revisa contar_operaciones_abiertas() o el limite de ops")
else:
    print(f"\n❌ FALLARON {len(fallaron)} FILTROS:")
    for f in fallaron:
        print(f"   - {f}")

print("\n💡 RECOMENDACION:")
if "Fase = ALCISTA" in fallaron:
    print("   → El problema es detectar_fase(): no clasifica como ALCISTA")
    print("   → Revisa la logica de detectar_fase() o fuerza la fase para testing")
elif "Memoria propia" in fallaron:
    print("   → La memoria esta bloqueando por resultados previos negativos")
    print("   → Revisa el archivo de memoria o espera a que se resetee")
elif "Calidad señal" in fallaron:
    print("   → El filtro de calidad no aprueba esta señal")
    print("   → Puede ser por volumen bajo o condiciones especificas")
elif "Filtro estadistico" in fallaron:
    print(f"   → Filtro estadistico: {motivo_stats}")
    print("   → Las velas recientes no cumplen condiciones estadisticas")
else:
    print("   → Ejecuta el script de nuevo y revisa cual filtro falla")

print("\n" + "="*60 + "\n")
