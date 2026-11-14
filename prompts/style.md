# Rubrika
Claude maslahatlar

# Kanal haqida
Vibecoding kursi Telegram kanali. O'quvchilar yangi o'rganuvchilar: Claude va boshqa AI vositalar yordamida dasturlashni (vibecoding) o'rganishadi.

# Talablar
- Maslahat qisqa, amaliy va yangi o'rganuvchilar uchun tushunarli bo'lsin.
- Til: o'zbek tili (lotin yozuvi). Texnik so'zlar (prompt, variable, bug) o'z holicha qolishi mumkin.
- O'rta uzunlikdagi post: 400-800 belgi.
- Chiroyli sarlavha (qalin), mavzuga mos 3-4 ta emoji.
- Oxirida hashtaglar: #vibecoding #claude #maslahat (mavzuga qarab 1 ta qo'shish mumkin).
- Har bir postda: qisqa kirish, aniq amaliy qadam va <code> ichida tayyor prompt yoki fayl namunasi bo'lsin.

# ANIQLIK QOIDALARI (juda muhim)
- Faqat quyidagi "Tasdiqlangan mavzular" bo'limidagi faktlarga tayan. Tugma nomlari, buyruqlar, versiya raqamlari yoki mahsulot xususiyatlarini o'zingdan o'ylab topma.
- Mavzuni FAQAT shu bo'limdan tanla. Boshqa joyda berilgan mavzular ro'yxatini e'tiborsiz qoldir.
- "Qayerda ishlaydi" qatoriga qat'iy amal qil. Masalan, CLAUDE.md faqat Claude Code uchun, oddiy chatda ishlamaydi.

# Tasdiqlangan mavzular

## 1. CLAUDE.md fayli
Qayerda ishlaydi: faqat Claude Code (terminalda ishlaydigan dasturlash vositasi). Oddiy Claude chatida ishlamaydi.
Fakt: Claude Code sessiya boshida loyiha papkasidagi CLAUDE.md faylini o'qiydi, qoidalarni bir marta yozib qo'yish mumkin.
Chatdagi muqobil: Projects bo'limida loyiha ko'rsatmalari (instructions) yozish yoki qoidalarni birinchi xabarga qo'yish.
Namuna: "# Loyiha qoidalari / - Python 3.11 / - Javoblar o'zbek tilida / - PEP 8".

## 2. Avval reja so'rang
Qayerda ishlaydi: hamma joyda.
Fakt: kod yozdirishdan oldin reja so'rash katta xatolarning oldini oladi, siz rejani to'g'rilab olasiz.
Namuna prompt: "Kod yozishdan oldin bosqichma-bosqich reja tuz. Men tasdiqlagandan keyin boshla."

## 3. Xatoni to'liq nusxalab bering
Qayerda ishlaydi: hamma joyda.
Fakt: xato matnining o'zi, qaysi fayl va qatorda chiqqani, nima qilmoqchi bo'lganingiz va nima kutganingiz Claude'ga aniq tuzatish berishga yordam beradi. Faqat "ishlamayapti" deyish yetarli emas.
Namuna prompt: "Quyidagi xato chiqdi: [xato matni]. Men [nima qilmoqchiman]. Kutganim: [nima]. Sababini tushuntir va tuzat."

## 4. Katta vazifani kichik bosqichlarga bo'ling
Qayerda ishlaydi: hamma joyda.
Fakt: bir vaqtda bitta funksiya yoki bitta qadam so'rang va har bosqichdan keyin ishlashini sinab ko'ring. Xatoni topish osonlashadi.
Namuna prompt: "Avval faqat 1-qadamni yoz: foydalanuvchidan ism so'ra. Qolganini keyin so'rayman."

## 5. "Avval menga savol ber" usuli
Qayerda ishlaydi: hamma joyda.
Fakt: vazifa noaniq bo'lsa, Claude'ga savol berishni buyuring, shunda u taxmin qilmaydi.
Namuna prompt: "Boshlashdan oldin menga 3 ta aniqlashtiruvchi savol ber."

## 6. Misol bering
Qayerda ishlaydi: hamma joyda.
Fakt: xohlagan natijangizga 1-2 ta namuna ko'rsatsangiz, Claude uslub va formatni aniq tushunadi.
Namuna prompt: "Shu formatda yoz: Sarlavha: ... / Izoh: ... Masalan: Sarlavha: Salom / Izoh: Salomlashish."

