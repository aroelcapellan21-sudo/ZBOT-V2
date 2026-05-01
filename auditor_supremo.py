import os
from datetime import datetime

archivos = ['adn_mercado.csv', 'latencia.log', 'memoria_fugas.csv', 'contexto_noticias.log']

print(f"--- REPORTE DE ESTADO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

for arc in archivos:
    print(f"\n>> ANALIZANDO: {arc}")
    if os.path.exists(arc):
        with open(arc, 'r') as f:
            lineas = f.readlines()
            # Mostramos las últimas 3 líneas de cada uno para no saturar
            for l in lineas[-3:]:
                print(f"   {l.strip()}")
    else:
        print(f"   [!] Sin datos aún en {arc}")

print("\n--- FIN DEL REPORTE ---")
