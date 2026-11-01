"""Build data/books.json from data/raw/hilol_products.json (written by scrape_hilol.py).

Usage:  python scripts/build_data.py

Everything published comes from the publisher's page. Derived values are labelled:
  * size_method "format": trimmed page size computed from the printed paper format
    (e.g. "60×90 1/16" -> sheet 600×900 mm folded 4 times = 150×225 mm, minus trim 10/5 mm = 215×145 mm;
    this reproduces the GOST 5773 sizes, e.g. 84×108/32 -> 200×130, 70×100/16 -> 240×170).
  * size_method "title_cm": size printed in the product title, e.g. "17x25 см".
  * thickness_method "pages": pages × 0.05 mm (0.1 mm per leaf) + cover boards (hard 4, soft 1.5, unknown 3 mm).
  * lang / series / kind: classified from the title, URL and details by the rules below.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "hilol_products.json"
OUT = ROOT / "data" / "books.json"

LANGS = {
    "uz-cyrl": {"uz": "O‘zbek (kirill)", "en": "Uzbek (Cyrillic)"},
    "uz-latn": {"uz": "O‘zbek (lotin)", "en": "Uzbek (Latin)"},
    "kaa": {"uz": "Qoraqalpoq", "en": "Karakalpak"},
    "ru": {"uz": "Rus", "en": "Russian"},
}
# (key, uz, en, regex on title; group 1 = volume number if any)
SERIES = [
    ("hadis-va-hayot", "Hadis va Hayot", "Hadith and Life", r"(?:Ҳадис ва Ҳаёт|Hadis va Hayot|Хадисы и Жизнь|Ҳәдис ҳәм Турмыс)\s*(\d+)?"),
    ("tafsiri-hilol", "Tafsiri Hilol", "Tafsiri Hilol", r"(?:Тафсири Ҳилол|Tafsiri Hilol|Тафсир Хилал)\s*(\d+)?"),
    ("oltin-silsila", "Oltin silsila", "The Golden Chain", r"(?:Олтин силсила|Oltin silsila).*?(\d+)-"),
    ("mominning", "“Mo‘minning…” turkumi", "“The Believer's…” series", r"(?:Мўминнинг|Mo‘minning|Мөминниң)"),
]

CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "’", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ё": "yo", "ў": "o‘", "қ": "q", "ғ": "g‘", "ҳ": "h",
}
VOWELS = set("аеёиоуўэюяaeiou")


def to_latin(text: str) -> str:
    """Uzbek Cyrillic -> Uzbek Latin (1995 alphabet). 'е' is 'ye' at word start / after a vowel."""
    out = []
    for i, ch in enumerate(text):
        low = ch.lower()
        if low == "е":
            prev = text[i - 1].lower() if i else " "
            lat = "ye" if (not prev.isalpha() or prev in VOWELS or prev == "ъ") else "e"
        elif low in CYR2LAT:
            lat = CYR2LAT[low]
        else:
            out.append(ch)
            continue
        if ch != low and lat:
            nxt = text[i + 1] if i + 1 < len(text) else " "
            lat = lat.upper() if (nxt.isupper() and len(lat) > 1) else lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


def strip_quotes(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("«", "").replace("»", "").replace('"', "")).strip()


def detect_lang(title: str, url: str) -> str:
    slug = url.lower()
    if re.search(r"(-qr\b|qoraqalpoq)", slug) or "қорақалпоқ" in title.lower() or re.search(r"[әөүңӘӨҮҢ]", title):
        return "kaa"
    if not re.search(r"[А-Яа-яЁёЎўҚқҒғҲҳ]", title):
        return "uz-latn"
    if "rus" in slug or (not re.search(r"[ЎўҚқҒғҲҳ]", title) and re.search(r"(ы|\bи\b|том|Книга|джуз)", title)):
        return "ru"
    return "uz-cyrl"


def detect_series(title: str) -> dict | None:
    for key, _, _, rx in SERIES:
        m = re.search(rx, title)
        if m:
            num = m.group(1) if m.groups() and m.group(1) else None
            return {"key": key, "number": int(num) if num else None}
    return None


def detect_kind(title: str, url: str) -> str:
    t = title.lower()
    if re.search(r"audio|mp3|usb|флеш|диск|disk", t):
        return "audio"
    if "product_id=" in url or "чегирма" in t:
        return "bundle"
    if re.search(r"қутида|qutida|тўплами|to‘plami|жилдлик|\d\s*,\s*\d\s*,\s*\d|\b[2-9]\s*жилд\b|\d+\s*та китоб|\d+\s*[-–]\s*\d+\s*-?й?\s*том", t):
        return "set"
    return "book"


def years_of(text: str | None) -> list[int]:
    return sorted({int(y) for y in re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", text or "")})


def pages_of(text: str | None) -> int | None:
    m = re.search(r"(\d{2,4})\s*(?:бет|bet|стр|с\.|page)", text or "", re.I)
    return int(m.group(1)) if m else None


def size_from_format(text: str | None) -> tuple[int, int] | None:
    """'60×90 1/16' -> (215, 145) = (height, width) mm. Only power-of-two folds are supported."""
    m = re.search(r"(\d{2,3})\s*[×xхX]\s*(\d{2,3})\s*(?:1\s*)?/\s*(\d{1,3})", text or "")
    if not m:
        return None
    a, b, n = int(m.group(1)) * 10, int(m.group(2)) * 10, int(m.group(3))
    folds = math.log2(n) if n > 0 else 0.5
    if folds != int(folds) or not 2 <= folds <= 7:
        return None
    sides = [a, b]
    for _ in range(int(folds)):
        sides.sort()
        sides[1] /= 2
    w, h = sorted(sides)
    return round(h - 10), round(w - 5)


def size_from_title(title: str) -> tuple[int, int] | None:
    m = re.search(r"(\d{1,2}(?:[.,]\d)?)\s*[×xх]\s*(\d{1,2}(?:[.,]\d)?)\s*см", title)
    if not m:
        return None
    a, b = (float(x.replace(",", ".")) * 10 for x in m.groups())
    return round(max(a, b)), round(min(a, b))


def binding_of(text: str | None) -> str | None:
    t = (text or "").lower()
    if re.search(r"қаттиқ|qattiq|тв[её]рд|қатты", t):
        return "hard"
    if re.search(r"юмшоқ|yumshoq|мягк|жумсақ", t):
        return "soft"
    return None


def build() -> dict:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    books, seen = [], set()
    for p in raw["products"]:
        # every product on the author's page is included; by_shayx only records whether his name is printed
        if p.get("error") or p["slug"] in seen:
            continue
        if detect_kind(strip_quotes(p.get("title") or ""), p["url"]) == "audio":
            continue  # audio products are not printed books
        seen.add(p["slug"])
        title = strip_quotes(p.get("title") or p.get("listing_title") or "")
        lang = detect_lang(title, p["url"])
        years = years_of(p.get("year"))
        pages = pages_of(p.get("pages"))
        binding = binding_of(p.get("binding")) or binding_of(title)
        size, size_method = size_from_title(title), "title_cm"
        if not size:
            size, size_method = size_from_format(p.get("format")), "format"
        if not size:
            size_method = None
        thickness = round(pages * 0.05 + {"hard": 4, "soft": 1.5}.get(binding, 3)) if pages else None
        books.append({
            "id": p["slug"],
            "title": title,
            "title_latn": to_latin(title) if lang == "uz-cyrl" else title,
            "url": p["url"],
            "lang": lang,
            "kind": detect_kind(title, p["url"]),
            "series": detect_series(title),
            "author": p.get("author"),
            "translator": p.get("translator"),
            "publisher": p.get("publisher"),
            "years": years,
            "first_year": years[0] if years else None,
            "latest_year": years[-1] if years else None,
            "year_text": p.get("year"),
            "pages": pages,
            "isbn": p.get("isbn") or p.get("isbn_stats"),
            "weight_kg": p.get("weight_kg"),
            "format": p.get("format"),
            "binding": binding,
            "binding_text": p.get("binding"),
            "height_mm": size[0] if size else None,
            "width_mm": size[1] if size else None,
            "size_method": size_method,
            "thickness_mm": thickness,
            "thickness_method": "pages" if thickness else None,
            "cover": p.get("cover"),
            "ebook_url": p.get("ebook_url"),
            "description": p.get("description"),
        })
    books.sort(key=lambda b: (b["first_year"] or 9999, (b["series"] or {}).get("number") or 0, b["title"]))
    return {
        "source": raw.get("source"),
        "site_total": raw.get("site_total"),
        "author": {"uz": "Shayx Muhammad Sodiq Muhammad Yusuf", "en": "Shaykh Muhammad Sodiq Muhammad Yusuf",
                   "cyrl": "Шайх Муҳаммад Содиқ Муҳаммад Юсуф"},
        "languages": LANGS,
        "series": {k: {"uz": uz, "en": en} for k, uz, en, _ in SERIES},
        "books": books,
    }


def main() -> None:
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    b = data["books"]
    print(f"{len(b)} books -> {OUT.relative_to(ROOT)} | with year: {sum(1 for x in b if x['first_year'])} | "
          f"pages: {sum(1 for x in b if x['pages'])} | size: {sum(1 for x in b if x['height_mm'])} | "
          f"covers: {sum(1 for x in b if x['cover'])}")


if __name__ == "__main__":
    main()
