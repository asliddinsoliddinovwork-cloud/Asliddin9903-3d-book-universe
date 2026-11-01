import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

from build_data import (binding_of, detect_kind, detect_lang, detect_series, pages_of,  # noqa: E402
                        size_from_format, size_from_title, to_latin, years_of)
from scrape_hilol import canonical, is_by_shayx, parse_details, parse_listing, parse_product, slug_of  # noqa: E402

FIX = HERE / "fixtures"


def test_parse_listing_uses_main_grid_only():
    cards, total = parse_listing((FIX / "listing.html").read_text(encoding="utf-8"))
    assert total == 237
    urls = [c["url"] for c in cards]
    assert "https://hilolnashr.uz/not-this" not in urls
    assert urls[0] == "https://hilolnashr.uz/shayx-kitoblari-uz?product_id=6141"
    assert urls[1] == "https://hilolnashr.uz/shayx-kitoblari-uz/muminning-umr-safari-qr"


def test_parse_product_fields():
    p = parse_product((FIX / "product_quron.html").read_text(encoding="utf-8"), "https://hilolnashr.uz/quron-ilmlari")
    assert p["title"] == "«Қуръон илмлари»"
    assert p["author"] == "Шайх Муҳаммад Содиқ Муҳаммад Юсуф"
    assert p["pages"] == "504 бет" and p["format"] == "60×90 1/16" and p["binding"] == "қаттиқ"
    assert p["isbn"] == "978-9910-987-04-4"
    assert p["cover_remote"].endswith("quron-ilmlari-web-550x550h.jpg")
    assert p["ebook_url"].startswith("https://e-hilolnashr.uz/")
    assert is_by_shayx(p)


def test_canonical_and_slug():
    assert canonical("https://hilolnashr.uz/a/b?limit=100") == "https://hilolnashr.uz/a/b"
    assert slug_of("https://hilolnashr.uz/shayx-kitoblari-uz?product_id=6141") == "product-6141"


def test_size_from_format_matches_gost():
    assert size_from_format("60×90 1/16") == (215, 145)
    assert size_from_format("84x108 1/32") == (200, 130)
    assert size_from_format("70×100 1/16") == (240, 170)
    assert size_from_format("60х84 1/16") == (200, 145)
    assert size_from_format("84×108/32") == (200, 130)
    assert size_from_format("60×90 1/12") is None
    assert size_from_format(None) is None
    assert size_from_title("Қуръони Карим (тажвидли, 17x25 см)") == (250, 170)


def test_years_pages_binding():
    assert years_of("2024 йил (2021, 2019, 2017, 2013, 2022)") == [2013, 2017, 2019, 2021, 2022, 2024]
    assert pages_of("504 бет") == 504
    assert binding_of("қаттиқ") == "hard" and binding_of("юмшоқ") == "soft" and binding_of(None) is None


def test_language_series_kind():
    assert detect_lang("Ҳадис ва Ҳаёт 7-жуз", "https://x/hadis-va-hayot-7-juz") == "uz-cyrl"
    assert detect_lang("Iymon", "https://x/iymon-lotin") == "uz-latn"
    assert detect_lang("Жалған", "https://x/yolgon-qoraqalpoq-tilida") == "kaa"
    assert detect_lang("Мөминниң өмир сапары", "https://x/muminning-umr-safari-qr") == "kaa"
    assert detect_lang("Хадисы и Жизнь 7-джуз", "https://x/hadis-i-jizn-7") == "ru"
    assert detect_lang("Тафсир Хилал 3-том", "https://x/tafsiri-hilol-3-tom-rus") == "ru"
    assert detect_series("Ҳадис ва Ҳаёт 28-жуз. Тафсир") == {"key": "hadis-va-hayot", "number": 28}
    assert detect_series("Олтин силсила – Саҳиҳул Бухорий 8-жуз")["number"] == 8
    assert detect_kind("Тасаввуфга оид 3 та китоб – 10% чегирмада", "https://x?product_id=1") == "bundle"
    assert detect_kind("Кифоя 1,2,3 - жузлари", "https://x/kifoya") == "set"
    assert detect_kind("Иймон", "https://x/iymon") == "book"
    assert detect_kind("Tafsiri Hilol AUDIO (MP3) USB-FLESH", "https://x/th-audio") == "audio"


def test_to_latin():
    assert to_latin("Қуръон илмлари") == "Qur’on ilmlari"
    assert to_latin("Ёлғон") == "Yolg‘on"
    assert to_latin("Ҳадис ва Ҳаёт") == "Hadis va Hayot"
    assert to_latin("Мўминнинг меърожи") == "Mo‘minning me’roji"
    assert to_latin("Ердаги") == "Yerdagi"


def test_parse_details_plain_text_variants():
    t = ("… янги мақолалар қўшилди. Муаллиф : Шайх Муҳаммад Содиқ Муҳаммад Юсуф Нашриёт : «Hilol-Nashr» нашриёт-матбааси "
         "Сана : 2026 (2013, 2015) Ҳажми : 368 бет ISBN : 978-9910-687-34-1 Ўлчами : 84×108 1/32 Муқоваси: қаттиқ "
         "Ўзбекистон Республикаси Дин ишлари бўйича қўмитаси")
    d = parse_details(t)
    assert d["author"] == "Шайх Муҳаммад Содиқ Муҳаммад Юсуф"
    assert d["year"] == "2026 (2013, 2015)" and d["pages"] == "368 бет"
    assert d["format"] == "84×108 1/32" and d["binding"] == "қаттиқ"
    d2 = parse_details("Муаллиф: X Таржимон: Шамсуддин Баҳауддинов Сана: 2021 йил ISBN 978-9943-7035-2-0 Муқоваси: юмшоқ")
    assert d2["translator"] == "Шамсуддин Баҳауддинов" and d2["isbn"] == "978-9943-7035-2-0" and d2["binding"] == "юмшоқ"
