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
    assert kind_cover("telegram_stars") == "/static/img/tg-stars.svg"
    assert kind_cover("telegram_stars", "https://x/y.png") == "https://x/y.png"
    assert kind_cover("topup") is None


def test_popular_has_images(conn):
    for item in popular.compute(conn):
        if item["kind"].startswith("telegram"):
            assert item["image_url"]


def test_home_shows_covers(client):
    html = client.get("/").text
    assert "/static/img/tg-stars.svg" in html and "cat-cover" in html
