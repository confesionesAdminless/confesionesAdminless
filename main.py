# coding=utf-8
from flask import Flask, request
from json import loads as load_json
import os
import re
import requests
import datetime
import math
import redis

# env vars
TOKEN = os.environ["token"]
group_id = int(os.environ["group_id"])
timeout_minutes = int(os.environ["timeout_minutes"])
timeout_max_count = int(os.environ["timeout_max_count"])
redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')

app = Flask(__name__)

def send_message(text, id_, markdown=False):
    url = "https://api.telegram.org/bot{}/".format(TOKEN)
    params = {
        "method": "sendMessage",
        "text": text,
        "chat_id": id_,
    }
    if markdown:
        params["parse_mode"] = "Markdown"
        params["disable_web_page_preview"] = "True"
    return requests.get(url, params=(params))

def send_photo(message_id, photo_id, id_):
    url = "https://api.telegram.org/bot{}/".format(TOKEN)
    params = {
        "method": "sendPhoto",
        "photo": photo_id,
        "chat_id": id_,
        'caption': 'Confesión #{}'.format(message_id)
    }
    return requests.get(url, params=(params))

# Responses
resp = {
    "completed": "Action Completed",
    "ignored": "Action Ignored",
    "error": "Error",
}

# Templates
template = "*Confesión #{} * \n{}"
template_timeout = "Solo se pueden enviar "+str(timeout_max_count)+" confesiones cada "+str(timeout_minutes)+" minuto\nPor favor espere {} segundos..."

message_id = 0
r = redis.from_url(redis_url)
m = r.get("message_id")
if m:
    message_id = int(m)
else:
    r.set("message_id", message_id)

users_timeout = {}

def getTimeout(user_id):
    now = datetime.datetime.now()
    if user_id in users_timeout:
        t = users_timeout[user_id]
        elapsed = (now - t["time"]).seconds
        period = math.floor(t["count"]/timeout_max_count)
        timeout_seconds = timeout_minutes * 60 * period
        if t["timeout"]:
            if (elapsed < timeout_seconds):
                return timeout_seconds - elapsed
            else:
                users_timeout[user_id]["time"] = now
                users_timeout[user_id]["count"] = users_timeout[user_id]["count"] + 1
                users_timeout[user_id]["timeout"] = False
                return False
        else:
            if t["count"] % timeout_max_count != 0:
                users_timeout[user_id]["count"] = users_timeout[user_id]["count"] + 1
                return False
            else:
                if (elapsed < timeout_minutes * 60):
                    users_timeout[user_id]["timeout"] = True
                    return timeout_seconds
                else:
                    users_timeout[user_id]["time"] = now
                    users_timeout[user_id]["count"] = 1
                    return False
    users_timeout[user_id] = {"count": 1, "time": now, "timeout": False}
    return False

@app.route("/Bot", methods=["POST", "GET"])
def telegram_bot():
    try:
        request_data = load_json(request.data)

        chat_type = request_data["message"]["chat"]["type"]
        is_bot = request_data["message"]["from"]["is_bot"]

        if ("edited_message" in request_data) or chat_type != "private" or is_bot:
            return resp["ignored"]

        is_photo = False
        text = ""

        if 'photo' in request_data["message"]:
            text = str(request_data["message"]["photo"][-1]['file_id'])
            is_photo = True
        else:
            text = str(request_data["message"]["text"])

        # Un nuevo mensaje que no viene del grupo
        if not text.startswith("/"):
            global message_id, r
            user_id = int(request_data["message"]["from"]["id"])
            timeout = getTimeout(user_id)
            if not timeout:
                message_id += 1
                r.set("message_id", message_id)
                if is_photo:
                    send_photo(str(message_id), text, group_id)
                else:
                    send_message(template.format(str(message_id), text), group_id, True)
            else:
                send_message(template_timeout.format(str(timeout)), user_id, False)
            return resp["completed"]
        return resp["ignored"]

    except Exception as e:
        print("ERROR EN EL BOT")
        print(e)
        # Si es que se genera un error que no deja aceptar más mensajes
        return resp["error"]

if __name__ == "__main__":
    app.run()
