import sqlite3
from datetime import datetime


# Initialize SQLite database with the required tables
def init_db():
    with sqlite3.connect('data/urls.db') as conn:
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
    conn.close()


# Save Telegram chat ID
def save_chat_id(chat_id, chat_type):
    with sqlite3.connect('data/urls.db') as conn:
        try:
            conn.execute("INSERT INTO telegram_chats (chat_id, chat_type) VALUES (?, ?)", (chat_id, chat_type))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    conn.close()


# Get all Telegram chat IDs
def get_chat_ids():
    with sqlite3.connect('data/urls.db') as conn:
        cursor = conn.execute("SELECT chat_id FROM telegram_chats")
        chat_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return chat_ids


# Save new URL to crawl
def add_url_to_crawl(url, name):
    with sqlite3.connect('data/urls.db') as conn:
        try:
            conn.execute("INSERT INTO urls_to_crawl (url, name) VALUES (?, ?)", (url, name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    conn.close()


# Delete URL to crawl
def delete_url_to_crawl(url_id):
    with sqlite3.connect('data/urls.db') as conn:
        conn.execute("DELETE FROM urls_to_crawl WHERE id = ?", (url_id,))
        conn.commit()
    conn.close()


# Get all URLs to crawl
def get_urls_to_crawl():
    with sqlite3.connect('data/urls.db') as conn:
        cursor = conn.execute("SELECT id, url, name, created_date, last_checked, last_update FROM urls_to_crawl")
        urls = cursor.fetchall()
    conn.close()
    return urls


# Update last_checked and last_update timestamps
def update_url_to_crawl(url_id, last_checked=None, last_update=None):
    with sqlite3.connect('data/urls.db') as conn:
        if last_checked and last_update:
            conn.execute("UPDATE urls_to_crawl SET last_checked = ?, last_update = ? WHERE id = ?",
                         (last_checked, last_update, url_id))
        elif last_checked:
            conn.execute("UPDATE urls_to_crawl SET last_checked = ? WHERE id = ?", (last_checked, url_id))
        elif last_update:
            conn.execute("UPDATE urls_to_crawl SET last_update = ? WHERE id = ?", (last_update, url_id))
        conn.commit()
    conn.close()


# Save new crawled URL
def save_crawled_url(url, source_url_id):
    with sqlite3.connect('data/urls.db') as conn:
        conn.execute("INSERT INTO crawled_urls (url, source_url_id, crawled_at) VALUES (?, ?, ?)",
                     (url, source_url_id, datetime.now()))
        conn.commit()
    conn.close()


# Check if a crawled URL already exists
def crawled_url_exists(url, source_url_id):
    with sqlite3.connect('data/urls.db') as conn:
        cursor = conn.execute("SELECT 1 FROM crawled_urls WHERE url = ? AND source_url_id = ?", (url, source_url_id))
        exists = cursor.fetchone() is not None
    conn.close()
    return exists


# Get paginated crawled URLs for history
def get_crawled_urls(page, per_page):
    offset = (page - 1) * per_page
    with sqlite3.connect('data/urls.db') as conn:
        cursor = conn.execute('''SELECT cu.url, cu.crawled_at, u.url as source_url
                                 FROM crawled_urls cu
                                 JOIN urls_to_crawl u ON cu.source_url_id = u.id
                                 ORDER BY cu.crawled_at DESC
                                 LIMIT ? OFFSET ?''', (per_page, offset))
        urls = cursor.fetchall()
        count_cursor = conn.execute('SELECT COUNT(*) FROM crawled_urls')
        total = count_cursor.fetchone()[0]
    conn.close()
    return urls, total


# Remove Telegram chat ID
def remove_chat_id(chat_id):
    with sqlite3.connect('data/urls.db') as conn:
        cursor = conn.execute("DELETE FROM telegram_chats WHERE chat_id = ?", (chat_id,))
        conn.commit()
        # Check if any row was deleted
        return cursor.rowcount > 0
    conn.close()
