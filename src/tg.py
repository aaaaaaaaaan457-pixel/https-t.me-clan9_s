import html
import json
import re

import requests

from config import get


def _call(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{get('TELEGRAM_BOT_TOKEN')}/{method}"
    r = requests.post(url, data=data, files=files, timeout=90)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"Telegram {method}: {j.get('description')}")
    return j["result"]


def plain(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def send_photo(chat_id, photo_bytes, caption_html):
    files = {"photo": ("post.png", photo_bytes)}
    try:
        res = _call("sendPhoto", {"chat_id": chat_id, "caption": caption_html, "parse_mode": "HTML"}, files)
    except RuntimeError as e:
        if "parse entities" not in str(e):
            raise
        res = _call("sendPhoto", {"chat_id": chat_id, "caption": plain(caption_html)}, files)
    return res["message_id"]


def send_audio(chat_id, audio_bytes, title):
    res = _call(
        "sendAudio",
        {"chat_id": chat_id, "title": title[:60], "performer": "Vibecoding kurs"},
        {"audio": ("maslahat.mp3", audio_bytes, "audio/mpeg")},
    )
    return res["message_id"]


def send_message(chat_id, text, buttons=None):
    data = {"chat_id": chat_id, "text": text}
    if buttons:
        data["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    return _call("sendMessage", data)["message_id"]


def copy_message(to_chat, from_chat, message_id):
    return _call("copyMessage", {"chat_id": to_chat, "from_chat_id": from_chat, "message_id": message_id})


def edit_text(chat_id, message_id, text):
    return _call("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text})


def answer_callback(callback_id, text=""):
    try:  # eski tugma bosilishlari uchun Telegram xato berishi mumkin, e'tibor bermaymiz
        _call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})
    except RuntimeError:
        pass


def get_updates(offset=None):
    data = {"timeout": 0, "allowed_updates": json.dumps(["callback_query"])}
    if offset is not None:
        data["offset"] = offset
    return _call("getUpdates", data)
