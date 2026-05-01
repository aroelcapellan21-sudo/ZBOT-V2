import os

archivos = [
    "config_cartera.py",
    "filtro_horario.py",
    "filtro_eventos.py",
    "filtro_calidad.py",
    "medidor_spread.py",
    "limitador_diario.py",
    "guardian_riesgo.py",
    "termometro.py"
]

print("\n========== REVISION DE PARAMETROS ==========\n")

for archivo in archivos:
    if os.path.exists(archivo):
        print(f"\n----- {archivo} -----\n")
        with open(archivo, "r") as f:
            lineas = f.readlines()
            for linea in lineas[:80]:
                if "=" in linea:
                    print(linea.strip())
    else:
        print(f"{archivo} NO EXISTE")

print("\n========== FIN REVISION ==========\n")
