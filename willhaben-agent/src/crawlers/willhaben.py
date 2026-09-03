import logging
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from config import config
from db_utils import (
    get_urls_to_crawl,
    save_crawled_url,
    crawled_url_exists,
    update_url_to_crawl,
    record_listing,
    mark_missing_listings_gone,
    count_listings_for_search,
)
from listings import parse_search_results, WILLHABEN_PREFIX
from bot import send_listing_notification, send_telegram_message
from datetime import datetime

# Ask willhaben for a full first page so we don't miss fast-moving deals
RESULT_ROWS = 100

# Round-robin index across configured willhaben searches
current_index = 0

# Consecutive empty/failed parses per search -> used to alert on layout changes
_blind_counts = {}
_BLIND_ALERT_AFTER = 3

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-AT,de;q=0.9",
}


def _with_rows(url, rows=RESULT_ROWS):
    """Return the search URL with a generous ``rows`` parameter.

    Preserves any repeated filter parameters the user's saved search carries.
    """
    try:
        parts = urlparse(url)
        pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if k.lower() != "rows"]
        pairs.append(("rows", str(rows)))
        return urlunparse(parts._replace(query=urlencode(pairs)))
    except ValueError:
        return url


def crawl_and_notify():
    global current_index

    searches = [u for u in get_urls_to_crawl() if u[1].startswith(WILLHABEN_PREFIX)]
    if not searches:
        logging.warning("No willhaben URLs to crawl.")
        return

    current_index %= len(searches)
    url_id, url, name, created_date, last_checked, last_update = searches[current_index]
    current_index = (current_index + 1) % len(searches)

    try:
        response = requests.get(_with_rows(url), headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("willhaben: network error for %s: %s", url, exc)
        return

    listings = parse_search_results(response.content.decode("utf-8", "replace"))

    if not listings:
        count = _blind_counts.get(url_id, 0) + 1
        _blind_counts[url_id] = count
        logging.warning("willhaben: 0 listings parsed for '%s' (%d in a row)", name, count)
        if count == _BLIND_ALERT_AFTER:
            send_telegram_message(
                f"⚠️ Crawler liefert seit {count} Durchläufen keine Ergebnisse "
                f"für '{name}'. Möglicherweise hat sich willhaben geändert oder blockiert."
            )
        return
    _blind_counts.pop(url_id, None)

    # First crawl of a search seeds silently; afterwards we notify. Also seed
    # silently the first time this search populates the listings table (e.g. an
    # upgrade from an older version whose DB has no structured listings yet).
    notify = last_checked is not None and count_listings_for_search(url_id) > 0
    now = datetime.now()
    seen_ids = []
    new_count = 0
    drop_count = 0

    for listing in listings:
        if not listing.get("ad_id") or not listing.get("url"):
            continue
        seen_ids.append(listing["ad_id"])

        event, old_price = record_listing(listing, url_id)

        if event == "new":
            new_count += 1
            if not crawled_url_exists(listing["url"], url_id):
                save_crawled_url(listing["url"], url_id)
            if notify:
                _safe_notify(listing, "new", None, name)
        elif event == "price_drop":
            drop_count += 1
            if notify:
                _safe_notify(listing, "price_drop", old_price, name)

    # Only reconcile "gone" listings when we've seen the whole result set
    # (a full page means there may be more results we didn't fetch).
    if len(listings) < RESULT_ROWS:
        mark_missing_listings_gone(url_id, seen_ids)

    if new_count or drop_count:
        update_url_to_crawl(url_id, last_checked=now, last_update=now)
    else:
        update_url_to_crawl(url_id, last_checked=now)

    logging.info(
        "willhaben: '%s' -> %d parsed, %d new, %d price drops",
        name, len(listings), new_count, drop_count,
    )


def _safe_notify(listing, kind, old_price, search_name):
    try:
        send_listing_notification(listing, kind, old_price=old_price, search_name=search_name)
    except Exception as exc:
        logging.error("willhaben: notification failed for %s: %s", listing.get("url"), exc)


scheduler = BackgroundScheduler()


def schedule_crawler():
    if not scheduler.running:
        scheduler.start()
    scheduler.remove_all_jobs()
    scheduler.add_job(
        crawl_and_notify,
        "interval",
        seconds=config["check_frequency"],
        id="crawl_and_notify",
        max_instances=1,
        replace_existing=True,
    )
