# =========================================
# centinela/config.py
# Configuracion central del Centinela Guardian
# Todos los umbrales y parametros en un solo lugar
# Constitucion RESPETADA
# =========================================

# --- ACTIVOS VIGILADOS ---
ACTIVOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]

# --- DRAWDOWN ---
DRAWDOWN_DIARIO_AMARILLO  = 2.0   # % alerta amarilla
DRAWDOWN_DIARIO_NARANJA   = 3.0   # % alerta naranja
DRAWDOWN_DIARIO_ROJO      = 5.0   # % pausa total

DRAWDOWN_SEMANAL_AMARILLO = 4.0   # % alerta amarilla
DRAWDOWN_SEMANAL_NARANJA  = 6.0   # % alerta naranja
DRAWDOWN_SEMANAL_ROJO     = 7.0   # % pausa total

DRAWDOWN_POR_ACTIVO_MAX   = 2.0   # % pausa individual del activo

# --- OPERACIONES SIMULTANEAS ---
MAX_OPERACIONES_SIMULTANEAS = 6   # Constitucion: maximo permitido

# --- CONECTIVIDAD ---
FALLOS_CONECTIVIDAD_PARA_PAUSAR = 3   # fallos seguidos antes de pausar
INTERVALO_PING = 300                   # segundos entre pings (5 minutos)

# --- VOLATILIDAD ANOMALA ---
VOLATILIDAD_ANOMALA_PORCENTAJE = 5.0  # % en 1 hora activa modo panico
DURACION_MODO_PANICO = 1800           # segundos en modo panico (30 min)

# --- CORRELACION ---
CORRELACION_UMBRAL = 0.9              # reduce posiciones al 50%
VENTANA_CORRELACION = 30              # dias para calcular correlacion movil

# --- CONFIRMACION DOBLE ---
CICLOS_CONFIRMACION = 2               # ciclos antes de actuar

# --- AUTO RECUPERACION ---
TIEMPO_AUTO_RECUPERACION = 3600       # segundos (60 minutos)

# --- INTERVALO PRINCIPAL ---
INTERVALO_CICLO = 60                  # segundos entre ciclos del Centinela

# --- TELEGRAM ---
TELEGRAM_TOKEN_ALERTAS = ""           # Token del bot de alertas urgentes
TELEGRAM_CHAT_ID_ALERTAS = ""         # Chat ID para alertas urgentes

# --- VALIDACION DE UMBRALES ---
def validar_umbrales():
    errores = []
    if DRAWDOWN_DIARIO_AMARILLO >= DRAWDOWN_DIARIO_NARANJA:
        errores.append("ERROR: Drawdown amarillo debe ser menor que naranja")
    if DRAWDOWN_DIARIO_NARANJA >= DRAWDOWN_DIARIO_ROJO:
        errores.append("ERROR: Drawdown naranja debe ser menor que rojo")
    if DRAWDOWN_SEMANAL_AMARILLO >= DRAWDOWN_SEMANAL_NARANJA:
        errores.append("ERROR: Drawdown semanal amarillo debe ser menor que naranja")
    if DRAWDOWN_SEMANAL_NARANJA >= DRAWDOWN_SEMANAL_ROJO:
        errores.append("ERROR: Drawdown semanal naranja debe ser menor que rojo")
    if MAX_OPERACIONES_SIMULTANEAS > 6:
        errores.append("ERROR: Maximo de operaciones viola la Constitucion (max 6)")
    if CICLOS_CONFIRMACION < 2:
        errores.append("ERROR: Doble confirmacion requiere minimo 2 ciclos")
    return errores

if __name__ == "__main__":
    print("=== CONFIGURACION DEL CENTINELA GUARDIAN ===\n")
    errores = validar_umbrales()
    if errores:
        for e in errores:
            print(e)
    else:
        print("✅ Todos los umbrales son validos y seguros.")
        print(f"\nDrawdown diario    : {DRAWDOWN_DIARIO_AMARILLO}% / {DRAWDOWN_DIARIO_NARANJA}% / {DRAWDOWN_DIARIO_ROJO}%")
        print(f"Drawdown semanal   : {DRAWDOWN_SEMANAL_AMARILLO}% / {DRAWDOWN_SEMANAL_NARANJA}% / {DRAWDOWN_SEMANAL_ROJO}%")
        print(f"Max operaciones    : {MAX_OPERACIONES_SIMULTANEAS}")
        print(f"Fallos conectividad: {FALLOS_CONECTIVIDAD_PARA_PAUSAR}")
        print(f"Volatilidad anomala: {VOLATILIDAD_ANOMALA_PORCENTAJE}% en 1 hora")
        print(f"Correlacion umbral : {CORRELACION_UMBRAL}")
        print(f"Ciclos confirmacion: {CICLOS_CONFIRMACION}")
        print(f"Auto recuperacion  : {TIEMPO_AUTO_RECUPERACION/60} minutos")
        print(f"Intervalo ciclo    : {INTERVALO_CICLO} segundos")
