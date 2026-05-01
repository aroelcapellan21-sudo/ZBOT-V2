import csv, random, os

# =========================
# CONFIGURACIÓN
# =========================
ARCHIVO = os.path.expanduser("~/bot-padre-v2/data/historico_4h/BTCUSDT_4h.csv")

CAPITAL_INICIAL = 1000.0
RIESGO = 0.01
MONTECARLO_SIMS = 2000

EMA_CORTA = 20
EMA_LARGA = 50
RSI_MIN = 45
RSI_MAX = 55
VENTANA_FASE = 30
UMBRAL_FASE = 2.5

TAKE_PROFIT = 6.0
STOP_LOSS = 3.5
TRAIL_ACT = 1.5
TRAIL_DIST = 1.5

# =========================
# CARGA CSV
# =========================
def cargar_csv(ruta):
    datos=[]
    with open(ruta) as f:
        reader = csv.DictReader(f)
        for r in reader:
            datos.append({
                "close":float(r["close"]),
                "high":float(r["high"]),
                "low":float(r["low"])
            })
    return datos

# =========================
# INDICADORES
# =========================
def calcular_ema(cierres, periodo):
    if len(cierres)<periodo:
        return []
    k=2/(periodo+1)
    ema_list=[]
    ema=sum(cierres[:periodo])/periodo
    ema_list.append(ema)
    for p in cierres[periodo:]:
        ema = p*k + ema*(1-k)
        ema_list.append(ema)
    return [None]*(periodo-1)+[round(e,2) for e in ema_list]

def calcular_rsi(cierres, periodo=14):
    rsi_list=[]
    for i in range(len(cierres)):
        if i<periodo:
            rsi_list.append(None)
            continue
        g=[max(cierres[j]-cierres[j-1],0) for j in range(i-periodo+1,i+1)]
        p=[max(cierres[j-1]-cierres[j],0) for j in range(i-periodo+1,i+1)]
        ag=sum(g)/periodo
        ap=sum(p)/periodo
        if ap==0: rsi_list.append(100)
        else: rsi_list.append(round(100-(100/(1+ag/ap)),2))
    return rsi_list

def detectar_fase(cierres):
    if len(cierres)<VENTANA_FASE: return "DESCONOCIDA"
    cambio=((cierres[-1]-cierres[-VENTANA_FASE])/cierres[-VENTANA_FASE])*100
    if cambio>UMBRAL_FASE: return "ALCISTA"
    elif cambio<-UMBRAL_FASE: return "BAJISTA"
    return "LATERAL"

# =========================
# BACKTEST REAL
# =========================
def backtest(datos):
    cierres=[d["close"] for d in datos]
    highs=[d["high"] for d in datos]
    ema_c_total=calcular_ema(cierres,EMA_CORTA)
    ema_l_total=calcular_ema(cierres,EMA_LARGA)
    rsi_total=calcular_rsi(cierres,14)

    start_idx=EMA_LARGA
    cierres=cierres[start_idx:]
    highs=highs[start_idx:]
    ema_c=ema_c_total[start_idx:]
    ema_l=ema_l_total[start_idx:]
    rsi_vals=rsi_total[start_idx:]

    capital=CAPITAL_INICIAL
    trades=[]
    en_trade=False
    precio_entrada=precio_max=sl_actual=0

    for i in range(len(cierres)):
        fase=detectar_fase(cierres[:i+1])
        precio=cierres[i]
        high=highs[i]

        if not en_trade:
            if fase=="LATERAL":
                if rsi_vals[i] is not None and ema_c[i] is not None and ema_l[i] is not None:
                    diff=abs(ema_c[i]-ema_l[i])/ema_l[i]*100
                    if RSI_MIN<=rsi_vals[i]<=RSI_MAX and diff<2:
                        en_trade=True
                        precio_entrada=precio
                        precio_max=precio
                        sl_actual=precio_entrada*(1-STOP_LOSS/100)
        else:
            if high>precio_max: precio_max=high
            gan_max=(precio_max-precio_entrada)/precio_entrada*100
            if gan_max>=TRAIL_ACT:
                sl_t=precio_max*(1-TRAIL_DIST/100)
                if sl_t>sl_actual: sl_actual=sl_t
            cambio=(precio-precio_entrada)/precio_entrada*100
            if cambio>=TAKE_PROFIT:
                gan=round((TAKE_PROFIT/100)*capital*RIESGO,4)
                capital+=gan
                trades.append({"gan_usd":gan,"metodo":"TP"})
                en_trade=False
                continue
            if precio<=sl_actual:
                gp=round((sl_actual-precio_entrada)/precio_entrada*100,4)
                gu=round((gp/100)*capital*RIESGO,4)
                capital+=gu
                trades.append({"gan_usd":gu,"metodo":"SL/TRAIL"})
                en_trade=False
    return capital,trades

