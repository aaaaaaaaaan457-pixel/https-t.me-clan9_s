"""5 ta agent (hammasi Gemini'da): 1) mavzu qidiruvchi, 2) yozuvchi, 3) rasm, 4) ovoz, 5) sifat nazorati."""
import json
import os
import re
import time

import requests
from google import genai
from google.genai import types

from config import ELEVENLABS_MODEL, GEMINI_IMAGE_MODEL, RUBRIC, get

TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-flash-latest").                                                                TEXT_MODEL = "gemini-2.5-flash"    

_client = None


def gemini():
    global _client
    if _client is None:
        _client = genai.Client(api_key=get("GEMINI_API_KEY"))
    return _client


def retry(fn, tries=4):
    """Bepul tarifda limit (429) yoki band server (503) bo'lsa, biroz kutib qayta urinadi."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"Xato ({e}), {20 * (i + 1)} soniyadan keyin qayta uriniladi...")
            time.sleep(20 * (i + 1))


def ask(contents, search=False, json_mode=False):
    kwargs = {}
    if search:
        kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    if json_mode:
        kwargs["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**kwargs) if kwargs else None
    resp = retry(lambda: gemini().models.generate_content(model=TEXT_MODEL, contents=contents, config=config))
    return resp.text or ""


def parse_json(text):
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON topilmadi: {text[:200]}")
    return json.loads(text[start : end + 1], strict=False)


# ---------- 1-agent: mavzu qidiruvchi (Google qidiruvi bilan) ----------
def find_topic(history):
    prompt = f"""Sen "{RUBRIC}" rubrikasi uchun mavzu qidiruvchi agentsan.
Vibecoding kursi kanali yangi o'rganuvchilar uchun. Internetdan (Google qidiruvi) Claude yoki
AI bilan dasturlashda (vibecoding) foydali, amaliy va yangi bitta maslahat mavzusini top.
Yangi o'rganuvchi bugunoq qo'llay oladigan narsa bo'lsin.

Quyidagi mavzular avval ishlatilgan, takrorlama:
{json.dumps(history[-40:], ensure_ascii=False)}

Oxirgi javobing FAQAT JSON bo'lsin (boshqa matn yo'q):
{{"topic": "mavzu nomi (o'zbekcha)", "angle": "qanday burchakdan yoritish", "key_facts": ["aniq faktlar"], "sources": ["url"]}}"""
    return parse_json(ask(prompt, search=True))


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
    return parse_json(ask(prompt, json_mode=True))


# ---------- 3-agent: rasm (Nano Banana, Gemini) ----------
def make_image(prompt):
    resp = retry(lambda: gemini().models.generate_content(model=GEMINI_IMAGE_MODEL, contents=[prompt]))
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data, (inline.mime_type or "image/png")
    raise RuntimeError("Gemini rasm qaytarmadi")


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

    prompt = f"""Sen "{RUBRIC}" rubrikasi uchun qattiq sifat nazoratchisisan.
Postni va rasmni tekshir:
1. Maslahat faktik jihatdan to'g'rimi?
2. Kod misoli (bo'lsa) ishlaydimi va to'g'ri yozilganmi?
3. O'zbek tili tabiiy va xatosizmi?
4. Yangi o'rganuvchilar uchun tushunarli, qisqa, amaliymi? Sarlavha va 3-4 emoji, oxirida hashtaglar bormi?
5. Telegram HTML teglari to'g'ri yopilganmi (faqat b, i, code, pre)?
6. Rasm mavzuga mosmi, g'alati/buzilgan yozuv yoki xunuk detallar yo'qmi?

POST:
{post['post_html']}

OVOZ MATNI:
{post['voice_text']}

FAQAT JSON qaytar: {{"approved": true/false, "issues": ["aniq muammolar"]}}
Faqat jiddiy muammo bo'lsa approved=false qil."""
    contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime), prompt]
    verdict = parse_json(ask(contents, json_mode=True))
    issues += verdict.get("issues", [])
    return {"approved": bool(verdict.get("approved")) and not issues, "issues": issues}
