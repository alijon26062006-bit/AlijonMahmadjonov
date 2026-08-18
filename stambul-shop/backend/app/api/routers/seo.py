"""То, что нужно поисковикам и мессенджерам, а не человеку.

Магазин — одностраничное приложение: браузер получает пустую разметку и
дорисовывает её сам. Роботы так не умеют, поэтому карту сайта и превью
ссылки отдаёт сервер. Обычный посетитель этих ответов не видит: nginx
уводит сюда только запросы роботов.
"""
import html
import uuid as uuid_mod
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import Db
from app.config import get_settings
from app.db.models import P_ACTIVE, P_OUT, Product
from app.catalog.schemas import CATEGORIES
from app.services import product_service

router = APIRouter(tags=["seo"])

SITEMAP_LIMIT = 5000


def _site() -> str:
    return get_settings().site_url.rstrip("/")


@router.get("/robots.txt", include_in_schema=False)
async def robots():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /cart\n"
        "Disallow: /profile\n"
        "Disallow: /login\n"
        "Disallow: /orders\n\n"
        f"Sitemap: {_site()}/sitemap.xml\n"
    )
    return Response(body, media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(session: Db):
    site = _site()
    urls = [f"{site}/", f"{site}/catalog", f"{site}/delivery"]
    urls += [f"{site}/catalog?category={c.slug}" for c in CATEGORIES]

    rows = (await session.execute(
        select(Product.public_id, Product.updated_at)
        .where(Product.status.in_((P_ACTIVE, P_OUT)))
        .order_by(Product.updated_at.desc()).limit(SITEMAP_LIMIT))).all()

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        parts.append(f"<url><loc>{xml_escape(url)}</loc></url>")
    for public_id, updated in rows:
        stamp = f"<lastmod>{updated.date().isoformat()}</lastmod>" if updated else ""
        parts.append(f"<url><loc>{site}/p/{public_id}</loc>{stamp}</url>")
    parts.append("</urlset>")
    return Response("\n".join(parts), media_type="application/xml")


@router.get("/p/{public_id}", include_in_schema=False)
async def product_preview(public_id: uuid_mod.UUID, session: Db):
    """Превью товара для робота: заголовок, цена, картинка.

    Сюда попадают краулеры и мессенджеры, разворачивающие ссылку. Человека
    nginx на этот адрес не пускает, но если он всё же зашёл — страница
    рабочая и ведёт в магазин, а не в тупик.
    """
    s = get_settings()
    site = _site()
    # через сервис: он подтягивает фотографии сразу, а ленивое обращение
    # к ним в асинхронной сессии падает
    product = await product_service.load_public(session, public_id)
    if product is None:
        return Response("<!doctype html><title>Товар не найден</title>",
                        media_type="text/html; charset=utf-8", status_code=404)

    photos = list(product.photos)
    image = (f"{site}/api/photos/{photos[0].public_id}?size=full"
             if photos else "")
    price = f"{round(float(product.price)):,}".replace(",", " ")
    title = html.escape(product.title)
    description = html.escape(
        (product.description or product.title).strip()[:200])
    money = f"{price} {s.currency_sign}"
    available = ("https://schema.org/InStock"
                 if product.status == P_ACTIVE else "https://schema.org/OutOfStock")

    return Response(f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>{title} — {money}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{site}/p/{public_id}">
<meta property="og:type" content="product">
<meta property="og:site_name" content="{html.escape(s.shop_name)}">
<meta property="og:title" content="{title} — {money}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{site}/p/{public_id}">
{f'<meta property="og:image" content="{image}">' if image else ''}
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Product",
"name":"{title}","description":"{description}",
{f'"image":"{image}",' if image else ''}
"offers":{{"@type":"Offer","price":"{round(float(product.price))}",
"priceCurrency":"{s.currency}","availability":"{available}",
"url":"{site}/p/{public_id}"}}}}
</script>
</head><body>
<h1>{title}</h1><p>{money}</p>
<p><a href="{site}/p/{public_id}">Открыть в магазине</a></p>
</body></html>""", media_type="text/html; charset=utf-8")
