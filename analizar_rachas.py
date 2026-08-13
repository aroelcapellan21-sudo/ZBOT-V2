import csv
from collections import defaultdict

archivo = "/home/ariel/bot-padre-v2/auditoria.csv"

rachas = defaultdict(list)

with open(archivo) as f:
    reader = csv.DictReader(f)
    for row in reader:
        moneda = row.get("symbol", "?").replace("USDT", "")
        estado = row.get("estado", "").strip().upper()
        if estado in ("TP", "SL"):
            rachas[moneda].append(estado)

print(f"\n{'Moneda':<8} {'Trades':<8} {'WR%':<8} {'MaxRachaLoss':<14} {'MaxRachaWin'}")
print("-"*55)

for moneda, trades in sorted(rachas.items()):
    total = len(trades)
    wins = trades.count("TP")
    wr = round(wins/total*100,1) if total else 0

    max_loss = max_win = cur_loss = cur_win = 0
    for t in trades:
        if t == "SL":
            cur_loss += 1
            cur_win = 0
            max_loss = max(max_loss, cur_loss)
        else:
            cur_win += 1
            cur_loss = 0
            max_win = max(max_win, cur_win)

    print(f"{moneda:<8} {total:<8} {wr:<8} {max_loss:<14} {max_win}")
