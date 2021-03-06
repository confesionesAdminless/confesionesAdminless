# coding=utf-8
from flask import Flask, request
from json import loads
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
api_url = "https://api.telegram.org/bot{}/".format(TOKEN)

app = Flask(__name__)

def send_message(text, chat_id):
    params = {
        "method": "sendMessage",
        "chat_id": chat_id,
        "text": text,
    }
    return requests.get(api_url, params=(params))

def send_photo(message_id, photo_id, caption=""):
    params = {
        "method": "sendPhoto",
        "chat_id": group_id,
        "photo": photo_id,
        'caption': template.format(message_id, caption)
    }
    return requests.get(api_url, params=(params))

def send_video(message_id, video_id, caption=""):
    params = {
        "method": "sendVideo",
        "chat_id": group_id,
        "video": video_id,
        'caption': template.format(message_id, caption)
    }
    return requests.get(api_url, params=(params))

def send_audio(message_id, audio_id, caption=""):
    params = {
        "method": "sendAudio",
        "chat_id": group_id,
        "audio": audio_id,
        'caption': template.format(message_id, caption)
    }
    return requests.get(api_url, params=(params))

def send_voice(message_id, voice_id, caption=""):
    params = {
        "method": "sendVoice",
        "chat_id": group_id,
        "voice": voice_id,
        'caption': template.format(message_id, caption)
    }
    return requests.get(api_url, params=(params))

def send_sticker(sticker_id):
    params = {
        "method": "sendSticker",
        "chat_id": group_id,
        "sticker": sticker_id,
    }
    return requests.get(api_url, params=(params))

def send_animation(animation_id):
    params = {
        "method": "sendAnimation",
        "chat_id": group_id,
        "animation": animation_id,
    }
    return requests.get(api_url, params=(params))

def send_poll(message_id, poll_data):
    poll_data["method"] = "sendPoll"
    poll_data["chat_id"] = group_id
    poll_data["question"] = template.format(message_id, poll_data["question"])
    poll_data["options"] = [op["text"] for op in poll_data["options"]]
    return requests.post(api_url, json=poll_data)

def send_dice(dice_emoji):
    params = {
        "method": "sendDice",
        "chat_id": group_id,
        "emoji": dice_emoji,
    }
    return requests.get(api_url, params=(params))

# Responses
resp = {
    "completed": "Action Completed",
    "ignored": "Action Ignored",
    "error": "Error",
}

# Templates
template = "Confesión #C{} \n{}"
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

def getType(data):
    msg = data["message"]

    # Ignorar bots, mensajes publicos y mensajes editados
    if ("edited_message" in data) or msg["chat"]["type"] != "private" or msg["from"]["is_bot"]:
        return False

    if "text" in msg: return "text"
    if "photo" in msg: return "photo"
    if "video" in msg: return "video"
    if "audio" in msg: return "audio"
    if "voice" in msg: return "voice"
    if "sticker" in msg: return "sticker"
    if "animation" in msg: return "animation"
    if "poll" in msg: return "poll"
    if "dice" in msg: return "dice"

    return False

@app.route("/Bot", methods=["POST", "GET"])
def telegram_bot():
    global message_id, r
    try:
        request_data = loads(request.data)
        msg_type = getType(request_data)
        if not msg_type: return resp["ignored"]

        msg = request_data["message"]

        user_id = int(msg["from"]["id"])
        timeout = getTimeout(user_id)
        if timeout:
            send_message(template_timeout.format(str(timeout)), user_id)
            return resp["completed"]

        if msg_type == "text":
            text = str(msg["text"])
            # Ignorar comandos
            if text.startswith("/"): return resp["ignored"]
            message_id += 1
            r.set("message_id", message_id)
            send_message(template.format(str(message_id), text), group_id)

        elif msg_type == "photo":
            photo_id = msg["photo"][-1]['file_id']
            caption = msg["caption"] if "caption" in msg else ""
            message_id += 1
            r.set("message_id", message_id)
            send_photo(str(message_id), photo_id, caption)
        
        elif msg_type == "video":
            video_id = msg["video"]['file_id']
            caption = msg["caption"] if "caption" in msg else ""
            message_id += 1
            r.set("message_id", message_id)
            send_video(str(message_id), video_id, caption)
        
        elif msg_type == "audio":
            audio_id = msg["audio"]['file_id']
            caption = msg["caption"] if "caption" in msg else ""
            message_id += 1
            r.set("message_id", message_id)
            send_audio(str(message_id), audio_id, caption)
        
        elif msg_type == "voice":
            voice_id = msg["voice"]['file_id']
            caption = msg["caption"] if "caption" in msg else ""
            message_id += 1
            r.set("message_id", message_id)
            send_voice(str(message_id), voice_id, caption)

        elif msg_type == "sticker":
            sticker_id = msg["sticker"]["file_id"]
            send_sticker(sticker_id)

        elif msg_type == "animation":
            animation_id = msg["animation"]["file_id"]
            send_animation(animation_id)
        
        elif msg_type == "poll":
            poll_data = msg["poll"]
            message_id += 1
            r.set("message_id", message_id)
            if "id" in poll_data: del poll_data["id"]
            send_poll(str(message_id), poll_data)

        elif msg_type == "dice":
            dice = msg["dice"]["emoji"]
            send_dice(dice)

        return resp["completed"]

    except Exception as e:
        print("ERROR EN EL BOT: ", e)
        return resp["error"]

if __name__ == "__main__":
    app.run()
