# =========================================
# centinela/centinela.py
# Orquestador principal del Centinela Guardian - V2.12
# BUG FIX: Modulo operaciones desactivado (Bug 7)
# Constitucion RESPETADA
# =========================================

import sys
import os
import time
from datetime import datetime

# Asegurar que el bot pueda importar modulos desde la raiz
sys.path.insert(0, os.path.expanduser("~/bot-padre-v2"))

from centinela.config import INTERVALO_CICLO, validar_umbrales
from centinela.estado import estado_global as estado
from centinela.modulos import drawdown
from centinela.modulos import conectividad
# from centinela.modulos import operaciones  # <-- DESACTIVADO (Bug 7)
from centinela.modulos import volatilidad
from centinela.modulos import alertas
from memoria.memoria import registrar_centinela

def resetear_si_nuevo_dia():
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    fecha_guardada = estado.get("fecha_inicio_dia")
    if fecha_hoy != fecha_guardada:
        estado.resetear_dia()
        registrar_centinela("Nuevo dia detectado. Drawdown diario reseteado.")
        print(f"[CENTINELA] Nuevo dia detectado. Drawdown diario reseteado.")

def resetear_si_nueva_semana():
    semana_hoy = datetime.now().strftime("%Y-%W")
    semana_guardada = estado.get("fecha_inicio_semana")
    if semana_hoy != semana_guardada:
        estado.resetear_semana()
        registrar_centinela("Nueva semana detectada. Drawdown semanal reseteado.")
        print(f"[CENTINELA] Nueva semana detectada. Drawdown semanal reseteado.")

def ejecutar_ciclo():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[CENTINELA] Ciclo {timestamp}")

    resetear_si_nuevo_dia()
    resetear_si_nueva_semana()

    resultados = []

    # 1. Evaluar Drawdown
    try:
        r_drawdown = drawdown.evaluar()
        resultados.append(r_drawdown)
        print(f"  Drawdown    : {r_drawdown['nivel']} | {r_drawdown['datos']['drawdown_diario']}% diario")
    except Exception as e:
        print(f"  [ERROR] Drawdown: {e}")

    # 2. Evaluar Conectividad
    try:
        r_conectividad = conectividad.evaluar()
        resultados.append(r_conectividad)
        print(f"  Conectividad: {r_conectividad['nivel']} | {r_conectividad['motivo']}")
    except Exception as e:
        print(f"  [ERROR] Conectividad: {e}")

    # 3. Módulo Operaciones (Omitido por Auditoría V2.12 - Evita doble conteo con Orquesta)
    """
    try:
        r_operaciones = operaciones.evaluar()
        resultados.append(r_operaciones)
    except Exception as e:
        print(f"  [ERROR] Operaciones: {e}")
    """

    # 4. Evaluar Volatilidad
    try:
        r_volatilidad = volatilidad.evaluar()
        resultados.append(r_volatilidad)
        print(f"  Volatilidad : {r_volatilidad['nivel']} | {r_volatilidad['motivo']}")
    except Exception as e:
        print(f"  [ERROR] Volatilidad: {e}")

    # 5. Procesar Alertas y Nivel Global
    resultado_alertas = alertas.evaluar(resultados)
    nivel_global = resultado_alertas["nivel"]

    resumen = estado.get_resumen()
    print(f"  {'='*40}")
    print(f"  NIVEL GLOBAL: {nivel_global.upper()}")
    print(f"  Capital      : ${resumen['capital_actual']}")
    print(f"  DD Diario   : {resumen['drawdown_diario']}%")
    print(f"  DD Semanal  : {resumen['drawdown_semanal']}%")
    print(f"  Pausado      : {resumen['sistema_pausado']}")
    print(f"  Panico       : {resumen['modo_panico']}")

    # Latido cada hora
    minuto_actual = datetime.now().minute
    if minuto_actual == 0:
        registrar_centinela(
            f"LATIDO HORA | Nivel: {nivel_global.upper()} | "
            f"Capital: ${resumen['capital_actual']} | "
            f"DD Diario: {resumen['drawdown_diario']}% | "
            f"DD Semanal: {resumen['drawdown_semanal']}% | "
            f"Pausado: {resumen['sistema_pausado']} | "
            f"Panico: {resumen['modo_panico']}"
        )
        print(f"[CENTINELA] 💓 Latido registrado en log.")

def iniciar():
    print("="*50)
    print("[CENTINELA GUARDIAN] Iniciando...")
    print("="*50)

    errores = validar_umbrales()
    if errores:
        for e in errores:
            print(e)
        print("[CENTINELA] Configuracion invalida. Abortando.")
        return

    registrar_centinela("CENTINELA GUARDIAN INICIADO. Vigilancia activa.")
    print("[CENTINELA] Configuracion validada. Vigilancia activa.")

    while True:
        try:
            ejecutar_ciclo()
        except Exception as e:
            registrar_centinela(f"ERROR en ciclo: {e}")
            print(f"[CENTINELA] Error en ciclo: {e}")
        time.sleep(INTERVALO_CICLO)

if __name__ == "__main__":
    iniciar()
