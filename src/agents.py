"""5 ta agent (hammasi Gemini'da): 1) mavzu qidiruvchi, 2) yozuvchi, 3) rasm, 4) ovoz, 5) sifat nazorati."""
import json
import os
import re
import struct
import time
import zlib

import requests
from google import genai
from google.genai import types

from config import ELEVENLABS_MODEL, RUBRIC, get

_client = None
_available = None
IMAGE_FALLBACK = False  # rasm yaratilmasa, oddiy fon ishlatiladi


def gemini():
    global _client
    if _client is None:
        _client = genai.Client(api_key=get("GEMINI_API_KEY"))
    return _client


def retry(fn, tries=2):
    """Limit (429) yoki band server (503) bo'lsa, biroz kutib qayta urinadi."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            fatal = any(s in msg for s in ("NOT_FOUND", "INVALID_ARGUMENT", "PERMISSION_DENIED", "limit: 0"))
            if i == tries - 1 or fatal:
                raise
            print(f"Xato ({msg[:150]}), {25 * (i + 1)} soniyadan keyin qayta uriniladi...")
            time.sleep(25 * (i + 1))


def _available_models():
    """Hisobingiz uchun mavjud model nomlari ro'yxati."""
    global _available
    if _available is None:
        names = []
        try:
            for m in gemini().models.list():
                actions = getattr(m, "supported_actions", None) or []
                if actions and "generateContent" not in actions:
                    continue
                names.append((m.name or "").replace("models/", ""))
        except Exception as e:
            print("Modellar ro'yxatini olib bo'lmadi:", str(e)[:150])
        _available = names
    return _available


def _candidates(kind):
    """Eng yangi modeldan boshlab nomzodlar (lite modellar oxirida: ularning bepul limiti ko'proq)."""
    env = os.getenv("GEMINI_TEXT_MODEL" if kind == "text" else "GEMINI_IMAGE_MODEL")
    if env:
        return [env]
    if kind == "text":
        pattern = r"^gemini-(\d+(?:\.\d+)?)-flash(-lite)?$"
        fallback = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.8-flash-lite"]
    else:
        pattern = r"^gemini-(\d+(?:\.\d+)?)-flash-image(?:-preview)?$"
        fallback = ["gemini-3.1-flash-image", "gemini-2.5-flash-image"]
    found = []
    for name in _available_models():
        m = re.match(pattern, name)
        if m:
            is_lite = bool(m.groups() and len(m.groups()) > 1 and m.group(2))
            found.append((float(m.group(1)), not is_lite, "preview" not in name, name))
    found.sort(reverse=True)
    names = [x[3] for x in found] + [n for n in fallback if n not in [x[3] for x in found]]
    return names[:6]


def generate(kind, contents, config=None, label=""):
    last = None
    for model in _candidates(kind):
        try:
            print(f"Model: {model}")
            return retry(lambda: gemini().models.generate_content(model=model, contents=contents, config=config))
        except Exception as e:
            last = e
            print(f"{model} ishlamadi: {str(e)[:200]}")
    raise RuntimeError(f"[{label}] {str(last)[:350]}")


