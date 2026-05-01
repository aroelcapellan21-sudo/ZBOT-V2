#!/usr/bin/env python3
# =========================================
# z_radar.py - Radar de Noticias (Gratis)
# Usa RSS feeds + palabras clave + opcional Google News
# =========================================

import feedparser
import time
from datetime import datetime
import os
import json

# Configuración
RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
    "https://cryptonews.com/news/feed/"
]

PALABRAS_ALCISTAS = [
    "sube", "rally", "explota", "dispara", "record", "maximo",
    "aprueba", "lanza", "adopcion", "etf", "institucional"
]

PALABRAS_BAJISTAS = [
    "baja", "caida", "desploma", "colapsa", "crisis",
    "regulacion", "prohibe", "demanda", "investigacion"
]

MONEDAS = ['BTC', 'ETH', 'SOL', 'BNB', 'AVAX']
ARCHIVO_ESTADO = "estado/z_radar.json"
ARCHIVO_LOG = "radar_noticias.log"

# Para evitar duplicados
vistos = set()

def clasificar_noticia(titulo):
    """Clasifica noticia como ALCISTA/BAJISTA/NEUTRAL basado en palabras clave"""
    titulo_lower = titulo.lower()
    alcistas = sum(1 for p in PALABRAS_ALCISTAS if p in titulo_lower)
    bajistas = sum(1 for p in PALABRAS_BAJISTAS if p in titulo_lower)
    
    if alcistas > bajistas:
        return "ALCISTA"
    elif bajistas > alcistas:
        return "BAJISTA"
    return "NEUTRAL"

def noticia_relevante(titulo):
    """Filtra noticias que mencionen monedas de interés"""
    titulo_upper = titulo.upper()
    for moneda in MONEDAS:
        if moneda in titulo_upper:
            return True
    return False

def obtener_noticias():
    """Obtiene noticias de todos los RSS feeds"""
    nuevas = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entrada in feed.entries[:5]:  # Top 5 por feed
                titulo = entrada.get('title', '')
                link = entrada.get('link', '')
                if titulo and link not in vistos and noticia_relevante(titulo):
                    vistos.add(link)
                    clasificacion = clasificar_noticia(titulo)
                    nuevas.append({
                        "titulo": titulo[:150],
                        "clasificacion": clasificacion,
                        "fuente": url.split('/')[2],
                        "timestamp": datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"Error con {url}: {e}")
    return nuevas

def guardar_estado(noticias):
    """Guarda estado en JSON para el auditor"""
    if not noticias:
        return
    
    os.makedirs(os.path.dirname(ARCHIVO_ESTADO), exist_ok=True)
    
    alcistas = sum(1 for n in noticias if n['clasificacion'] == 'ALCISTA')
    bajistas = sum(1 for n in noticias if n['clasificacion'] == 'BAJISTA')
    
    with open(ARCHIVO_ESTADO, 'w') as f:
        json.dump({
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "noticias": noticias[:10],
            "resumen": {
                "alcistas": alcistas,
                "bajistas": bajistas,
                "sentimiento": "POSITIVO" if alcistas > bajistas else "NEGATIVO" if bajistas > alcistas else "NEUTRAL"
            }
        }, f, indent=2)
    
    # También guardar en log
    with open(ARCHIVO_LOG, 'a') as f:
        for n in noticias:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{n['clasificacion']}] {n['titulo']}\n")

if __name__ == "__main__":
    print("="*50)
    print("📡 z_radar - Radar de Noticias (Gratis)")
    print(f"   Fuentes: {len(RSS_FEEDS)} RSS feeds")
    print("="*50)
    
    while True:
        try:
            noticias = obtener_noticias()
            if noticias:
                guardar_estado(noticias)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(noticias)} noticias nuevas")
            
            time.sleep(300)  # 5 minutos
            
        except KeyboardInterrupt:
            print("\n🛑 z_radar detenido")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)
