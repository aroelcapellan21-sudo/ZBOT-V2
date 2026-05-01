# =========================================
# filtro_eventos.py
# FIX: imports muertos eliminados
# FIX: Comparacion de horas como enteros
# FIX: except pass eliminados
# Sin librerias externas. Constitucion RESPETADA
# =========================================

import json
import os
from datetime import datetime, timezone

EVENTOS_MANUAL = os.path.expanduser("~/bot-padre-v2/signals/eventos_macro.json")

HORAS_RIESGO_MACRO = {
    "13:30": "Apertura mercados USA / Datos economicos",
    "14:00": "Fed / Reserva Federal anuncios",
    "14:30": "Datos empleo USA / CPI / PPI",
    "18:00": "Cierre sesion NY",
    "20:00": "Declaraciones Fed fuera de horario",
}

def cargar_eventos_manuales():
    try:
        with open(EVENTOS_MANUAL, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"evento_activo": False, "descripcion": "", "hasta": ""}
    except Exception as e:
        print(f"  [EVENTOS] Error cargando eventos: {e}")
        return {"evento_activo": False, "descripcion": "", "hasta": ""}

def guardar_evento_manual(activo, descripcion="", hasta=""):
    try:
        os.makedirs(os.path.dirname(EVENTOS_MANUAL), exist_ok=True)
        data = {
            "evento_activo": activo,
            "descripcion":   descripcion,
            "hasta":         hasta
        }
        with open(EVENTOS_MANUAL, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  [EVENTOS] Evento guardado: {descripcion}")
    except Exception as e:
        print(f"  [EVENTOS] Error guardando evento: {e}")

def verificar_hora_riesgo():
    ahora  = datetime.now(timezone.utc)
    hora_h = ahora.hour
    hora_m = ahora.minute
    ahora_min = hora_h * 60 + hora_m

    for hora_riesgo, descripcion in HORAS_RIESGO_MACRO.items():
        h, m      = map(int, hora_riesgo.split(":"))
        riesgo_min = h * 60 + m
        diff       = abs(ahora_min - riesgo_min)
        if diff <= 15:
            print(f"  [EVENTOS] ⚠️ Cerca de evento macro: {descripcion} ({hora_riesgo} UTC)")
            return True, descripcion

    return False, ""

def puede_operar_eventos():
    eventos = cargar_eventos_manuales()

    if eventos.get("evento_activo"):
        hasta = eventos.get("hasta", "")
        desc  = eventos.get("descripcion", "evento desconocido")

        if hasta:
            # FIX: Comparacion como enteros, no strings
            ahora  = datetime.now(timezone.utc)
            ahora_min = ahora.hour * 60 + ahora.minute
            try:
                h, m       = map(int, hasta.split(":"))
                hasta_min  = h * 60 + m
                if ahora_min >= hasta_min:
                    guardar_evento_manual(False)
                    print(f"  [EVENTOS] ✅ Evento macro terminado. Bot activo.")
                else:
                    print(f"  [EVENTOS] ❌ Evento macro activo: {desc}. No operar.")
                    return False
            except Exception as e:
                print(f"  [EVENTOS] Error parseando hora hasta: {e}")
                return False
        else:
            print(f"  [EVENTOS] ❌ Evento macro activo: {desc}. No operar.")
            return False

    en_riesgo, descripcion = verificar_hora_riesgo()
    if en_riesgo:
        print(f"  [EVENTOS] ❌ Ventana de riesgo macro ({descripcion}). No operar.")
        return False

    print(f"  [EVENTOS] ✅ Sin eventos macro. Puede operar.")
    return True

def activar_evento_manual(descripcion, hasta_hora_utc):
    guardar_evento_manual(True, descripcion, hasta_hora_utc)
    print(f"  [EVENTOS] 🛑 Evento activado: {descripcion} hasta {hasta_hora_utc} UTC")

def desactivar_evento_manual():
    guardar_evento_manual(False)
    print(f"  [EVENTOS] ✅ Evento desactivado manualmente.")

if __name__ == "__main__":
    print("📰 Filtro de Eventos Macro\n")
    print(f"  Horas de riesgo configuradas:")
    for hora, desc in HORAS_RIESGO_MACRO.items():
        print(f"  {hora} UTC → {desc}")
    print()
    resultado = puede_operar_eventos()
    print(f"\n  Resultado: {'✅ Puede operar' if resultado else '❌ No operar ahora'}")
