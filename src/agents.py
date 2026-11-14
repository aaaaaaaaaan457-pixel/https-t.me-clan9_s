"""5 ta agent (hammasi Gemini'da): 1) mavzu tanlovchi, 2) yozuvchi, 3) rasm, 4) ovoz, 5) sifat nazorati."""
import json
import os
import re
import html
import io
import subprocess
import sys
import time
import urllib.parse

import requests
from google import genai
from google.genai import types

from config import ELEVENLABS_MODEL, ROOT, RUBRIC, get

try:  # jurnalda yozuvlar darhol ko'rinishi uchun
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

_client = None
_available = None
_started = False
_last_post = None
_image_cache = {}
_qc_down = False
IMAGE_FALLBACK = False  # rasm yaratilmasa, oddiy fon ishlatiladi
DEADLINE = time.time() + 600  # 10 daqiqadan keyin to'xtaydi (GitHub 15 daqiqada o'chirmasidan oldin)
QC_DOWN_MSG = "AI tekshiruvi bajarilmadi (Gemini band yoki limit tugagan). Postni o'zingiz diqqat bilan o'qib chiqing."


def _tell(text):
    """Adminga qisqa xabar yuboradi (jarayonni Telegram'dan kuzatish uchun)."""
    try:
        import tg
        tg.send_message(get("ADMIN_CHAT_ID"), text[:400])
    except Exception as e:
        print("Telegram'ga yozib bo'lmadi:", str(e)[:100])


