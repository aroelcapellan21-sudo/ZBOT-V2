import time, os, subprocess

while True:
    os.system("python3 /home/ariel/bot-padre-v2/diagnostico_bot.py")
    os.system("python3 /home/ariel/bot-padre-v2/monitor_screens.py")
    time.sleep(60)
