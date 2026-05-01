import json
import os
from datetime import datetime

BILLETERA_PATH = "signals/billetera.json"


def cargar_billetera():
    if not os.path.exists(BILLETERA_PATH):
        return {"USDT": 1000.0}

    with open(BILLETERA_PATH, "r") as f:
        return json.load(f)


def guardar_billetera(billetera):
    os.makedirs("signals", exist_ok=True)
    with open(BILLETERA_PATH, "w") as f:
        json.dump(billetera, f, indent=4)


def actualizar_saldo(activo, monto):
    billetera = cargar_billetera()

    if activo not in billetera:
        billetera[activo] = 0.0

    billetera[activo] += float(monto)

    guardar_billetera(billetera)

    print(f"✅ Tesorero: {activo} actualizado en {monto:+.6f}")
    print(f"📊 Nuevo saldo {activo}: {billetera[activo]:.6f}")


if __name__ == "__main__":
    # EJEMPLO DE PRUEBA CONTROLADA
    actualizar_saldo("USDT", 0.0)