def gemini():
    global _client
    if _client is None:
        _client = genai.Client(api_key=get("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=45000))
    return _client


def retry(fn, tries=2):
    """Faqat 'server band' (503) bo'lsa, 10 soniya kutib bir marta qayta urinadi. Limit (429) bo'lsa, darhol keyingi modelga o'tiladi."""
    for i in range(tries):
        if time.time() > DEADLINE:
            raise TimeoutError("vaqt tugadi (10 daqiqa)")
        try:
            return fn()
        except Exception as e:
            busy = "UNAVAILABLE" in str(e) or "503" in str(e)[:30]
            if i == tries - 1 or not busy:
                raise
            time.sleep(10)


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
    """Eng yangi modeldan boshlab nomzodlar (lite modellar oxirida)."""
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


def generate(kind, contents, config=None, label="", quick=False):
    global _started
    if not _started:
        _started = True
        _tell("⏳ Bot ishga tushdi, post tayyorlanmoqda...")
    names = _candidates(kind)
    if quick:
        names = names[:2]
    rounds = 1 if quick else 2
    last = None
    for rnd in range(rounds):
        for model in names:
            if time.time() > DEADLINE:
                break
            try:
                print(f"Model: {model}")
                return retry(lambda: gemini().models.generate_content(model=model, contents=contents, config=config),
                             tries=1 if quick else 2)
            except Exception as e:
                last = e
                print(f"{model} ishlamadi: {str(e)[:200]}")
                if kind != "image":
                    _tell(f"⚠️ [{label}] {model}: {str(e)[:250]}")
        if rnd < rounds - 1 and time.time() < DEADLINE - 150:
            _tell("⏳ Google band yoki limit tugagan. 40 soniyadan keyin yana urinaman...")
            time.sleep(40)
        else:
            break
    raise RuntimeError(f"[{label}] {str(last)[:350] if last else 'vaqt tugadi (10 daqiqa)'}")


def ask(contents, json_mode=False, label="matn", quick=False):
    config = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None
    return generate("text", contents, config, label, quick).text or ""


def parse_json(text):
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON topilmadi: {text[:200]}")
    return json.loads(text[start : end + 1], strict=False)


POST_RULES = """Qoidalar:
- post_html: Telegram HTML formatida. Faqat <b>, <i>, <code>, <pre> teglari. Matndagi <, >, & belgilarini &lt; &gt; &amp; deb yoz.
- Teglarsiz ko'rinadigan matn 900 belgidan oshmasin.
- voice_text: shu maslahatning og'zaki varianti, o'zbekcha, tabiiy, 20-40 soniya (700 belgigacha). Emoji, hashtag, kod belgilari yo'q.
- image_prompt: inglizcha, post mavzusiga mos zamonaviy texnologik illyustratsiya, 16:9. Rasmda hech qanday yozuv/harf/raqam bo'lmasin.
- title: audio uchun qisqa nom."""


TOPIC_BANK = """1. CLAUDE.md (yoki loyiha qoidalari) fayli: loyiha haqida bir marta yozib qo'ying
2. Avval reja so'rang: "kod yozishdan oldin bosqichma-bosqich reja tuz"
3. Xatoni to'liq nusxalab bering (error matni, qaysi fayl, qaysi qator)
4. Katta vazifani kichik bosqichlarga bo'ling
5. Claude'ga rol bering: "senior dasturchi sifatida tekshir"
6. Misol bering: xohlagan natijangizga 1-2 ta namuna ko'rsating
7. Kontekst bering: tegishli fayl va kodni birga yuboring
8. "Avval menga savol ber" usuli: Claude noaniqliklarni o'zi so'rasin
9. Har bir qatorga izoh yozdirib, kodni tushunib oling
10. Kod yozdirgandan keyin test ham yozdiring
11. Har ishlagan bosqichdan keyin git commit qiling
12. Suhbat uzayib ketsa, yangi chat oching va qisqa xulosa bering
13. Cheklovlarni ayting: til, kutubxona, versiya, "boshqa kutubxona ishlatma"
14. Javob formatini belgilang: ro'yxat, jadval, faqat kod
15. Ishlagan kodni refactor qildiring (soddalashtirish)
16. API kalitlarni kodga yozmang: .env fayldan foydalaning
17. Ikki xil yechim so'rang va ularni taqqoslating
18. "Nega aynan shunday qilding?" deb so'rang
19. UI xatolarida skrinshot yuboring
20. Tez prototip uchun Artifacts'dan foydalaning
21. Xatoni topish: "bosqichma-bosqich fikrla va sababni top"
22. Tayyor kodni "code review" qildiring
23. README yozdirish: loyihani boshqalarga tushuntirish
24. Yaxshi ishlagan promptlarni shablon sifatida saqlang
25. Faqat o'zgargan joyni so'rang: butun faylni qayta yozdirmang
26. Yangi kutubxona o'rganish: "5 qatorli eng oddiy misol ber"
27. Kod ishlamasa: oldin nima kutganingiz va nima bo'lganini yozing
28. Xavfsizlik tekshiruvi: "bu kodda zaif joylar bormi?"
29. "Boshlovchiga tushuntirgandek tushuntir" usuli
30. Loyiha papkalari tuzilmasini Claude bilan birga rejalashtiring"""


# ---------- 1-agent: mavzu tanlovchi (bir so'rovda mavzu va post tayyorlanadi: Gemini chaqiruvlari kamroq) ----------
def find_topic(history):
    style = (ROOT / "prompts" / "style.md").read_text(encoding="utf-8")
    prompt = f"""Sen "{RUBRIC}" rubrikasi uchun mavzu tanlovchi va post yozuvchi agentsan.
Vibecoding kursi kanali yangi o'rganuvchilar uchun: ular Claude va boshqa AI vositalar yordamida dasturlashni o'rganishadi.

Quyidagi ro'yxatdan HALI ISHLATILMAGAN bitta mavzuni tanla (ishlatilganlari pastda). Hammasi ishlatilgan bo'lsa, shunga o'xshash yangi, aniq va amaliy mavzu o'ylab top.
MAVZULAR:
{TOPIC_BANK}

Allaqachon ishlatilgan mavzular (takrorlama):
{json.dumps(history[-40:], ensure_ascii=False)}

Post sifati talablari:
- Umumiy gap emas, ANIQ va amaliy bo'lsin: o'quvchi o'qib bo'lgach, shu zahoti qo'llay olsin.
- Tuzilishi: (1) qiziqtiruvchi qisqa kirish yoki muammo, (2) aniq amaliy qadam, (3) Claude'ga yozish mumkin bo'lgan TAYYOR PROMPT namunasi (<code> ichida).
- Aniq bilmagan mahsulot xususiyatlarini o'ylab topma, umumiy tamoyillarga tayan.

USLUB VA TALABLAR:
{style}

{POST_RULES}

FAQAT JSON qaytar:
{{"topic": "mavzu nomi (o'zbekcha)", "angle": "qanday burchakdan yoritildi", "key_facts": ["aniq faktlar"], "post_html": "...", "voice_text": "...", "image_prompt": "...", "title": "..."}}"""
    data = parse_json(ask(prompt, json_mode=True, label="1-agent"))
    post = {k: data[k] for k in ("post_html", "voice_text", "image_prompt", "title")}
    return {
        "topic": data.get("topic") or "Claude maslahat",
        "angle": data.get("angle", ""),
        "key_facts": data.get("key_facts", []),
        "_post": post,
    }


# ---------- 2-agent: yozuvchi (birinchi variant tayyor; faqat sifat nazorati talab qilsa, qayta yozadi) ----------
def write_post(topic, style, feedback=None):
    global _last_post
    if feedback is None and topic.get("_post"):
        _last_post = topic["_post"]
        return _last_post
    if feedback and feedback.startswith("- AI tekshiruvi") and _last_post:
        return _last_post
    clean = {k: v for k, v in topic.items() if k != "_post"}
    prev = f"\n\nOldingi variant:\n{_last_post['post_html']}" if _last_post else ""
    fb = f"\n\nOldingi urinish sifat nazoratidan o'tmadi. Muammolar:\n{feedback}\nShularni tuzat." if feedback else ""
    prompt = f"""Sen Telegram kanal uchun post yozuvchi agentsan.

USLUB VA TALABLAR:
{style}

MAVZU:
{json.dumps(clean, ensure_ascii=False)}{prev}{fb}

{POST_RULES}

FAQAT JSON qaytar:
{{"post_html": "...", "voice_text": "...", "image_prompt": "...", "title": "..."}}"""
    _last_post = parse_json(ask(prompt, json_mode=True, label="2-agent"))
    return _last_post


# ---------- 3-agent: rasm. 1) Gemini (Nano Banana) 2) bepul kalitsiz xizmat 3) chiroyli sarlavha kartasi ----------
def _ensure_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "Pillow"], check=True)


