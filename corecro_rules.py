# corecro_rules.py
# CoreCro: órgano consultivo. NUNCA ejecuta. NUNCA ordena.

REGLAS_CORECRO = {
    "puede_opinar": True,
    "puede_recomendar": True,
    "puede_ordenar": False,
    "puede_ejecutar": False,
    "puede_ser_ignorado_por_matrix": True,
    "ignorado_debe_ser_registrado": True
}

def evaluar_contexto(contexto):
    """
    Devuelve una recomendación simple:
    'comprar', 'vender' o 'esperar'
    """
    return "esperar"