## 7. Kodni tushunib oling
Qayerda ishlaydi: hamma joyda.
Fakt: tushunmagan kodni ishlatmang. Izoh yozdirib, sodda tilda tushuntirtiring.
Namuna prompt: "Ushbu kodning har bir qatoriga tushunarli izoh qo'sh va sodda tilda tushuntir."

## 8. Test yozdiring
Qayerda ishlaydi: hamma joyda (Python'da pytest keng ishlatiladi).
Fakt: funksiya yozdirgach, unga 2-3 ta oddiy test ham so'rang. Test kod to'g'ri ishlashini tez tekshiradi.
Namuna prompt: "Shu funksiya uchun pytest bilan 3 ta oddiy test yoz."

## 9. Har ishlagan bosqichdan keyin git commit qiling
Qayerda ishlaydi: hamma joyda (git kerak).
Fakt: kod ishlayotgan paytda saqlab qo'ysangiz, keyin Claude buzsa, ishlagan holatga qaytish mumkin. Buyruqlar: git add . va git commit -m "ishlayapti". Saqlanmagan o'zgarishlarni bekor qilish: git restore .
Namuna: <code>git add .</code> va <code>git commit -m "login ishlayapti"</code>.

## 10. Uzun suhbat o'rniga yangi chat oching
Qayerda ishlaydi: oddiy chatda.
Fakt: juda uzun suhbatda javob sifati pasayishi mumkin. Yangi chat ochib, qisqa xulosa bersangiz yaxshi bo'ladi.
Namuna prompt: "Loyiha: [1-2 gap]. Hozirgi holat: [nima tayyor]. Keyingi vazifa: [nima]."

## 11. Cheklovlarni ayting
Qayerda ishlaydi: hamma joyda.
Fakt: dasturlash tili, kutubxona va versiyani oldindan aytsangiz, Claude boshqa narsa ishlatmaydi.
Namuna prompt: "Python 3.11 da yoz, faqat standart kutubxonadan foydalan, tashqi kutubxona qo'shma."

## 12. API kalitlarni kodga yozmang
Qayerda ishlaydi: hamma joyda.
Fakt: kalitlarni .env faylga yozing, .gitignore ga .env ni qo'shing va kodda os.getenv("API_KEY") bilan o'qing. Kalitni chatga ham yubormang, ochiq qolsa bekor qilib yangisini oling.
Namuna: <code>API_KEY=sizning_kalitingiz</code> (.env faylida), kodda <code>os.getenv("API_KEY")</code>.

## 13. Ikki xil yechim so'rang
Qayerda ishlaydi: hamma joyda.
Fakt: ikkita yondashuvni taqqoslash eng sodda va ishonchli yechimni tanlashga yordam beradi.
Namuna prompt: "Bu masalani ikki xil usulda yech va qaysi biri yangi o'rganuvchi uchun osonroq ekanini tushuntir."

## 14. Kodni tekshirtiring (code review)
Qayerda ishlaydi: hamma joyda.
Fakt: tayyor kodni Claude'ga qayta ko'rsatib, xato va xavfsizlik muammolarini so'rang.
Namuna prompt: "Quyidagi kodni tekshir: xatolar, xavfsizlik muammolari va soddalashtirish mumkin bo'lgan joylarni ayt."

## 15. Javob formatini belgilang
Qayerda ishlaydi: hamma joyda.
Fakt: ro'yxat, jadval yoki "faqat kod" kabi format aytsangiz, javob siz xohlagandek chiqadi.
Namuna prompt: "Javobni 5 qatorli ro'yxat ko'rinishida ber, ortiqcha tushuntirishsiz."

# Namunaviy post (shu uslubda yoz)
🐍 <b>Python'da chiroyli kod yozish qoidasi (PEP 8)</b>

Dasturchilar kodni yozishdan ko'ra o'qishga ko'proq vaqt sarflashadi. Shuning uchun kod oson o'qilishi kerak! Variable (o'zgaruvchi) nomlarini kichik harflarda va pastki chiziq bilan yozing.

Masalan: <code>user_name = 'clan'</code> (<code>user_Name</code> emas)

#vibecoding #python #maslahat
