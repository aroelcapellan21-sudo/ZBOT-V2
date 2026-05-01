import os
import csv
import json

def buscar_y_auditar():
    print("\n--- 🕵️ INVESTIGACIÓN PROFUNDA DE LA MATRIX ---")
    
    archivos_objetivo = ["registro_ops.csv", "billetera.json", "registro_ops_v3_obj5_stop3.csv", "auditoria.csv"]
    
    # Buscamos en todas las subcarpetas
    for root, dirs, files in os.walk("."):
        for nombre in files:
            if nombre in archivos_objetivo or "billetera" in nombre:
                ruta_completa = os.path.join(root, nombre)
                print(f"\n📍 Encontrado en: {ruta_completa}")
                
                if nombre.endswith('.csv'):
                    with open(ruta_completa, mode='r') as f:
                        lineas = list(csv.reader(f))
                        if len(lineas) > 1:
                            print(f"   📊 Operaciones totales: {len(lineas) - 1}")
                            print(f"   📝 Última línea: {lineas[-1]}")
                
                elif nombre.endswith('.json'):
                    with open(ruta_completa, 'r') as f:
                        try:
                            data = json.load(f)
                            print(f"   💰 Datos: {data}")
                        except:
                            print("   ⚠️ Error al leer JSON")

    print("\n----------------------------------------------")

buscar_y_auditar()
