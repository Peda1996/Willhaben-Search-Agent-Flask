import json
import os
import sqlite3
from datetime import datetime

# Persistent data directory: /data inside the Home Assistant add-on, ./data locally.
DATA_DIR = os.environ.get('DATA_DIR', 'data')
DB_PATH = os.path.join(DATA_DIR, 'urls.db')


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize SQLite database with the required tables
def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS urls_to_crawl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            name TEXT,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_checked DATETIME,
            last_update DATETIME
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS crawled_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_url_id INTEGER,
            FOREIGN KEY (source_url_id) REFERENCES urls_to_crawl(id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS telegram_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE NOT NULL,
            chat_type TEXT NOT NULL
        )''')
        # Structured listings for the deal feed + price-drop watch
        conn.execute('''CREATE TABLE IF NOT EXISTS listings (
            ad_id INTEGER PRIMARY KEY,
            source TEXT,
            source_url_id INTEGER,
            url TEXT,
            heading TEXT,
            body TEXT,
            price INTEGER,
            first_price INTEGER,
            price_display TEXT,
            seller_type TEXT,
            org_name TEXT,
            location TEXT,
            postcode TEXT,
            state TEXT,
            district TEXT,
            coordinates TEXT,
            image_url TEXT,
            published TEXT,
            first_seen DATETIME,
            last_seen DATETIME,
            last_price_change DATETIME,
            status TEXT DEFAULT 'active',
            user_state TEXT,
            notes TEXT,
            attrs_json TEXT,
            FOREIGN KEY (source_url_id) REFERENCES urls_to_crawl(id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_id INTEGER NOT NULL,
            price INTEGER,
            seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ad_id) REFERENCES listings(ad_id)
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_crawled_urls_url ON crawled_urls(url, source_url_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings(last_seen)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_listings_user_state ON listings(user_state)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_price_history_ad ON price_history(ad_id)')
    conn.close()


# Save Telegram chat ID
def save_chat_id(chat_id, chat_type):
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("INSERT INTO telegram_chats (chat_id, chat_type) VALUES (?, ?)", (chat_id, chat_type))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    conn.close()


# Get all Telegram chat IDs
def get_chat_ids():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT chat_id FROM telegram_chats")
        chat_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return chat_ids


# Save new URL to crawl
def add_url_to_crawl(url, name):
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("INSERT INTO urls_to_crawl (url, name) VALUES (?, ?)", (url, name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    conn.close()


# Delete URL to crawl
def delete_url_to_crawl(url_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM urls_to_crawl WHERE id = ?", (url_id,))
        conn.commit()
    conn.close()


# Get all URLs to crawl
def get_urls_to_crawl():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT id, url, name, created_date, last_checked, last_update FROM urls_to_crawl")
        urls = cursor.fetchall()
    conn.close()
    return urls


# Update specific fields in the urls_to_crawl table
def update_url_to_crawl(url_id, url=None, name=None, last_checked=None, last_update=None):
    with sqlite3.connect(DB_PATH) as conn:
        query = "UPDATE urls_to_crawl SET"
        params = []
        if url:
            query += " url = ?,"
            params.append(url)
        if name:
            query += " name = ?,"
            params.append(name)
        if last_checked:
            query += " last_checked = ?,"
            params.append(last_checked)
        if last_update:
            query += " last_update = ?,"
            params.append(last_update)
        # Remove trailing comma and add WHERE clause
        query = query.rstrip(",") + " WHERE id = ?"
        params.append(url_id)
        conn.execute(query, tuple(params))
        conn.commit()
        return True


# Save new crawled URL
def save_crawled_url(url, source_url_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO crawled_urls (url, source_url_id, crawled_at) VALUES (?, ?, ?)",
                     (url, source_url_id, datetime.now()))
        conn.commit()
    conn.close()


# Check if a crawled URL already exists
def crawled_url_exists(url, source_url_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT 1 FROM crawled_urls WHERE url = ? AND source_url_id = ?", (url, source_url_id))
        exists = cursor.fetchone() is not None
    conn.close()
    return exists


# Get paginated crawled URLs for history
def get_crawled_urls(page, per_page):
    offset = (page - 1) * per_page
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''SELECT cu.url, cu.crawled_at, u.url as source_url
                                 FROM crawled_urls cu
                                 JOIN urls_to_crawl u ON cu.source_url_id = u.id
                                 ORDER BY cu.crawled_at DESC
                                 LIMIT ? OFFSET ?''', (per_page, offset))
        urls = cursor.fetchall()

        # Use JOIN in the count query as well
        count_cursor = conn.execute('''SELECT COUNT(*)
                                       FROM crawled_urls cu
                                       JOIN urls_to_crawl u ON cu.source_url_id = u.id''')
        total = count_cursor.fetchone()[0]

    conn.close()
    return urls, total


# Remove Telegram chat ID
def remove_chat_id(chat_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("DELETE FROM telegram_chats WHERE chat_id = ?", (chat_id,))
        conn.commit()
        # Check if any row was deleted
        return cursor.rowcount > 0
    conn.close()


# --------------------------------------------------------------------------- #
# Structured listings / price-drop watch / deal feed
# --------------------------------------------------------------------------- #
_LISTING_REFRESH_FIELDS = (
    "url", "heading", "body", "price_display", "seller_type", "org_name",
    "location", "postcode", "state", "district", "coordinates", "image_url",
    "published",
)


def count_listings_for_search(source_url_id):
    with _connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE source_url_id = ?", (source_url_id,)
        ).fetchone()[0]
    conn.close()
    return n


def get_listing(ad_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM listings WHERE ad_id = ?", (ad_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _add_price_point(conn, ad_id, price):
    conn.execute(
        "INSERT INTO price_history (ad_id, price, seen_at) VALUES (?, ?, ?)",
        (ad_id, price, datetime.now()),
    )


def record_listing(listing, source_url_id):
    """Insert or update a listing.

    Returns a tuple ``(event, old_price)`` where event is one of
    ``"new"``, ``"price_drop"``, ``"price_up"`` or ``"seen"``.
    """
    ad_id = listing.get("ad_id")
    if not ad_id:
        return ("skip", None)

    now = datetime.now()
    price = listing.get("price")
    attrs_json = json.dumps(listing, ensure_ascii=False)

    with _connect() as conn:
        existing = conn.execute(
            "SELECT price FROM listings WHERE ad_id = ?", (ad_id,)
        ).fetchone()

        if existing is None:
            conn.execute(
                """INSERT INTO listings
                   (ad_id, source, source_url_id, url, heading, body, price,
                    first_price, price_display, seller_type, org_name, location,
                    postcode, state, district, coordinates, image_url, published,
                    first_seen, last_seen, status, attrs_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'active', ?)""",
                (
                    ad_id, listing.get("source", "willhaben"), source_url_id,
                    listing.get("url"), listing.get("heading"), listing.get("body"),
                    price, price, listing.get("price_display"),
                    listing.get("seller_type"), listing.get("org_name"),
                    listing.get("location"), listing.get("postcode"),
                    listing.get("state"), listing.get("district"),
                    listing.get("coordinates"), listing.get("image_url"),
                    listing.get("published"), now, now, attrs_json,
                ),
            )
            if price is not None:
                _add_price_point(conn, ad_id, price)
            conn.commit()
            return ("new", None)

        old_price = existing["price"]
        set_clause = ", ".join(f"{f} = ?" for f in _LISTING_REFRESH_FIELDS)
        params = [listing.get(f) for f in _LISTING_REFRESH_FIELDS]
        conn.execute(
            f"UPDATE listings SET {set_clause}, last_seen = ?, status = 'active', "
            f"attrs_json = ? WHERE ad_id = ?",
            params + [now, attrs_json, ad_id],
        )

        event = "seen"
        if price is not None and old_price is None:
            conn.execute("UPDATE listings SET price = ? WHERE ad_id = ?", (price, ad_id))
            _add_price_point(conn, ad_id, price)
        elif price is not None and old_price is not None and price != old_price:
            conn.execute(
                "UPDATE listings SET price = ?, last_price_change = ? WHERE ad_id = ?",
                (price, now, ad_id),
            )
            _add_price_point(conn, ad_id, price)
            event = "price_drop" if price < old_price else "price_up"

        conn.commit()
    conn.close()
    return (event, old_price)


def mark_missing_listings_gone(source_url_id, seen_ad_ids):
    """Flag listings from this search that no longer appear (likely sold)."""
    if not seen_ad_ids:
        return
    placeholders = ",".join("?" for _ in seen_ad_ids)
    with _connect() as conn:
        conn.execute(
            f"""UPDATE listings SET status = 'gone'
                WHERE source_url_id = ? AND status = 'active'
                AND ad_id NOT IN ({placeholders})""",
            [source_url_id, *seen_ad_ids],
        )
        conn.commit()
    conn.close()


def set_listing_user_state(ad_id, state):
    with _connect() as conn:
        conn.execute(
            "UPDATE listings SET user_state = ? WHERE ad_id = ?", (state, ad_id)
        )
        conn.commit()
    conn.close()


def get_price_history(ad_id):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT price, seen_at FROM price_history WHERE ad_id = ? ORDER BY seen_at",
            (ad_id,),
        ).fetchall()
    conn.close()
    return [(r["price"], r["seen_at"]) for r in rows]


_DEAL_SORTS = {
    "newest": "l.first_seen DESC",
    "recent": "l.last_seen DESC",
    "drop": "pct_change ASC, l.last_price_change DESC",
    "price_asc": "l.price ASC",
    "price_desc": "l.price DESC",
}


def get_deals(filters, page=1, per_page=20):
    where = ["1=1"]
    params = []

    if filters.get("q"):
        where.append("(l.heading LIKE ? OR u.name LIKE ?)")
        params += [f"%{filters['q']}%", f"%{filters['q']}%"]
    if filters.get("seller") in ("private", "dealer"):
        where.append("l.seller_type = ?")
        params.append(filters["seller"])
    if filters.get("min_price"):
        where.append("l.price >= ?")
        params.append(int(filters["min_price"]))
    if filters.get("max_price"):
        where.append("l.price <= ?")
        params.append(int(filters["max_price"]))
    if filters.get("drops_only"):
        where.append("l.first_price IS NOT NULL AND l.price < l.first_price")
    if filters.get("source_url_id"):
        where.append("l.source_url_id = ?")
        params.append(int(filters["source_url_id"]))

    state = filters.get("state")
    if state == "new":
        where.append("(l.user_state IS NULL OR l.user_state = '')")
    elif state in ("saved", "contacted", "bought", "muted"):
        where.append("l.user_state = ?")
        params.append(state)
    elif not state or state == "active":
        where.append("(l.user_state IS NULL OR l.user_state != 'muted')")

    order = _DEAL_SORTS.get(filters.get("sort"), _DEAL_SORTS["newest"])
    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page

    with _connect() as conn:
        total = conn.execute(
            f"""SELECT COUNT(*) FROM listings l
                LEFT JOIN urls_to_crawl u ON l.source_url_id = u.id
                WHERE {where_sql}""",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT l.*, u.name AS search_name,
                       CASE WHEN l.first_price > 0
                            THEN round((l.price - l.first_price) * 100.0 / l.first_price, 1)
                            ELSE NULL END AS pct_change
                FROM listings l
                LEFT JOIN urls_to_crawl u ON l.source_url_id = u.id
                WHERE {where_sql}
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def get_deal_stats():
    with _connect() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN first_price IS NOT NULL AND price < first_price THEN 1 ELSE 0 END) AS drops,
                 SUM(CASE WHEN user_state = 'saved' THEN 1 ELSE 0 END) AS saved,
                 SUM(CASE WHEN user_state = 'bought' THEN 1 ELSE 0 END) AS bought
               FROM listings"""
        ).fetchone()
    conn.close()
    return dict(row) if row else {}
