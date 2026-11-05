"""5 ta agent: 1) mavzu qidiruvchi, 2) yozuvchi, 3) rasm, 4) ovoz, 5) sifat nazorati."""
import base64
import json
import re

import anthropic
import requests
from google import genai

from config import CLAUDE_MODEL, ELEVENLABS_MODEL, GEMINI_IMAGE_MODEL, RUBRIC, get

_client = None
WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search"}


def claude():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=get("ANTHROPIC_API_KEY"))
    return _client


def _text(resp):
    return "".join(b.text for b in resp.content if b.type == "text")


def ask(content, tools=None, max_tokens=3000):
    """Claude'ga so'rov. Web search uzoq davom etsa (pause_turn), davom ettiradi."""
    messages = [{"role": "user", "content": content}]
    kwargs = {"tools": tools} if tools else {}
    resp = None
    for _ in range(6):
        resp = claude().messages.create(
            model=CLAUDE_MODEL, max_tokens=max_tokens, messages=messages, **kwargs
        )
        if resp.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": resp.content})
    return _text(resp)


def parse_json(text):
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON topilmadi: {text[:200]}")
    return json.loads(text[start : end + 1])


# ---------- 1-agent: mavzu qidiruvchi ----------
def find_topic(history):
    prompt = f"""Sen "{RUBRIC}" rubrikasi uchun mavzu qidiruvchi agentsan.
Vibecoding kursi kanali yangi o'rganuvchilar uchun. Internetdan (web_search) Claude yoki
AI bilan dasturlashda (vibecoding) foydali, amaliy va yangi bitta maslahat mavzusini top.
Yangi o'rganuvchi bugunoq qo'llay oladigan narsa bo'lsin.

Quyidagi mavzular avval ishlatilgan, takrorlama:
{json.dumps(history[-40:], ensure_ascii=False)}

Oxirgi javobing FAQAT JSON bo'lsin (boshqa matn yo'q):
{{"topic": "mavzu nomi (o'zbekcha)", "angle": "qanday burchakdan yoritish", "key_facts": ["aniq faktlar"], "sources": ["url"]}}"""
    tools = [{**WEB_SEARCH, "max_uses": 5}]
    return parse_json(ask(prompt, tools=tools))


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
    return parse_json(ask(prompt, max_tokens=3000))


# ---------- 3-agent: rasm (Nano Banana, Gemini) ----------
def make_image(prompt):
    client = genai.Client(api_key=get("GEMINI_API_KEY"))
    resp = client.models.generate_content(model=GEMINI_IMAGE_MODEL, contents=[prompt])
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
1. Maslahat faktik jihatdan to'g'rimi? Shubha bo'lsa web_search bilan tekshir.
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
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(image_bytes).decode()}},
        {"type": "text", "text": prompt},
    ]
    verdict = parse_json(ask(content, tools=[{**WEB_SEARCH, "max_uses": 3}], max_tokens=1500))
    issues += verdict.get("issues", [])
    return {"approved": bool(verdict.get("approved")) and not issues, "issues": issues}
