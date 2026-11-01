import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_data import build, genre_tags, parse_sales_millions, parse_year, split_title  # noqa: E402
from enrich_openlibrary import parse_dimensions, pages_thickness, pick_edition  # noqa: E402


def test_split_title():
    assert split_title("The Little Prince (Le Petit Prince)") == ("The Little Prince", "Le Petit Prince")
    assert split_title("Dune") == ("Dune", None)


def test_parse_year_and_sales():
    assert parse_year("1925–1929") == 1925
    assert parse_year("1304") == 1304
    assert parse_sales_millions(">200 million") == 200
    assert parse_sales_millions("28 – 30 million") == 28
    assert parse_sales_millions("36.4 million copies in USSR") == 36.4


def test_genre_tags():
    assert genre_tags("-") == ["unspecified"]
    assert genre_tags("Fantasy, children's fiction")[0] == "children"
    assert genre_tags("Science fiction novel")[0] == "scifi"
    assert genre_tags("Self-help") == ["selfhelp"]


def test_parse_dimensions():
    assert parse_dimensions("20 x 13 x 2.5 centimeters") == {"height_mm": 200, "width_mm": 130, "thickness_mm": 25}
    assert parse_dimensions("5.1 x 7.8 x 1 inches") == {"height_mm": 198, "width_mm": 130, "thickness_mm": 25}
    assert parse_dimensions("20 x 13 centimeters") is None
    assert parse_dimensions("200 x 130 x 25 centimeters") is None  # implausible
    assert parse_dimensions(None) is None


def test_pages_thickness():
    assert pages_thickness(400) == 22
    assert pages_thickness(None) is None


def test_pick_edition_prefers_dims_and_cover():
    eds = [{"key": "a", "covers": [1]}, {"key": "b", "physical_dimensions": "20 x 13 x 2 cm"},
           {"key": "c", "physical_dimensions": "21 x 14 x 3 cm", "covers": [5]}]
    d, c = pick_edition(eds)
    assert d["key"] == "c" and c["key"] == "c"


def test_build_counts_and_unique_ids():
    data = build()
    ids = [b["id"] for b in data["books"]]
    assert len(ids) == 169 and len(set(ids)) == 169
    years = [b["year"] for b in data["books"]]
    assert years == sorted(years)
    assert all(b["genre"] in data["genres"] for b in data["books"])
    assert all(b["language"] in data["languages"] for b in data["books"])
