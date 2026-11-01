# Shayx Kutubxonasi / Shaykh's Library

Shayx Muhammad Sodiq Muhammad Yusufning [Hilol Nashr](https://hilolnashr.uz/shayx-kitoblari-uz) tomonidan chop etilgan barcha kitoblari bitta javonda: birinchi nashr yili bo‘yicha, haqiqiy o‘lcham nisbatida.
Every book by Shaykh Muhammad Sodiq Muhammad Yusuf published by Hilol Nashr, on one shelf, by first edition, at real proportions.

**Sayt / Site:** https://asliddinsoliddinovwork-cloud.github.io/Asliddin9903-3d-book-universe/

## Imkoniyatlar / Features
- Bosh ekran: javon. Kitob qirrasini bossangiz, u burilib muqovasini ko‘rsatadi.
- Til/yozuv bo‘yicha filtr (o‘zbek kirill, lotin, qoraqalpoq, rus), yil slayderi, ‹ › va klaviatura strelkalari.
- Tanlangan kitob: yil(lar), sahifa, format, o‘lcham, muqova, ISBN, Hilol Nashr va elektron nashr havolalari, havolani ulashish (`#kitob-slug`).
- “Mening javonim”: yoqqan kitoblarni saqlash (brauzerda).
- Turkumlar (Hadis va Hayot, Tafsiri Hilol, Oltin silsila…), katalog: qidiruv, saralash, filtrlar.
- O‘zbek / ingliz interfeysi. Shrift: Apple qurilmalarida SF Pro, boshqalarida Inter.

## Ma'lumot / Data
| Qiymat | Qayerdan |
|---|---|
| Nom, muallif, yil(lar), sahifa, format, muqova, ISBN, tavsif, muqova rasmi, elektron nashr havolasi | hilolnashr.uz mahsulot sahifasi (`scripts/scrape_hilol.py`) |
| O‘lcham (mm) | Formatdan hisoblanadi, masalan 60×90 1/16 → 215×145 mm (GOST 5773) — `scripts/build_data.py` |
| Qalinlik | Sahifalar × 0,05 mm + muqova (qattiq 4, yumshoq 1,5 mm) — taxminiy |
| Lotin yozuvidagi nom, til, turkum, tur | Nom va URL bo‘yicha qoidalar — `scripts/build_data.py` |

Muqova rasmlari va matnlar mualliflik huquqi Hilol Nashrga tegishli.

## Yangilash / Update
GitHub → **Actions → Update books from Hilol Nashr → Run workflow** (har oyning 1-kuni avtomatik ham ishlaydi). So‘ng sayt o‘zi qayta joylanadi.

## Lokal ishga tushirish / Run locally
```bash
python -m http.server 8000      # http://localhost:8000
pip install pytest && python -m pytest -q tests
```
GitHub Pages: Settings → Pages → Source: **GitHub Actions**.
