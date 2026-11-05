"""Har 5 daqiqada ishlaydi: admin tugmalarini tekshiradi va tasdiqlangan postni kanalga chiqaradi."""
import tg
from config import get


def handle(cq, admin, channel, done):
    msg = cq.get("message") or {}
    if cq["from"]["id"] != admin:
        tg.answer_callback(cq["id"], "Ruxsat yo'q")
        return
    key = (msg.get("chat", {}).get("id"), msg.get("message_id"))
    if key in done:
        tg.answer_callback(cq["id"])
        return
    done.add(key)

    try:
        action, photo_id, audio_id = (cq.get("data") or "").split(":")
        photo_id, audio_id = int(photo_id), int(audio_id)
    except ValueError:
        tg.answer_callback(cq["id"], "Noto'g'ri tugma")
        return

    ctrl_id = msg.get("message_id")
    if action == "ok":
        try:
            tg.copy_message(channel, admin, photo_id)
            if audio_id:
                tg.copy_message(channel, admin, audio_id)
        except Exception as e:
            tg.send_message(admin, f"❌ Kanalga chiqarib bo'lmadi: {str(e)[:300]}")
            tg.answer_callback(cq["id"], "Xato")
            return
        tg.edit_text(admin, ctrl_id, "✅ Kanalga chiqarildi")
        tg.answer_callback(cq["id"], "Kanalga chiqarildi ✅")
    else:
        tg.edit_text(admin, ctrl_id, "❌ Bekor qilindi")
        tg.answer_callback(cq["id"], "Bekor qilindi")


def main():
    admin = int(get("ADMIN_CHAT_ID"))
    channel = get("CHANNEL_ID")
    updates = tg.get_updates()
    if not updates:
        print("Yangi tugma bosilishi yo'q")
        return
    done = set()
    try:
        for u in updates:
            if "callback_query" in u:
                handle(u["callback_query"], admin, channel, done)
    finally:
        tg.get_updates(offset=updates[-1]["update_id"] + 1)  # ko'rilganlarini tasdiqlash


if __name__ == "__main__":
    main()
