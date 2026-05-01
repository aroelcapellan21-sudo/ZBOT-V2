import json

def mostrar_cartera():
    try:
        # Abrimos el archivo correcto (en la raíz del proyecto)
        with open("billetera.json", "r") as f:
            billetera = json.load(f)

        print("\n" + "=" * 30)
        print("📊 ESTADO DE TU CARTERA")
        print("=" * 30)

        for activo, cantidad in billetera.items():
            if activo == "USDT":
                print(f"{activo}: ${cantidad:,.2f}")
            elif cantidad > 0:
                print(f"{activo}: {cantidad:.6f}")

        print("=" * 30 + "\n")

    except FileNotFoundError:
        print("❌ El archivo billetera.json no existe.")
    except json.JSONDecodeError as e:
        print("❌ Error de formato en billetera.json:")
        print(e)


if __name__ == "__main__":
    mostrar_cartera()

