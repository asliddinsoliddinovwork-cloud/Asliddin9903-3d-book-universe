"""Fetch real edition dimensions + covers from Open Library for every book in data/books.json.

Runs in GitHub Actions (see .github/workflows/enrich.yml) or locally with internet access:
    python scripts/enrich_openlibrary.py            # only books not yet enriched
    python scripts/enrich_openlibrary.py --all      # re-check everything
Writes data/enrichment.json and covers/<id>.jpg. Then run scripts/build_data.py.

Dimension rules (documented, not guessed per book):
  * "edition": dimensions come from an Open Library edition's `physical_dimensions`.
    The three numbers are sorted: largest = height, middle = width, smallest = thickness.
  * "pages_estimate": no edition has dimensions; thickness = pages * 0.05 mm + 2 mm (cover boards),
    height/width left empty so the viewer uses its labelled default.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books.json"
ENRICH = ROOT / "data" / "enrichment.json"
COVERS = ROOT / "covers"
UA = "3d-book-universe/1.0 (https://github.com; data enrichment script)"
PAUSE = 1.0  # seconds between requests, to be polite to Open Library

UNIT_MM = {"cm": 10.0, "centimeter": 10.0, "centimeters": 10.0, "mm": 1.0, "millimeters": 1.0,
           "in": 25.4, "inch": 25.4, "inches": 25.4}


def parse_dimensions(text: str | None) -> dict | None:
    """'20 x 13 x 2.5 centimeters' -> {'height_mm': 200, 'width_mm': 130, 'thickness_mm': 25}"""
    if not text:
        return None
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]
    unit = re.search(r"(centimeters?|cm|millimeters|mm|inches|inch|in)\b", text.lower())
    if len(nums) != 3 or not unit:
        return None
    k = UNIT_MM[unit.group(1)]
    h, w, t = sorted((n * k for n in nums), reverse=True)
    if not (90 <= h <= 450 and 60 <= w <= 350 and 1 <= t <= 120):
        return None  # implausible -> ignore rather than draw something wrong
    return {"height_mm": round(h), "width_mm": round(w), "thickness_mm": round(t)}


def pages_thickness(pages: int | None) -> int | None:
    if not pages or pages < 8 or pages > 3000:
        return None
    return round(pages * 0.05 + 2)


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    time.sleep(PAUSE)
    return data


def download(url: str, dest: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
    except Exception as exc:  # noqa: BLE001
        print(f"   cover failed: {exc}", file=sys.stderr)
        return False
    finally:
        time.sleep(PAUSE)
    if len(body) < 2000:  # Open Library returns a tiny placeholder when no cover exists
        return False
    dest.write_bytes(body)
    return True


def pick_edition(entries: list[dict]) -> tuple[dict | None, dict | None]:
    """Return (edition with usable dims, best edition with a cover). Prefer editions having both."""
    dims_ed = cover_ed = None
    for ed in entries:
        dims = parse_dimensions(ed.get("physical_dimensions"))
        has_cover = any(c and c > 0 for c in ed.get("covers", []) or [])
        if dims and has_cover:
            return ed, ed
        if dims and not dims_ed:
            dims_ed = ed
        if has_cover and not cover_ed:
            cover_ed = ed
    return dims_ed, cover_ed


def enrich_book(book: dict) -> dict:
    q = urllib.parse.urlencode({"title": book["title"], "author": book["author"], "limit": 1,
                                "fields": "key,cover_i,number_of_pages_median"})
    found = get_json(f"https://openlibrary.org/search.json?{q}").get("docs", [])
    if not found:
        return {"status": "not_found"}
    work = found[0]
    eds = get_json(f"https://openlibrary.org{work['key']}/editions.json?limit=300").get("entries", [])
    dims_ed, cover_ed = pick_edition(eds)
    out: dict = {"status": "ok", "work_url": f"https://openlibrary.org{work['key']}"}
    if dims_ed:
        out |= parse_dimensions(dims_ed["physical_dimensions"])
        out["dims_method"] = "edition"
        out["edition_url"] = f"https://openlibrary.org{dims_ed['key']}"
        out["pages"] = dims_ed.get("number_of_pages")
    else:
        pages = work.get("number_of_pages_median")
        t = pages_thickness(pages)
        if t:
            out |= {"thickness_mm": t, "dims_method": "pages_estimate", "pages": pages}
    cover_id = None
    if cover_ed:
        cover_id = next(c for c in cover_ed["covers"] if c and c > 0)
    elif work.get("cover_i"):
        cover_id = work["cover_i"]
    if cover_id:
        dest = COVERS / f"{book['id']}.jpg"
        if download(f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg", dest):
            out["cover"] = f"covers/{dest.name}"
            out["cover_source"] = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="re-check books already enriched")
    ap.add_argument("--limit", type=int, default=0, help="stop after N books (testing)")
    args = ap.parse_args()
    books = json.loads(BOOKS.read_text(encoding="utf-8"))["books"]
    done = json.loads(ENRICH.read_text(encoding="utf-8")) if ENRICH.exists() else {}
    COVERS.mkdir(exist_ok=True)
    n = 0
    for b in books:
        if not args.all and done.get(b["id"], {}).get("status") == "ok":
            continue
        print(f"-> {b['title']} / {b['author']}")
        try:
            done[b["id"]] = enrich_book(b)
        except Exception as exc:  # noqa: BLE001  keep going; record the failure
            done[b["id"]] = {"status": "error", "error": str(exc)[:200]}
        ENRICH.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
        if args.limit and n >= args.limit:
            break
    ok = sum(1 for v in done.values() if v.get("dims_method") == "edition")
    print(f"processed {n}; books with edition dimensions: {ok}/{len(books)}")


if __name__ == "__main__":
    main()
