# Kitob Javoni / Book Shelf

Dunyoning eng ko‘p sotilgan kitoblari bitta gorizontal javonda, yil bo‘yicha va haqiqiy o‘lcham nisbatida. Kitob qirrasini bossangiz, u burilib muqovasini ko‘rsatadi.
The world’s best-selling books on one horizontal shelf, by year and at real proportions; click a spine to turn the book to its cover.

## Ma'lumot manbalari / Data sources

| Ma'lumot | Manba | Holat |
|---|---|---|
| Kitoblar ro‘yxati, til, yil, sotuv, janr matni | [Wikipedia: List of best-selling books](https://en.wikipedia.org/wiki/List_of_best-selling_books) — 10 mln+ nusxa sotilgan alohida kitoblar (seriyalar emas) | 169 kitob, `data/raw/bestsellers_wikipedia.tsv` |
| Janr guruhlari | Wikipedia janr matnidan `scripts/build_data.py` dagi kalit so‘zlar bo‘yicha | Loyiha talqini; 45 ta kitobda manbada janr yo‘q → "Janr ko‘rsatilmagan" |
| O‘lcham, sahifa soni, muqova | [Open Library](https://openlibrary.org) nashrlari | `Enrich book data` workflow ishga tushirilgach to‘ladi |

* Sotuv raqamlari taxminiy (Wikipedia’dagidek).
* O‘lcham topilmasa, ko‘rinishda 210 × 140 × 30 mm ishlatiladi va kartada **taxminiy** deb yoziladi.
* Muqova rasmlari Open Library’dan olinadi; mualliflik huquqi nashriyotlarga tegishli.

## Ishga tushirish / Run locally

```bash
python -m http.server 8000
# open http://localhost:8000
```
`file://` orqali ochib bo‘lmaydi (brauzer `data/books.json` ni yuklamaydi).

## Ma'lumotni yangilash / Update data

1. GitHub → **Actions → Enrich book data (Open Library) → Run workflow**. O‘lcham va muqovalarni yig‘ib, `data/` va `covers/` ga commit qiladi (~10–15 daqiqa).
2. Ro‘yxatni o‘zgartirish: `data/raw/bestsellers_wikipedia.tsv` ni tahrirlang, so‘ng `python scripts/build_data.py`.

## Testlar / Tests

```bash
pip install pytest
python -m pytest -q tests
```

## GitHub Pages

Settings → Pages → Source: **GitHub Actions**. `main` ga har push saytni yangilaydi.