def ask(contents, search=False, json_mode=False, label="matn"):
    kwargs = {}
    if search:
        kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    if json_mode:
        kwargs["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**kwargs) if kwargs else None
    return generate("text", contents, config, label).text or ""


def parse_json(text):
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON topilmadi: {text[:200]}")
    return json.loads(text[start : end + 1], strict=False)


# ---------- 1-agent: mavzu qidiruvchi (Google qidiruvi bilan, bo'lmasa o'z bilimi bilan) ----------
def find_topic(history):
    prompt = f"""Sen "{RUBRIC}" rubrikasi uchun mavzu qidiruvchi agentsan.
Vibecoding kursi kanali yangi o'rganuvchilar uchun. {{SOURCE}} Claude yoki
AI bilan dasturlashda (vibecoding) foydali, amaliy va yangi bitta maslahat mavzusini top.
Yangi o'rganuvchi bugunoq qo'llay oladigan narsa bo'lsin.

Quyidagi mavzular avval ishlatilgan, takrorlama:
{json.dumps(history[-40:], ensure_ascii=False)}

Oxirgi javobing FAQAT JSON bo'lsin (boshqa matn yo'q):
{{"topic": "mavzu nomi (o'zbekcha)", "angle": "qanday burchakdan yoritish", "key_facts": ["aniq faktlar"], "sources": ["url"]}}"""
    try:
        text = ask(prompt.replace("{SOURCE}", "Internetdan (Google qidiruvi) top:"), search=True, label="1-agent qidiruv")
        return parse_json(text)
    except Exception as e:
        print("Qidiruv bilan ishlamadi, qidiruvsiz urinamiz:", str(e)[:200])
        text = ask(prompt.replace("{SOURCE}", "O'z bilimingdan foydalanib top:"), json_mode=True, label="1-agent")
        return parse_json(text)


# ---------- 2-agent: yozuvchi ----------
def write_post(topic, style, feedback=None):
    fb = f"\n\nOldingi urinish sifat nazoratidan o'tmadi. Muammolar:\n{feedback}\nShularni tuzat." if feedback else ""
    prompt = f"""Sen Telegram kanal uchun post yozuvchi agentsan.

USLUB VA TALABLAR:
{style}

MAVZU (tadqiqotchi agentdan):
{json.dumps(topic, ensure_ascii=False)}
{fb}

Qoidalar:
- post_html: Telegram HTML formatida. Faqat <b>, <i>, <code>, <pre> teglari. Matndagi <, >, & belgilarini &lt; &gt; &amp; deb yoz.
- Teglarsiz ko'rinadigan matn 900 belgidan oshmasin.
- voice_text: shu maslahatning og'zaki varianti, o'zbekcha, tabiiy, 20-40 soniya (700 belgigacha). Emoji, hashtag, kod belgilari yo'q.
- image_prompt: inglizcha, post mavzusiga mos zamonaviy texnologik illyustratsiya, 16:9. Rasmda hech qanday yozuv/harf/raqam bo'lmasin.
- title: audio uchun qisqa nom.

FAQAT JSON qaytar:
{{"post_html": "...", "voice_text": "...", "image_prompt": "...", "title": "..."}}"""
    return parse_json(ask(prompt, json_mode=True, label="2-agent"))


# ---------- 3-agent: rasm (Nano Banana, Gemini). Bo'lmasa oddiy fon ----------
def _placeholder_png(w=1280, h=720):
    rows = []
    for y in range(h):
        t = y / (h - 1)
        r, g, b = int(20 + 30 * t), int(25 + 60 * t), int(60 + 120 * t)
        rows.append(b"\x00" + bytes([r, g, b]) * w)
    raw = b"".join(rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def make_image(prompt):
    global IMAGE_FALLBACK
    try:
        resp = generate("image", [prompt], label="3-agent rasm")
        for cand in resp.candidates or []:
            for part in cand.content.parts or []:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    IMAGE_FALLBACK = False
                    return inline.data, (inline.mime_type or "image/png")
        raise RuntimeError("Gemini rasm qaytarmadi")
    except Exception as e:
        print("Rasm yaratilmadi, oddiy fon ishlatiladi:", str(e)[:200])
        IMAGE_FALLBACK = True
        return _placeholder_png(), "image/png"


# ---------- 4-agent: ovoz (ElevenLabs) ----------
def make_audio(text):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{get('ELEVENLABS_VOICE_ID')}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": get("ELEVENLABS_API_KEY")},
        json={"text": text, "model_id": ELEVENLABS_MODEL},
        timeout=180,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
    return r.content


# ---------- 5-agent: sifat nazorati ----------
def _visible_len(html_text):
    return len(re.sub(r"<[^>]+>", "", html_text))


def review(post, image_bytes, mime):
    issues = []
    n = _visible_len(post["post_html"])
    if n > 1000:
        issues.append(f"Post juda uzun ({n} belgi), Telegram rasm izohi limiti 1024.")
    if "#vibecoding" not in post["post_html"]:
        issues.append("#vibecoding hashtagi yo'q.")

    image_rule = (
        "6. Rasm yaratilmadi, oddiy fon qo'yilgan. Rasmni tekshirma."
        if IMAGE_FALLBACK
        else "6. Rasm mavzuga mosmi, g'alati/buzilgan yozuv yoki xunuk detallar yo'qmi?"
    )
    prompt = f"""Sen "{RUBRIC}" rubrikasi uchun qattiq sifat nazoratchisisan.
Postni tekshir:
1. Maslahat faktik jihatdan to'g'rimi?
2. Kod misoli (bo'lsa) ishlaydimi va to'g'ri yozilganmi?
3. O'zbek tili tabiiy va xatosizmi?
4. Yangi o'rganuvchilar uchun tushunarli, qisqa, amaliymi? Sarlavha va 3-4 emoji, oxirida hashtaglar bormi?
5. Telegram HTML teglari to'g'ri yopilganmi (faqat b, i, code, pre)?
{image_rule}

POST:
{post['post_html']}

OVOZ MATNI:
{post['voice_text']}

FAQAT JSON qaytar: {{"approved": true/false, "issues": ["aniq muammolar"]}}
Faqat jiddiy muammo bo'lsa approved=false qil."""
    contents = [prompt] if IMAGE_FALLBACK else [types.Part.from_bytes(data=image_bytes, mime_type=mime), prompt]
    verdict = parse_json(ask(contents, json_mode=True, label="5-agent"))
    issues += verdict.get("issues", [])
    return {"approved": bool(verdict.get("approved")) and not issues, "issues": issues}
