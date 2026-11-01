"""Build data/books.json from the raw Wikipedia list + optional Open Library enrichment.

Usage:  python scripts/build_data.py
Inputs: data/raw/bestsellers_wikipedia.tsv, data/enrichment.json (optional)
Output: data/books.json
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "bestsellers_wikipedia.tsv"
ENRICH = ROOT / "data" / "enrichment.json"
OUT = ROOT / "data" / "books.json"
SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_best-selling_books"

# Language labels (uz / en). Grouping by original language = "xalq" proxy.
LANGS = {
    "English": "Ingliz", "French": "Fransuz", "Portuguese": "Portugal", "Chinese": "Xitoy",
    "Norwegian": "Norveg", "Spanish": "Ispan", "German": "Nemis", "Italian": "Italyan",
    "Russian": "Rus", "Dutch": "Niderland", "Swedish": "Shved", "Japanese": "Yapon",
    "Hebrew": "Ivrit", "Czech": "Chex", "Yiddish": "Idish", "Gujarati": "Gujarot",
}

# Genre categories: our own grouping of the free-text genre on Wikipedia (an interpretation).
# Order = priority when picking the primary category.
GENRES = [
    ("children", "Bolalar adabiyoti", "Children's", ["children", "picture book"]),
    ("young_adult", "O‘smirlar adabiyoti", "Young adult", ["young adult"]),
    ("scifi", "Ilmiy fantastika", "Science fiction", ["science fiction", "dystop"]),
    ("fantasy", "Fantastika (fentezi)", "Fantasy", ["fantasy", "magic realism"]),
    ("mystery", "Detektiv va triller", "Mystery & thriller", ["mystery", "thriller", "crime"]),
    ("horror", "Qo‘rqinchli va gotika", "Horror & gothic", ["horror", "gothic"]),
    ("romance", "Romantika", "Romance", ["romance", "romantic", "sentimental", "erotica"]),
    ("historical", "Tarixiy", "Historical", ["historical", "war"]),
    ("memoir", "Memuar va biografiya", "Memoir & biography", ["memoir", "autobiograph", "biograph"]),
    ("selfhelp", "Shaxsiy rivojlanish", "Self-help", ["self-help", "motivational"]),
    ("spiritual", "Diniy-ma’naviy", "Spiritual & religious", ["bible", "spiritual", "recovery"]),
    ("nonfiction", "Ilmiy-ommabop va hujjatli", "Non-fiction",
     ["popular science", "nonfiction", "non-fiction", "history", "social science", "manual", "guide", "anthropology", "essay"]),
    ("fiction", "Badiiy adabiyot", "Fiction",
     ["novel", "fiction", "coming-of-age", "bildungsroman", "family saga", "adventure", "satir", "literature", "travel"]),
]
UNSPECIFIED = ("unspecified", "Janr ko‘rsatilmagan", "Genre not given")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def split_title(raw: str) -> tuple[str, str | None]:
    """'The Little Prince (Le Petit Prince)' -> ('The Little Prince', 'Le Petit Prince')."""
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", raw)
    return (m.group(1).strip(), m.group(2).strip()) if m else (raw.strip(), None)


def parse_year(text: str) -> int | None:
    m = re.search(r"\d{3,4}", text)
    return int(m.group()) if m else None


def parse_sales_millions(text: str) -> float | None:
    """Lower bound in millions, for sorting only. '28 – 30 million' -> 28.0, '>200 million' -> 200.0"""
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def genre_tags(text: str) -> list[str]:
    t = text.lower()
    if t.strip() in ("", "-"):
        return [UNSPECIFIED[0]]
    tags = [key for key, _, _, kws in GENRES if any(k in t for k in kws)]
    return tags or ["fiction"]


def build() -> dict:
    enrichment = json.loads(ENRICH.read_text(encoding="utf-8")) if ENRICH.exists() else {}
    books = []
    with RAW.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            title, original = split_title(row["title"])
            book_id = slugify(f"{title}-{row['author']}")
            tags = genre_tags(row["genre"])
            e = enrichment.get(book_id, {})
            books.append({
                "id": book_id,
                "title": title,
                "original_title": original,
                "author": row["author"],
                "language": row["original_language"],
                "year": parse_year(row["first_published"]),
                "year_text": row["first_published"],
                "sales_text": row["approx_sales"],
                "sales_millions_min": parse_sales_millions(row["approx_sales"]),
                "genre_text": None if row["genre"] == "-" else row["genre"],
                "genre": tags[0],
                "genre_tags": tags,
                "list_source": SOURCE_URL,
                # Physical edition data (null until scripts/enrich_openlibrary.py has run)
                "height_mm": e.get("height_mm"),
                "width_mm": e.get("width_mm"),
                "thickness_mm": e.get("thickness_mm"),
                "dims_method": e.get("dims_method"),   # "edition" | "pages_estimate" | None
                "pages": e.get("pages"),
                "cover": e.get("cover"),
                "edition_source": e.get("edition_url"),
            })
    books.sort(key=lambda b: (b["year"] or 9999, b["title"]))
    return {
        "generated_from": SOURCE_URL,
        "note": "Sales figures are approximate, as published on Wikipedia. Genre categories are this project's grouping of Wikipedia's free-text genre.",
        "languages": {k: {"uz": v, "en": k} for k, v in LANGS.items()},
        "genres": {k: {"uz": uz, "en": en} for k, uz, en, _ in GENRES} | {UNSPECIFIED[0]: {"uz": UNSPECIFIED[1], "en": UNSPECIFIED[2]}},
        "books": books,
    }


def main() -> None:
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(data["books"])
    with_dims = sum(1 for b in data["books"] if b["dims_method"] == "edition")
    with_cover = sum(1 for b in data["books"] if b["cover"])
    print(f"{n} books -> {OUT.relative_to(ROOT)} | edition dims: {with_dims} | covers: {with_cover}")


if __name__ == "__main__":
    main()