# =========================
# MONTE CARLO
# =========================
def montecarlo(trades,sims=MONTECARLO_SIMS):
    if not trades: return {}
    dds,caps,wrs=[],[],[]
    for _ in range(sims):
        m=random.sample(trades,len(trades))
        cap=CAPITAL_INICIAL
        peak=cap
        ganados=0
        for t in m:
            cap+=t["gan_usd"]
            if t["gan_usd"]>0: ganados+=1
            if cap>peak: peak=cap
            dd=(peak-cap)/peak*100
            dds.append(dd)
        wrs.append(round(ganados/len(m)*100,2))
        caps.append(cap)
    dds.sort()
    caps.sort()
    return {
        "dd_p50":round(dds[int(0.5*sims)],2),
        "dd_p95":round(dds[int(0.95*sims)],2),
        "dd_p99":round(dds[int(0.99*sims)],2),
        "cap_peor":round(caps[int(0.05*sims)],2),
        "cap_mediana":round(caps[int(0.5*sims)],2),
        "cap_mejor":round(caps[int(0.95*sims)],2),
        "aprobacion":round(sum(1 for c in caps if c>CAPITAL_INICIAL)/sims*100,2),
        "wr_promedio":round(sum(wrs)/sims,2)
    }

# =========================
# STRESS TEST HISTÓRICO
# =========================
def stress_test(datos, start,end):
    subset=datos[start:end]
    capital,_=backtest(subset)
    peak=capital
    max_dd=0
    for d in subset:
        if d["close"]>peak: peak=d["close"]
        dd=(peak-d["close"])/peak*100
        if dd>max_dd: max_dd=dd
    return capital,max_dd

# =========================
# WALK FORWARD
# =========================
def walk_forward(datos,train_size=0.5):
    split=int(len(datos)*train_size)
    train=datos[:split]
    test=datos[split:]
    cap_train,_=backtest(train)
    cap_test,_=backtest(test)
    return cap_train,cap_test

# =========================
# MAIN
# =========================
if __name__=="__main__":
    datos=cargar_csv(ARCHIVO)
    print("🔥 VALIDACIÓN COMPLETA 🔥")
    capital,trades=backtest(datos)
    print(f"Capital final: {capital}")
    print(f"Trades realizados: {len(trades)}")

    mc=montecarlo(trades)
    print("\n📊 MONTE CARLO")
    print(mc)

    st_cap, st_dd=stress_test(datos,0,len(datos))
    print("\n💣 STRESS TEST")
    print(f"Capital final: {st_cap}")
    print(f"Max DD: {st_dd:.2f}%")

    wf_train,wf_test=walk_forward(datos)
    print("\n🧪 WALK FORWARD")
    print(f"Train: {wf_train}")
    print(f"Test: {wf_test}")

    veredicto="🟢 ROBUSTA" if mc.get("aprobacion",0)>80 and st_dd<25 and st_cap>CAPITAL_INICIAL else "🟡 ESTRATEGIA INESTABLE"
    print(f"\n⚖️ VEREDICTO FINAL\n{veredicto}")

    print("\n✅ FIN")
