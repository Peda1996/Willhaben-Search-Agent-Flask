"""SQLite access layer for monitored searches, workspaces and Telegram chats."""

import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "urls.db"
DEFAULT_SPACE_NAME = "Allgemein"


@contextmanager
def _connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    # Older installations allowed deleting a search while keeping its historical
    # rows. Do not enable SQLite's retroactive FK enforcement here: it would make
    # a later, unrelated search ID impossible to delete when legacy orphaned
    # history happens to use that ID. The application keeps relations explicit.
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _column_exists(conn, table, column):
    return any(row["name"] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def init_db():
    """Create tables and safely migrate a previous single-workspace database."""
    with _connect() as conn:
        # A legacy UNIQUE(url) migration rebuilds the two linked tables below.
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute('''CREATE TABLE IF NOT EXISTS urls_to_crawl (
            id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, name TEXT, space_id INTEGER,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP, last_checked DATETIME, last_update DATETIME,
            UNIQUE(url, space_id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS crawled_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL,
            crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP, source_url_id INTEGER,
            FOREIGN KEY (source_url_id) REFERENCES urls_to_crawl(id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS telegram_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER UNIQUE NOT NULL, chat_type TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS spaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            description TEXT NOT NULL DEFAULT '', is_default INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS space_members (
            space_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner', 'editor', 'viewer')),
            notifications_enabled INTEGER NOT NULL DEFAULT 1, joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (space_id, chat_id),
            FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE CASCADE,
            FOREIGN KEY (chat_id) REFERENCES telegram_chats(chat_id) ON DELETE CASCADE
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS space_invitations (
            code TEXT PRIMARY KEY, space_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('editor', 'viewer')) DEFAULT 'editor',
            expires_at DATETIME NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE CASCADE
        )''')

        if not _column_exists(conn, "urls_to_crawl", "space_id"):
            conn.execute("ALTER TABLE urls_to_crawl ADD COLUMN space_id INTEGER")
        if not _column_exists(conn, "telegram_chats", "active_space_id"):
            conn.execute("ALTER TABLE telegram_chats ADD COLUMN active_space_id INTEGER")
        if not _column_exists(conn, "telegram_chats", "chat_name"):
            conn.execute("ALTER TABLE telegram_chats ADD COLUMN chat_name TEXT")

        default_space = conn.execute("SELECT id FROM spaces WHERE is_default = 1 ORDER BY id LIMIT 1").fetchone()
        if default_space is None:
            conn.execute("INSERT INTO spaces (name, description, is_default) VALUES (?, ?, 1)",
                         (DEFAULT_SPACE_NAME, "Der gemeinsame Standard-Suchraum. Bestehende Daten wurden hierher migriert."))
            default_space_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            default_space_id = default_space["id"]

        # Existing data is deliberately kept together, so an upgrade changes no behaviour.
        conn.execute("UPDATE urls_to_crawl SET space_id = ? WHERE space_id IS NULL", (default_space_id,))
        for chat in conn.execute("SELECT chat_id FROM telegram_chats").fetchall():
            conn.execute("INSERT OR IGNORE INTO space_members (space_id, chat_id, role) VALUES (?, ?, 'editor')",
                         (default_space_id, chat["chat_id"]))
        conn.execute("UPDATE telegram_chats SET active_space_id = ? WHERE active_space_id IS NULL", (default_space_id,))
        _migrate_url_uniqueness(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_urls_space ON urls_to_crawl(space_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_members_chat ON space_members(chat_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_crawled_source ON crawled_urls(source_url_id)")


def _migrate_url_uniqueness(conn):
    """Replace legacy UNIQUE(url) with UNIQUE(url, space_id), preserving all history."""
    legacy_unique_url = False
    for index in conn.execute("PRAGMA index_list(urls_to_crawl)").fetchall():
        if index["origin"] != "u":
            continue
        columns = [column["name"] for column in conn.execute(f"PRAGMA index_info({index['name']})").fetchall()]
        if columns == ["url"]:
            legacy_unique_url = True
            break
    if not legacy_unique_url:
        return

    # SQLite changes foreign-key references when a table is renamed. Recreate the
    # small history table as well, so its source_url_id remains attached to the
    # new table. IDs are copied unchanged.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute('''CREATE TABLE urls_to_crawl_workspace_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, name TEXT, space_id INTEGER,
        created_date DATETIME DEFAULT CURRENT_TIMESTAMP, last_checked DATETIME, last_update DATETIME,
        UNIQUE(url, space_id)
    )''')
    conn.execute('''INSERT INTO urls_to_crawl_workspace_new
                    (id, url, name, space_id, created_date, last_checked, last_update)
                    SELECT id, url, name, space_id, created_date, last_checked, last_update FROM urls_to_crawl''')
    conn.execute('''CREATE TABLE crawled_urls_workspace_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL,
        crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP, source_url_id INTEGER,
        FOREIGN KEY (source_url_id) REFERENCES urls_to_crawl(id)
    )''')
    conn.execute('''INSERT INTO crawled_urls_workspace_new (id, url, crawled_at, source_url_id)
                    SELECT id, url, crawled_at, source_url_id FROM crawled_urls''')
    conn.execute("DROP TABLE crawled_urls")
    conn.execute("DROP TABLE urls_to_crawl")
    conn.execute("ALTER TABLE urls_to_crawl_workspace_new RENAME TO urls_to_crawl")
    conn.execute("ALTER TABLE crawled_urls_workspace_new RENAME TO crawled_urls")


def get_default_space():
    with _connect() as conn:
        return conn.execute("SELECT * FROM spaces WHERE is_default = 1 ORDER BY id LIMIT 1").fetchone()


def get_spaces(chat_id=None):
    with _connect() as conn:
        if chat_id is None:
            return conn.execute("SELECT * FROM spaces ORDER BY is_default DESC, name COLLATE NOCASE").fetchall()
        return conn.execute('''SELECT s.*, sm.role, sm.notifications_enabled FROM spaces s
                               JOIN space_members sm ON sm.space_id = s.id WHERE sm.chat_id = ?
                               ORDER BY s.is_default DESC, s.name COLLATE NOCASE''', (chat_id,)).fetchall()


def get_space(space_id):
    with _connect() as conn:
        return conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()


def create_space(name, description="", creator_chat_id=None):
    name = name.strip()
    if not name:
        return None
    try:
        with _connect() as conn:
            cursor = conn.execute("INSERT INTO spaces (name, description) VALUES (?, ?)", (name, description.strip()))
            space_id = cursor.lastrowid
            if creator_chat_id is not None:
                conn.execute("INSERT OR IGNORE INTO space_members (space_id, chat_id, role) VALUES (?, ?, 'owner')",
                             (space_id, creator_chat_id))
                conn.execute("UPDATE telegram_chats SET active_space_id = ? WHERE chat_id = ?", (space_id, creator_chat_id))
            return space_id
    except sqlite3.IntegrityError:
        return None


def update_space(space_id, name, description):
    try:
        with _connect() as conn:
            return conn.execute("UPDATE spaces SET name = ?, description = ? WHERE id = ?",
                                (name.strip(), description.strip(), space_id)).rowcount > 0
    except sqlite3.IntegrityError:
        return False


def delete_space(space_id):
    """Only empty, non-default spaces can be removed; searches are never silently lost."""
    with _connect() as conn:
        space = conn.execute("SELECT is_default FROM spaces WHERE id = ?", (space_id,)).fetchone()
        if not space or space["is_default"]:
            return False, "Der Standardraum „Allgemein“ kann nicht gelöscht werden."
        if conn.execute("SELECT COUNT(*) FROM urls_to_crawl WHERE space_id = ?", (space_id,)).fetchone()[0]:
            return False, "Der Raum enthält noch Suchen und kann deshalb nicht gelöscht werden."
        conn.execute("DELETE FROM spaces WHERE id = ?", (space_id,))
        return True, None


def save_chat_id(chat_id, chat_type, chat_name=None):
    """Register/update a chat and put it in the default workspace as an editor."""
    default_space = get_default_space()
    with _connect() as conn:
        conn.execute('''INSERT INTO telegram_chats (chat_id, chat_type, chat_name, active_space_id)
                        VALUES (?, ?, ?, ?) ON CONFLICT(chat_id) DO UPDATE SET
                        chat_type = excluded.chat_type,
                        chat_name = COALESCE(excluded.chat_name, telegram_chats.chat_name)''',
                     (chat_id, chat_type, chat_name, default_space["id"]))
        conn.execute("INSERT OR IGNORE INTO space_members (space_id, chat_id, role) VALUES (?, ?, 'editor')",
                     (default_space["id"], chat_id))


def is_chat_registered(chat_id):
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM telegram_chats WHERE chat_id = ?", (chat_id,)).fetchone() is not None


def get_active_space(chat_id):
    with _connect() as conn:
        return conn.execute('''SELECT s.*, sm.role, sm.notifications_enabled FROM telegram_chats tc
                               JOIN space_members sm ON sm.chat_id = tc.chat_id AND sm.space_id = tc.active_space_id
                               JOIN spaces s ON s.id = sm.space_id WHERE tc.chat_id = ?''', (chat_id,)).fetchone()


def set_active_space(chat_id, identifier):
    with _connect() as conn:
        space = conn.execute('''SELECT s.* FROM spaces s JOIN space_members sm ON sm.space_id = s.id
                                WHERE sm.chat_id = ? AND (s.id = ? OR lower(s.name) = lower(?))''',
                             (chat_id, str(identifier), str(identifier))).fetchone()
        if space:
            conn.execute("UPDATE telegram_chats SET active_space_id = ? WHERE chat_id = ?", (space["id"], chat_id))
        return space


def get_member_role(space_id, chat_id):
    with _connect() as conn:
        member = conn.execute("SELECT role FROM space_members WHERE space_id = ? AND chat_id = ?",
                              (space_id, chat_id)).fetchone()
        return member["role"] if member else None


def get_space_members(space_id):
    with _connect() as conn:
        return conn.execute('''SELECT sm.chat_id, sm.role, sm.notifications_enabled, sm.joined_at,
                                      tc.chat_type, tc.chat_name FROM space_members sm
                               JOIN telegram_chats tc ON tc.chat_id = sm.chat_id WHERE sm.space_id = ?
                               ORDER BY CASE sm.role WHEN 'owner' THEN 0 WHEN 'editor' THEN 1 ELSE 2 END,
                               COALESCE(tc.chat_name, tc.chat_id)''', (space_id,)).fetchall()


def update_space_member(space_id, chat_id, role, notifications_enabled):
    if role not in {"owner", "editor", "viewer"}:
        return False
    with _connect() as conn:
        return conn.execute("UPDATE space_members SET role = ?, notifications_enabled = ? WHERE space_id = ? AND chat_id = ?",
                            (role, int(bool(notifications_enabled)), space_id, chat_id)).rowcount > 0


def set_notifications(space_id, chat_id, enabled):
    with _connect() as conn:
        return conn.execute("UPDATE space_members SET notifications_enabled = ? WHERE space_id = ? AND chat_id = ?",
                            (int(bool(enabled)), space_id, chat_id)).rowcount > 0


def create_invitation(space_id, role="editor", valid_days=7):
    role = role if role in {"editor", "viewer"} else "editor"
    with _connect() as conn:
        for _ in range(5):
            code = secrets.token_urlsafe(6).upper()
            try:
                expires_at = (datetime.now() + timedelta(days=valid_days)).isoformat(sep=" ", timespec="seconds")
                conn.execute("INSERT INTO space_invitations (code, space_id, role, expires_at) VALUES (?, ?, ?, ?)",
                             (code, space_id, role, expires_at))
                return code
            except sqlite3.IntegrityError:
                continue
    return None


def join_space(chat_id, code):
    with _connect() as conn:
        invitation = conn.execute('''SELECT i.*, s.name FROM space_invitations i JOIN spaces s ON s.id = i.space_id
                                     WHERE i.code = ?''', (code.strip().upper(),)).fetchone()
        if not invitation or datetime.fromisoformat(invitation["expires_at"]) < datetime.now():
            return None, "Dieser Einladungs-Code ist ungültig oder abgelaufen."
        conn.execute("INSERT OR IGNORE INTO space_members (space_id, chat_id, role) VALUES (?, ?, ?)",
                     (invitation["space_id"], chat_id, invitation["role"]))
        conn.execute("UPDATE telegram_chats SET active_space_id = ? WHERE chat_id = ?", (invitation["space_id"], chat_id))
        return invitation, None


def get_chat_ids(space_id=None):
    with _connect() as conn:
        if space_id is None:
            return [row["chat_id"] for row in conn.execute("SELECT chat_id FROM telegram_chats")]
        return [row["chat_id"] for row in conn.execute("SELECT chat_id FROM space_members WHERE space_id = ? AND notifications_enabled = 1",
                                                        (space_id,))]


def remove_chat_id(chat_id):
    with _connect() as conn:
        return conn.execute("DELETE FROM telegram_chats WHERE chat_id = ?", (chat_id,)).rowcount > 0


def add_url_to_crawl(url, name, space_id):
    with _connect() as conn:
        try:
            conn.execute("INSERT INTO urls_to_crawl (url, name, space_id) VALUES (?, ?, ?)", (url, name, space_id))
            return True
        except sqlite3.IntegrityError:
            return False


def get_urls_to_crawl(space_id=None):
    query = "SELECT id, space_id, url, name, created_date, last_checked, last_update FROM urls_to_crawl"
    parameters = ()
    if space_id is not None:
        query += " WHERE space_id = ?"
        parameters = (space_id,)
    with _connect() as conn:
        return conn.execute(query + " ORDER BY id", parameters).fetchall()


def get_url_to_crawl(url_id):
    with _connect() as conn:
        return conn.execute("SELECT id, space_id, url, name, created_date, last_checked, last_update FROM urls_to_crawl WHERE id = ?",
                            (url_id,)).fetchone()


def delete_url_to_crawl(url_id, space_id=None):
    query, parameters = "DELETE FROM urls_to_crawl WHERE id = ?", [url_id]
    if space_id is not None:
        query += " AND space_id = ?"
        parameters.append(space_id)
    with _connect() as conn:
        return conn.execute(query, parameters).rowcount > 0


def update_url_to_crawl(url_id, space_id=None, url=None, name=None, last_checked=None, last_update=None):
    fields, parameters = [], []
    for field, value in (("url", url), ("name", name), ("last_checked", last_checked), ("last_update", last_update)):
        if value is not None:
            fields.append(f"{field} = ?")
            parameters.append(value)
    if not fields:
        return False
    query = f"UPDATE urls_to_crawl SET {', '.join(fields)} WHERE id = ?"
    parameters.append(url_id)
    if space_id is not None:
        query += " AND space_id = ?"
        parameters.append(space_id)
    try:
        with _connect() as conn:
            return conn.execute(query, parameters).rowcount > 0
    except sqlite3.IntegrityError:
        return False


def save_crawled_url(url, source_url_id):
    with _connect() as conn:
        conn.execute("INSERT INTO crawled_urls (url, source_url_id, crawled_at) VALUES (?, ?, ?)",
                     (url, source_url_id, datetime.now()))


def crawled_url_exists(url, source_url_id):
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM crawled_urls WHERE url = ? AND source_url_id = ?", (url, source_url_id)).fetchone() is not None


def get_crawled_urls(space_id, page, per_page):
    offset = (page - 1) * per_page
    with _connect() as conn:
        urls = conn.execute('''SELECT cu.url, cu.crawled_at, u.url AS source_url FROM crawled_urls cu
                               JOIN urls_to_crawl u ON cu.source_url_id = u.id WHERE u.space_id = ?
                               ORDER BY cu.crawled_at DESC LIMIT ? OFFSET ?''', (space_id, per_page, offset)).fetchall()
        total = conn.execute('''SELECT COUNT(*) FROM crawled_urls cu JOIN urls_to_crawl u ON cu.source_url_id = u.id
                                WHERE u.space_id = ?''', (space_id,)).fetchone()[0]
        return urls, total
