def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo + 1:
        return None

    ganancias = []
    perdidas  = []

    for i in range(1, len(precios)):
        cambio = precios[i] - precios[i-1]
        if cambio > 0:
            ganancias.append(cambio)
            perdidas.append(0)
        else:
            ganancias.append(0)
            perdidas.append(abs(cambio))

    avg_ganancia = sum(ganancias[-periodo:]) / periodo
    avg_perdida  = sum(perdidas[-periodo:])  / periodo

    if avg_perdida == 0:
        return 100

    rs  = avg_ganancia / avg_perdida
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)
