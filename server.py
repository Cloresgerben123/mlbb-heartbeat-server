from flask import Flask, request, jsonify
import requests
import time
import threading
from collections import OrderedDict

app = Flask(__name__)

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1472222731792548024/baaTjJ_AQPiHtQQ0Rhf3kRq2DdTuIOkGxayEDSbz2dM1zQod7C2TcEPNjqiTlxNJaAbC"
ACTIVE_TIMEOUT = 120
DISCORD_UPDATE_COOLDOWN = 5

active_users = OrderedDict()
lock = threading.Lock()
last_discord_post = 0
pending_update = False
last_known_count = -1

def clean_stale_users():
    now = time.time()
    with lock:
        stale = [uid for uid, ts in active_users.items() if now - ts > ACTIVE_TIMEOUT]
        for uid in stale:
            del active_users[uid]
        return len(stale) > 0

def get_active_count():
    clean_stale_users()
    return len(active_users)

def send_discord_embed(count):
    color = 0x00FF00 if count > 0 else 0xFF0000
    status_emoji = "🟢" if count > 0 else "🔴"
    
    embed = {
        "embeds": [{
            "title": f"{status_emoji} Live Active Users: {count}",
            "color": color,
            "fields": [
                {"name": "Last Updated", "value": f"<t:{int(time.time())}:R>", "inline": False},
                {"name": "Timeout", "value": f"{ACTIVE_TIMEOUT//60} minutes", "inline": True}
            ],
            "footer": {"text": "Real-time Heartbeat System"}
        }]
    }
    
    try:
        requests.post(DISCORD_WEBHOOK, json=embed)
        print(f"Discord updated: {count} active users")
    except Exception as e:
        print("Discord send error:", e)

def delayed_discord_update():
    global pending_update, last_known_count
    count = get_active_count()
    if count != last_known_count:
        send_discord_embed(count)
        last_known_count = count
    pending_update = False

def trigger_discord_update():
    global pending_update, last_discord_post
    now = time.time()
    with lock:
        if pending_update:
            return
        if now - last_discord_post < DISCORD_UPDATE_COOLDOWN:
            wait = DISCORD_UPDATE_COOLDOWN - (now - last_discord_post)
            threading.Timer(wait, delayed_discord_update).start()
            pending_update = True
        else:
            delayed_discord_update()
            last_discord_post = now

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    data = request.get_json()
    if not data or 'device_id' not in data:
        return jsonify({"error": "Missing device_id"}), 400
    
    device_id = data['device_id']
    now = time.time()
    
    with lock:
        old_count = len(active_users)
        active_users[device_id] = now
        new_count = len(active_users)
    
    if new_count != old_count:
        trigger_discord_update()
    
    return jsonify({"status": "ok"})

def background_cleaner():
    while True:
        time.sleep(10)
        if clean_stale_users():
            trigger_discord_update()

threading.Thread(target=background_cleaner, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
