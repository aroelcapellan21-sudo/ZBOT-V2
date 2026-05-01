#!/usr/bin/env python3
"""
Inventario de Filtros del Z-Bot V2
-----------------------------------
Analiza los archivos fuente del bot y extrae:
- Filtros de entrada (RSI, EMAs, fase, etc.)
- Filtros de protección (horario, eventos, drawdown, etc.)
- Filtros de calidad (volumen, spread, ATR, etc.)
- Parámetros y umbrales configurados
"""

import os
import re
import ast
import sys
from pathlib import Path
from collections import defaultdict

# Directorio base del bot (ajústalo si es necesario)
BASE_DIR = Path(os.path.expanduser("~/bot-padre-v2"))

# Palabras clave para identificar filtros en el código
FILTER_KEYWORDS = [
    "filtro", "filter", "validar", "validate", "check", "verificar",
    "spread", "horario", "evento", "macro", "correlacion", "drawdown",
    "limitador", "riesgo", "risk", "calidad", "quality", "atr", "volumen"
]

# Archivos prioritarios para escanear
PRIORITY_FILES = [
    "config.py", "centinela/config.py", "utils.py",
    "filtro_calidad.py", "filtro_horario.py", "filtro_eventos.py",
    "gestor_riesgo.py", "guardian_riesgo.py", "limitador_diario.py",
    "director_orquesta.py", "corecro.py", "cerebro.py"
]

def buscar_filtros_en_archivo(ruta):
    """Busca fragmentos de código que parezcan filtros."""
    filtros = []
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
            lineas = contenido.split('\n')
            for i, linea in enumerate(lineas, 1):
                linea_lower = linea.lower()
                if any(kw in linea_lower for kw in FILTER_KEYWORDS):
                    # Limpiar la línea para mostrar
                    linea_limpia = linea.strip()
                    if len(linea_limpia) > 120:
                        linea_limpia = linea_limpia[:120] + "..."
                    filtros.append({
                        "archivo": ruta.name,
                        "linea": i,
                        "texto": linea_limpia
                    })
    except Exception as e:
        pass
    return filtros

def extraer_constantes(ruta):
    """Extrae variables de configuración (asignaciones simples)."""
    constantes = {}
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
            # Buscar patrones como NOMBRE = valor
            patron = r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)(?:\s*#.*)?$'
            for linea in contenido.split('\n'):
                m = re.match(patron, linea)
                if m:
                    nombre = m.group(1)
                    valor = m.group(2).strip()
                    constantes[nombre] = valor
    except:
        pass
    return constantes

def main():
    print("\n" + "="*70)
    print("🔍 INVENTARIO DE FILTROS - Z-Bot V2")
    print("="*70)
    
    if not BASE_DIR.exists():
        print(f"❌ No se encontró el directorio: {BASE_DIR}")
        print("   Por favor, ajusta la variable BASE_DIR al inicio del script.")
        sys.exit(1)
    
    # 1. Recolectar constantes de configuración
    print("\n📦 CONFIGURACIÓN GENERAL (umbrales y límites)")
    print("-" * 50)
    constantes_totales = {}
    for archivo in PRIORITY_FILES:
        ruta = BASE_DIR / archivo
        if ruta.exists():
            const = extraer_constantes(ruta)
            if const:
                constantes_totales.update(const)
    if constantes_totales:
        for k, v in sorted(constantes_totales.items()):
            print(f"   {k} = {v}")
    else:
        print("   ⚠️ No se encontraron constantes en archivos prioritarios.")
    
    # 2. Buscar filtros en todo el código
    print("\n🛡️ FILTROS DETECTADOS EN EL CÓDIGO")
    print("-" * 50)
    todos_filtros = []
    for archivo in BASE_DIR.rglob("*.py"):
        # Saltar directorios de caché o virtual env
        if "venv" in str(archivo) or "__pycache__" in str(archivo):
            continue
        filtros = buscar_filtros_en_archivo(archivo)
        if filtros:
            todos_filtros.extend(filtros)
    
    if todos_filtros:
        # Agrupar por archivo
        por_archivo = defaultdict(list)
        for f in todos_filtros:
            por_archivo[f["archivo"]].append(f)
        
        for arch, flist in por_archivo.items():
            print(f"\n📄 {arch}")
            for f in flist[:5]:  # máx 5 por archivo para no saturar
                print(f"   Línea {f['linea']}: {f['texto']}")
            if len(flist) > 5:
                print(f"   ... y {len(flist)-5} ocurrencias más")
    else:
        print("   ⚠️ No se encontraron filtros explícitos. ¿Los archivos están en el directorio correcto?")
    
    # 3. Filtros conocidos por nombre de módulo
    print("\n🎯 FILTROS ESPECIALIZADOS (por módulo)")
    print("-" * 50)
    modulos_esperados = [
        "filtro_calidad", "filtro_horario", "filtro_eventos",
        "filtro_estadistico", "detector_multitimeframe", "gestor_correlacion"
    ]
    for mod in modulos_esperados:
        arch = BASE_DIR / f"{mod}.py"
        if arch.exists():
            print(f"   ✅ {mod}.py presente")
        else:
            print(f"   ❌ {mod}.py no encontrado")
    
    # 4. Filtros del Centinela (si existe)
    centinela_config = BASE_DIR / "centinela" / "config.py"
    if centinela_config.exists():
        print("\n🚨 CENTINELA (protecciones)")
        print("-" * 50)
        const_centinela = extraer_constantes(centinela_config)
        for k, v in const_centinela.items():
            print(f"   {k} = {v}")
    else:
        print("\n⚠️ No se encontró configuración del Centinela.")
    
    # 5. Resumen de filtros activos en demo (últimos logs)
    print("\n📊 ESTADO RECIENTE (últimos 7 días)")
    print("-" * 50)
    # Intentar leer el resumen diario o los logs de rechazos
    resumen_file = BASE_DIR / "resumen_diario.txt"
    if resumen_file.exists():
        with open(resumen_file, 'r') as f:
            lines = f.readlines()[-20:]  # últimas 20 líneas
            for line in lines:
                if "TOP RECHAZOS" in line or "MATRIX_PAUSA" in line or "FASE_" in line:
                    print(f"   {line.strip()}")
    else:
        # Buscar en logs de Telegram o eventos.log
        evento_log = BASE_DIR / "memoria" / "eventos.log"
        if evento_log.exists():
            with open(evento_log, 'r') as f:
                lines = f.readlines()[-30:]
                rechazos = [l for l in lines if "rechazo" in l.lower() or "bloqueado" in l.lower()]
                for r in rechazos[-5:]:
                    print(f"   {r.strip()}")
        else:
            print("   No se encontraron logs recientes para mostrar rechazos.")
    
    print("\n" + "="*70)
    print("✅ Análisis completado. Revisa los filtros y ajusta los que sean demasiado estrictos.")
    print("="*70)

if __name__ == "__main__":
    main()
