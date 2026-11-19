from PIL import Image

from donatix import catalog_job, popular
from donatix.deps import kind_cover


def test_thumb_made_and_used(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_job, "_images", {})
    monkeypatch.setattr(catalog_job, "_thumbs", set())
    url = "https://cdn.example.com/ff.png"
    key = catalog_job._key(url)
    Image.new("RGB", (1200, 1200), "red").save(tmp_path / f"{key}.png")
    catalog_job._images[key] = f"{key}.png"
    assert catalog_job.make_thumb(tmp_path, f"{key}.png")
    with Image.open(tmp_path / "s" / f"{key}.webp") as im:
        assert max(im.size) == catalog_job.THUMB_PX
    assert catalog_job.local_url(url) == f"/media/s/{key}.webp"


def test_covers_for_kinds_without_image():
    assert kind_cover("telegram_stars").startswith("/static/img/tg-stars.svg?v=")   # с хешем — кэш на год
    assert kind_cover("telegram_stars", "https://x/y.png") == "https://x/y.png"
    assert kind_cover("topup") is None


def test_popular_has_images(conn):
    for item in popular.compute(conn):
        if item["kind"].startswith("telegram"):
            assert item["image_url"]


def test_home_shows_covers(client):
    html = client.get("/").text
    assert "/static/img/tg-stars.svg" in html and "cat-cover" in html


def test_static_versioned_and_cached_a_year(client):
    from donatix.deps import static_url
    url = static_url("/static/img/ff-cover.webp")
    assert url.startswith("/static/img/ff-cover.webp?v=")
    r = client.get(url)
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert static_url("/static/nope.png") == "/static/nope.png"          # нет файла — адрес как есть


def test_fonts_local_and_preloaded(client):
    html = client.get("/").text
    assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
    assert 'rel="preload" href="/static/fonts/onest-cyrillic.woff2?v=11"' in html and "font-display: swap" in html
    assert "Onest Fallback" in html
    r = client.get("/static/fonts/onest-cyrillic.woff2?v=11")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
