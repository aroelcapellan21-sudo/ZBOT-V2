# =========================================
# filtro_horario.py
# FIX: pytz eliminado (violaba Constitucion)
# FIX: Reemplazado con datetime stdlib UTC-4
# Sin librerias externas. Constitucion RESPETADA
# =========================================

from datetime import datetime, timezone, timedelta

# Santo Domingo — UTC-4 (sin horario de verano)
TZ_SD     = timezone(timedelta(hours=-4))
HORA_INICIO = 4   # 4 AM hora local
HORA_FIN    = 21  # 9 PM hora local

def puede_operar_horario():
    hora_actual = datetime.now(TZ_SD).hour
    puede       = HORA_INICIO <= hora_actual < HORA_FIN
    print(f"  [HORARIO] Hora local SD: {hora_actual}h | Ventana: {HORA_INICIO}-{HORA_FIN}h | {'✅ OK' if puede else '❌ Fuera'}")
    return puede

if __name__ == "__main__":
    if puede_operar_horario():
        print("✅ El bot tiene permiso para operar ahora.")
    else:
        print("🌙 Fuera de horario. El bot descansará.")
