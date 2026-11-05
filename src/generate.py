"""Har kuni ishlaydi: post yaratadi va ADMIN chatga tasdiqlash uchun yuboradi."""
import json
import traceback

import agents
import tg
from config import MAX_TRIES, ROOT, get

HISTORY = ROOT / "data" / "history.json"


def load_history():
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def run(admin):
    history = load_history()
    style = (ROOT / "prompts" / "style.md").read_text(encoding="utf-8")

    print("1-agent: mavzu qidirilmoqda...")
    topic = agents.find_topic(history)
    print("Mavzu:", topic["topic"])

    feedback, post, img, verdict = None, None, None, None
    for attempt in range(1, MAX_TRIES + 1):
        print(f"2-agent: post yozilmoqda (urinish {attempt})...")
        post = agents.write_post(topic, style, feedback)
        print("3-agent: rasm yaratilmoqda...")
        img, mime = agents.make_image(post["image_prompt"])
        print("5-agent: sifat nazorati...")
        verdict = agents.review(post, img, mime)
        print("Natija:", verdict)
        if verdict["approved"]:
            break
        feedback = "\n".join(f"- {i}" for i in verdict["issues"])

    audio = None
    try:
        print("4-agent: audio yaratilmoqda...")
        audio = agents.make_audio(post["voice_text"])
    except Exception as e:  # audio bo'lmasa ham post ketaveradi
        print("Audio xatosi:", e)

    photo_id = tg.send_photo(admin, img, post["post_html"])
    audio_id = tg.send_audio(admin, audio, post["title"]) if audio else 0

    note = "✅ Sifat nazoratidan o'tdi" if verdict["approved"] else "⚠️ Sifat nazoratidan o'tmadi:\n" + "\n".join(verdict["issues"])
    if not audio:
        note += "\n🔇 Audio yaratilmadi (kanalga faqat rasm va matn ketadi)"
    tg.send_message(
        admin,
        f"Kanalga chiqarilsinmi?\n\n{note}",
        buttons=[[
            {"text": "✅ Chiqarilsin", "callback_data": f"ok:{photo_id}:{audio_id}"},
            {"text": "❌ Bekor qilish", "callback_data": f"no:{photo_id}:{audio_id}"},
        ]],
    )

    history.append(topic["topic"])
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    admin = get("ADMIN_CHAT_ID")
    try:
        run(admin)
    except Exception as e:
        traceback.print_exc()
        try:
            tg.send_message(admin, f"❌ Post yaratishda xato:\n{str(e)[:500]}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
