"""Structured listing extraction and formatting for Willhaben search results.

Willhaben embeds the full, structured search result as JSON in a
``<script id="__NEXT_DATA__">`` tag. That gives us price, seller type,
location, coordinates, car attributes and image URLs without touching a
single detail page - which keeps the crawler fast.
"""

import json
import logging
import re
from datetime import datetime, timezone

WILLHABEN_PREFIX = "https://www.willhaben.at"
IAD_PREFIX = "https://www.willhaben.at/iad/"
IMAGE_CACHE_PREFIX = "https://cache.willhaben.at/mmo/"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_search_results(html):
    """Return a list of structured listing dicts for a Willhaben search page.

    Falls back to an empty list if the page layout is not what we expect
    (caller should treat that as "crawler went blind" and alert).
    """
    match = _NEXT_DATA_RE.search(html)
    if not match:
        logging.warning("willhaben: __NEXT_DATA__ block not found")
        return []

    try:
        data = json.loads(match.group(1))
        adverts = (
            data["props"]["pageProps"]["searchResult"]["advertSummaryList"]
            ["advertSummary"]
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logging.warning("willhaben: could not read advert list: %s", exc)
        return []

    listings = []
    for advert in adverts:
        try:
            listings.append(_build_listing(advert))
        except Exception as exc:  # one bad advert must not kill the batch
            logging.error("willhaben: failed to parse advert: %s", exc)
    return listings


def _attr_map(advert):
    result = {}
    for attr in advert.get("attributes", {}).get("attribute", []):
        values = attr.get("values") or []
        result[attr.get("name")] = values[0] if len(values) == 1 else values
    return result


def _to_int(value):
    if value in (None, "", []):
        return None
    try:
        return int(round(float(str(value).replace(",", "."))))
    except (ValueError, TypeError):
        return None


def _first_image(advert, attrs):
    images = advert.get("advertImageList", {}).get("advertImage") or []
    for image in images:
        if image.get("mainImageUrl"):
            return image["mainImageUrl"]
    raw = attrs.get("MMO") or ""
    if not raw:
        all_urls = attrs.get("ALL_IMAGE_URLS") or ""
        raw = all_urls.split(";")[0] if all_urls else ""
    if raw:
        return IMAGE_CACHE_PREFIX + re.sub(r"\.jpg$", "_hoved.jpg", raw)
    return None


def _build_listing(advert):
    attrs = _attr_map(advert)

    seo_url = attrs.get("SEO_URL") or ""
    ad_id = _to_int(attrs.get("ADID")) or _to_int(advert.get("id"))

    price = _to_int(attrs.get("PRICE"))
    if price is None:
        price = _to_int(attrs.get("PRICE/AMOUNT"))

    is_private = str(attrs.get("ISPRIVATE") or "").strip() == "1"

    published = attrs.get("PUBLISHED_String") or attrs.get("PUBLISHED")

    return {
        "ad_id": ad_id,
        "source": "willhaben",
        "url": IAD_PREFIX + seo_url if seo_url else advert.get("selfLink"),
        "heading": (attrs.get("HEADING") or advert.get("description") or "").strip(),
        "body": (attrs.get("BODY_DYN") or "").strip(),
        "price": price,
        "price_display": attrs.get("PRICE_FOR_DISPLAY") or format_price(price),
        "seller_type": "private" if is_private else "dealer",
        "org_name": attrs.get("ORGNAME") or "",
        "location": attrs.get("LOCATION") or "",
        "postcode": str(attrs.get("POSTCODE") or ""),
        "state": attrs.get("STATE") or "",
        "district": attrs.get("DISTRICT") or "",
        "coordinates": attrs.get("COORDINATES") or "",
        "image_url": _first_image(advert, attrs),
        "published": published,
        # car / vehicle attributes (absent for plain marketplace ads)
        "year": _to_int(attrs.get("YEAR_MODEL")),
        "mileage": _to_int(attrs.get("MILEAGE")),
        "fuel": attrs.get("ENGINE/FUEL_RESOLVED") or attrs.get("MOTOR_FUEL") or "",
        "transmission": attrs.get("TRANSMISSION_RESOLVED") or "",
        "power_ps": _to_int(attrs.get("ENGINE/EFFECT")),
        "make": attrs.get("CAR_MODEL/MAKE") or "",
        "model": attrs.get("CAR_MODEL/MODEL") or "",
    }


# --------------------------------------------------------------------------- #
# Formatting helpers (shared by Telegram + web UI)
# --------------------------------------------------------------------------- #
def format_price(amount):
    if amount in (None, ""):
        return "Preis auf Anfrage"
    try:
        return "€ " + f"{int(amount):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(amount)


def _parse_dt(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or str(value).isdigit():
        try:
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def human_age(published):
    dt = _parse_dt(published)
    if dt is None:
        return ""
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "gerade eben"
    if seconds < 90:
        return "gerade eben"
    if seconds < 3600:
        return f"vor {seconds // 60} Min"
    if seconds < 86400:
        return f"vor {seconds // 3600} Std"
    return f"vor {seconds // 86400} Tg"


def map_link(coordinates="", postcode="", location=""):
    if coordinates:
        query = coordinates
    else:
        query = " ".join(part for part in (postcode, location, "Austria") if part)
    if not query.strip():
        return None
    return "https://www.google.com/maps/search/?api=1&query=" + query.replace(" ", "+")


def spec_line(listing):
    parts = []
    if listing.get("year"):
        parts.append(str(listing["year"]))
    if listing.get("mileage"):
        parts.append(f"{listing['mileage']:,}".replace(",", ".") + " km")
    if listing.get("fuel"):
        parts.append(listing["fuel"])
    if listing.get("transmission"):
        parts.append(listing["transmission"])
    if listing.get("power_ps"):
        parts.append(f"{listing['power_ps']} PS")
    return " · ".join(parts)


def location_line(listing):
    bits = [b for b in (listing.get("postcode"), listing.get("location")) if b]
    text = " ".join(bits)
    if listing.get("state") and listing["state"] not in text:
        text = f"{text} ({listing['state']})" if text else listing["state"]
    return text


def price_change_pct(old_price, new_price):
    if not old_price or not new_price:
        return None
    return round((new_price - old_price) / old_price * 100, 1)


def draft_inquiry(listing, offer_factor=0.87):
    """A ready-to-copy German first message to the seller."""
    heading = listing.get("heading") or "Ihr Inserat"
    lines = [
        f'Hallo, ist "{heading}" noch verfügbar?',
        "Ich hätte ernsthaftes Interesse und könnte kurzfristig abholen.",
    ]
    price = listing.get("price")
    if price:
        offer = int(round(price * offer_factor / 10.0)) * 10
        if offer and offer < price:
            lines.append(f"Wäre ein Preis von {format_price(offer)} möglich?")
    lines.append("Bitte um kurze Rückmeldung. Danke!")
    return "\n".join(lines)


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_caption(listing, kind="new", old_price=None, search_name=None):
    """HTML-formatted caption for a Telegram photo/message."""
    if kind == "price_drop":
        header = "\U0001f4c9 <b>PREIS GESENKT</b>"
    else:
        header = "\U0001f195 <b>Neues Inserat</b>"

    lines = [f"{header}", f"<b>{_esc(listing.get('heading') or 'Inserat')}</b>"]

    price_now = format_price(listing.get("price"))
    if kind == "price_drop" and old_price:
        pct = price_change_pct(old_price, listing.get("price"))
        pct_txt = f"  ({pct:+.1f}%)" if pct is not None else ""
        lines.append(
            f"\U0001f4b0 <s>{_esc(format_price(old_price))}</s> → "
            f"<b>{_esc(price_now)}</b>{pct_txt}"
        )
    else:
        lines.append(f"\U0001f4b0 <b>{_esc(price_now)}</b>")

    specs = spec_line(listing)
    if specs:
        lines.append(f"\U0001f527 {_esc(specs)}")

    loc = location_line(listing)
    age = human_age(listing.get("published"))
    meta = " · ".join(p for p in (loc, age) if p)
    if meta:
        lines.append(f"\U0001f4cd {_esc(meta)}")

    if listing.get("seller_type") == "private":
        lines.append("\U0001f464 Privat")
    elif listing.get("org_name"):
        lines.append(f"\U0001f3e2 Händler: {_esc(listing['org_name'])}")
    else:
        lines.append("\U0001f3e2 Händler")

    if search_name:
        lines.append(f"\U0001f50e {_esc(search_name)}")

    if listing.get("url"):
        lines.append(f'\n<a href="{_esc(listing["url"])}">Zum Inserat auf willhaben</a>')

    return "\n".join(lines)
