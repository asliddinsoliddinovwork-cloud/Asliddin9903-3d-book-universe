"""Collect every book by Shayx Muhammad Sodiq Muhammad Yusuf listed on hilolnashr.uz.

Runs in GitHub Actions (.github/workflows/update-books.yml) or locally with internet access:
    python scripts/scrape_hilol.py            # writes data/raw/hilol_products.json + covers/hilol/*.jpg
    python scripts/scrape_hilol.py --limit 5  # quick test
Then run scripts/build_data.py.

Only values printed on the publisher's pages are stored. Nothing is guessed here; derived values
(physical size from the paper format, thickness from page count, transliteration) are computed
and labelled in build_data.py.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "hilol_products.json"
COVERS = ROOT / "covers" / "hilol"
BASE = "https://hilolnashr.uz"
AUTHOR_PAGE = BASE + "/shayx-kitoblari-uz"
UA = "Mozilla/5.0 (compatible; kitob-javoni/1.0; +https://github.com/asliddinsoliddinovwork-cloud/Asliddin9903-3d-book-universe)"
PAUSE = 0.7

# Labels as printed on the site (Uzbek Cyrillic/Latin, Russian, Karakalpak) -> field name
LABELS = {
    "author": ["Муаллиф", "Muallif", "Автор", "Avtor"],
    "translator": ["Таржимон", "Tarjimon", "Переводчик", "Аудармашы"],
    "publisher": ["Нашриёт", "Nashriyot", "Издательство", "Баспа"],
    "year": ["Сана", "Sana", "Год издания", "Год", "Нашр йили"],
    "pages": ["Ҳажми", "Hajmi", "Объём", "Объем", "Количество страниц", "Көлеми"],
    "isbn": ["ISBN"],
    "format": ["Ўлчами", "O‘lchami", "Oʻlchami", "O'lchami", "Формат", "Өлшеми"],
    "binding": ["Муқоваси", "Муқова", "Muqovasi", "Muqova", "Обложка", "Переплёт", "Переплет"],
}
STOPS = ["Ўзбекистон Республикаси", "Өзбекстан Республикасы", "O‘zbekiston Respublikasi", "Oʻzbekiston Respublikasi",
         "Республики Узбекистан", "Электрон нашри", "Stock:", "Код:", "Вазни:"]
_LABEL_RX = re.compile(r"(?<!\w)(" + "|".join(sorted({re.escape(x) for v in LABELS.values() for x in v}, key=len, reverse=True))
                       + r")\s*:?\s*(?=\S)")


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def get(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read().decode("utf-8", errors="replace")
            time.sleep(PAUSE)
            return body
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            print(f"   retry {url}: {exc}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


# ---------- listing ----------
def parse_listing(page_html: str) -> tuple[list[dict], int | None]:
    """Cards from the main product grid only (the page also has unrelated carousels)."""
    i = page_html.find('<div class="main-products')
    if i < 0:
        return [], None
    seg = page_html[i:]
    end = seg.find('<div class="row pagination-results">')
    total = None
    if end > 0:
        m = re.search(r"Жами\s+(\d+)", seg[end:end + 600])
        total = int(m.group(1)) if m else None
        seg = seg[:end]
    cards = []
    for m in re.finditer(r'<div class="name"><a href="([^"]+)">([^<]+)</a>', seg):
        cards.append({"url": canonical(html.unescape(m.group(1))), "title": clean(m.group(2))})
    return cards, total


def canonical(url: str) -> str:
    """Drop listing query params (limit/page) but keep product_id for bundle pages."""
    p = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(p.query)
    keep = {"product_id": q["product_id"]} if "product_id" in q else {}
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(keep, doseq=True), ""))


# ---------- product ----------
def meta(page_html: str, prop: str) -> str | None:
    m = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]*)"', page_html)
    return html.unescape(m.group(1)) if m else None


def parse_details(text: str) -> dict:
    """'Муаллиф: X Нашриёт: Y Сана: Z …' (plain text) -> {field: value}. First occurrence wins."""
    hits = list(_LABEL_RX.finditer(text))
    out = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else min(len(text), m.end() + 160)
        value = text[m.end():end]
        for stop in STOPS:
            value = value.split(stop)[0]
        value = value.replace("«Hilol Nashr»", "").strip(" :;,.\u00a0")
        field = next(f for f, names in LABELS.items() if m.group(1) in names)
        if value and field not in out and len(value) < 200:
            out[field] = value
    return out


def parse_stats(page_html: str) -> dict:
    """OpenCart 'product-stats' list: ISBN, weight and (sometimes) dimensions, as printed."""
    i = page_html.find('class="product-stats"')
    if i < 0:
        return {}
    t = clean(page_html[i:i + 1500])
    out = {}
    m = re.search(r"Вазни:\s*([\d.,]+)\s*кг", t)
    if m:
        out["weight_kg"] = float(m.group(1).replace(",", "."))
    m = re.search(r"Dimensions:\s*([\d.]+)см x ([\d.]+)см x ([\d.]+)см", t)
    if m:
        out["dimensions_cm"] = [float(x) for x in m.groups()]
    m = re.search(r"ISBN:\s*([\d-]{10,17})", t)
    if m:
        out["isbn_stats"] = m.group(1)
    return out


def pick_cover(page_html: str, og_image: str | None) -> str | None:
    """Prefer the 550px-high flat cover that OpenCart renders for the product gallery."""
    if not og_image:
        return None
    base = re.sub(r"-\d+x\d+[wh]?\.(?:jpe?g|png|webp)$", "", og_image)
    urls = set(re.findall(re.escape(base) + r"-(\d+)x(\d+)h\.(?:jpe?g|png|webp)", page_html))
    for size in ("550", "1000", "1100"):
        if any(h == size for _, h in urls):
            ext = re.search(re.escape(base) + rf"-\d+x{size}h\.(jpe?g|png|webp)", page_html).group(1)
            return f"{base}-{size}x{size}h.{ext}"
    return og_image


def parse_product(page_html: str, url: str) -> dict:
    title = meta(page_html, "og:title") or ""
    h1 = re.search(r'<h1 class="title page-title"><span>(.*?)</span>', page_html, re.S)
    if h1:
        title = clean(h1.group(1))
    i = page_html.find('<div class="block-content expand-content">')
    block = page_html[i:i + 8000] if i >= 0 else ""
    j = block.find('class="product-stats"')
    if j > 0:
        block = block[:j]
    text = clean(block)
    details = parse_details(text)
    first = _LABEL_RX.search(text)
    intro = (text[:first.start()] if first else text)[:600].strip()
    ebook = re.search(r'href="(https://e-hilolnashr\.uz/[^"]+)"', block)
    og_image = meta(page_html, "og:image")
    return {
        "url": url,
        "title": title,
        "description": intro or (meta(page_html, "og:description") or "")[:600],
        **details,
        **parse_stats(page_html),
        "ebook_url": ebook.group(1) if ebook else None,
        "cover_remote": pick_cover(page_html, og_image),
    }


def is_by_shayx(p: dict) -> bool:
    text = " ".join([p.get("author", ""), p.get("description", ""), p.get("title", "")]).lower()
    return any(k in text for k in ("муҳаммад содиқ", "muhammad sodiq", "мухаммад садык", "мухаммад содиқ", "muhammad sodiq muhammad yusuf"))


def slug_of(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    s = p.path.rstrip("/").rsplit("/", 1)[-1] or "item"
    q = urllib.parse.parse_qs(p.query)
    if "product_id" in q:
        s = "product-" + q["product_id"][0]
    return re.sub(r"[^A-Za-z0-9_-]+", "-", s).strip("-").lower()


def download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read()
        time.sleep(PAUSE)
    except Exception as exc:  # noqa: BLE001
        print(f"   cover failed {url}: {exc}", file=sys.stderr)
        return False
    if len(body) < 1500:
        return False
    dest.write_bytes(body)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    cards, page, total = [], 1, None
    while True:
        found, t = parse_listing(get(f"{AUTHOR_PAGE}?limit=100&page={page}"))
        total = total or t
        print(f"listing page {page}: {len(found)} items (site total: {total})")
        if not found:
            break
        cards += found
        if total and len(cards) >= total or page > 20:
            break
        page += 1
    seen, products = set(), []
    COVERS.mkdir(parents=True, exist_ok=True)
    for c in cards:
        if c["url"] in seen:
            continue
        seen.add(c["url"])
        if args.limit and len(products) >= args.limit:
            break
        print(f"-> {c['title']}")
        try:
            p = parse_product(get(c["url"]), c["url"])
        except Exception as exc:  # noqa: BLE001
            products.append({"url": c["url"], "title": c["title"], "error": str(exc)[:200]})
            continue
        p["listing_title"] = c["title"]
        p["slug"] = slug_of(c["url"])
        p["by_shayx"] = is_by_shayx(p)
        if p["cover_remote"]:
            ext = Path(urllib.parse.urlsplit(p["cover_remote"]).path).suffix or ".jpg"
            dest = COVERS / f"{p['slug']}{ext}"
            if dest.exists() or download(p["cover_remote"], dest):
                p["cover"] = f"covers/hilol/{dest.name}"
        products.append(p)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps({"source": AUTHOR_PAGE, "site_total": total, "products": products},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved {len(products)} products -> {RAW.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