def _font(size):
    from PIL import ImageFont
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _card_title(post):
    text = ""
    if post and post.get("post_html"):
        plain = html.unescape(re.sub(r"<[^>]+>", "", post["post_html"])).strip()
        text = plain.splitlines()[0] if plain else ""
    if not text and post:
        text = post.get("title", "")
    text = "".join(ch for ch in text if ord(ch) < 0x2100).strip()  # emoji shriftda yo'q
    return text or "Claude maslahat"


def _title_card(post):
    """Rasm yaratilmasa: gradient fon va katta sarlavhali chiroyli karta (bepul, xatosiz)."""
    _ensure_pillow()
    from PIL import Image, ImageDraw
    W, H, M = 1280, 720, 90
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=(int(16 + 70 * t), int(20 + 26 * t), int(52 + 90 * t)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([W - 520, -220, W + 220, 520], fill=(255, 255, 255, 22))
    g.ellipse([W - 330, H - 330, W + 120, H + 120], fill=(255, 210, 90, 28))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)

    d.text((M, 78), "CLAUDE MASLAHATLAR", font=_font(34), fill=(150, 175, 255))
    d.rectangle([M, 138, M + 130, 146], fill=(255, 200, 80))

    title = _card_title(post)
    max_w = W - 2 * M - 120
    for size in range(88, 44, -4):
        font = _font(size)
        lines, line = [], ""
        for word in title.split():
            trial = (line + " " + word).strip()
            if d.textlength(trial, font=font) <= max_w or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        if len(lines) <= 4 and len(lines) * size * 1.25 <= 380:
            break
    y = 190
    for ln in lines[:4]:
        d.text((M, y), ln, font=font, fill=(255, 255, 255))
        y += int(size * 1.25)

    d.text((M, H - 105), "#vibecoding", font=_font(38), fill=(200, 205, 235))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _free_image(prompt):
    """Kalitsiz bepul rasm xizmati (ishlashiga kafolat yo'q). Ishlamasa None."""
    try:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:600])
        r = requests.get(url, params={"width": 1280, "height": 720, "nologo": "true"}, timeout=45)
        ctype = r.headers.get("content-type", "").split(";")[0]
        if r.status_code == 200 and ctype.startswith("image/") and len(r.content) > 5000:
            return r.content, ctype
        print("Bepul rasm xizmati rad etdi:", r.status_code, ctype)
    except Exception as e:
        print("Bepul rasm xizmati ishlamadi:", str(e)[:150])
    return None


def make_image(prompt):
    global IMAGE_FALLBACK
    if prompt in _image_cache:
        data, mime, fallback = _image_cache[prompt]
        IMAGE_FALLBACK = fallback
        return data, mime
    result = None
    try:
        resp = generate("image", [prompt], label="3-agent rasm", quick=True)
        for cand in resp.candidates or []:
            for part in cand.content.parts or []:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    result = (inline.data, inline.mime_type or "image/png", False)
                    break
            if result:
                break
    except Exception as e:
        print("Gemini rasmi ishlamadi:", str(e)[:200])
    if result is None:
        free = _free_image(prompt)
        if free:
            result = (free[0], free[1], False)
    if result is None:
        print("Sarlavha kartasi yaratilmoqda")
        result = (_title_card(_last_post), "image/png", True)
    IMAGE_FALLBACK = result[2]
    _image_cache[prompt] = result
    return result[0], result[1]


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
    global _qc_down
    issues = []
    n = _visible_len(post["post_html"])
    if n > 1000:
        issues.append(f"Post juda uzun ({n} belgi), Telegram rasm izohi limiti 1024.")
    if "#vibecoding" not in post["post_html"]:
        issues.append("#vibecoding hashtagi yo'q.")
    if issues:  # oddiy xatolar bo'lsa, AI'ga murojaat qilmay qayta yozdiramiz
        return {"approved": False, "issues": issues}
    if _qc_down:
        return {"approved": False, "issues": [QC_DOWN_MSG]}

    image_rule = (
        "6. Rasm o'rnida oddiy sarlavha kartasi qo'yilgan. Rasmni tekshirma."
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
    try:
        verdict = parse_json(ask(contents, json_mode=True, label="5-agent", quick=True))
    except Exception as e:
        print("AI tekshiruvi bajarilmadi:", str(e)[:200])
        _qc_down = True
        return {"approved": False, "issues": [QC_DOWN_MSG]}
    found = verdict.get("issues", [])
    return {"approved": bool(verdict.get("approved")) and not found, "issues": found}
