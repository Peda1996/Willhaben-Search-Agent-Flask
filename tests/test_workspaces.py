import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import db_utils  # noqa: E402


class WorkspaceDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.previous_path = db_utils.DATABASE_PATH
        db_utils.DATABASE_PATH = Path(self.temp_directory.name) / "urls.db"

    def tearDown(self):
        db_utils.DATABASE_PATH = self.previous_path
        self.temp_directory.cleanup()

    def test_legacy_database_is_migrated_to_default_workspace(self):
        connection = sqlite3.connect(db_utils.DATABASE_PATH)
        connection.executescript('''
            CREATE TABLE urls_to_crawl (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_checked DATETIME,
                last_update DATETIME
            );
            CREATE TABLE crawled_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                source_url_id INTEGER
            );
            CREATE TABLE telegram_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                chat_type TEXT NOT NULL
            );
            INSERT INTO urls_to_crawl (url, name) VALUES ('https://example.test/legacy', 'Legacy search');
            INSERT INTO crawled_urls (url, source_url_id) VALUES ('https://example.test/item', 1);
            INSERT INTO telegram_chats (chat_id, chat_type) VALUES (123, 'private');
        ''')
        connection.commit()
        connection.close()

        db_utils.init_db()

        default_space = db_utils.get_default_space()
        self.assertEqual(default_space['name'], 'Allgemein')
        self.assertTrue(default_space['is_default'])
        self.assertEqual(db_utils.get_urls_to_crawl(default_space['id'])[0]['name'], 'Legacy search')
        self.assertEqual(db_utils.get_active_space(123)['id'], default_space['id'])
        self.assertEqual(db_utils.get_space_members(default_space['id'])[0]['chat_id'], 123)

    def test_workspaces_keep_searches_and_notifications_isolated(self):
        db_utils.init_db()
        default_space = db_utils.get_default_space()
        second_space_id = db_utils.create_space('Wohnung Wien')
        db_utils.save_chat_id(100, 'private', 'Default chat')
        db_utils.save_chat_id(200, 'private', 'Second chat')

        invitation = db_utils.create_invitation(second_space_id, 'viewer')
        joined, error = db_utils.join_space(200, invitation)
        self.assertIsNone(error)
        self.assertEqual(joined['name'], 'Wohnung Wien')

        self.assertTrue(db_utils.add_url_to_crawl('https://example.test/same', 'Default', default_space['id']))
        self.assertTrue(db_utils.add_url_to_crawl('https://example.test/same', 'Separate', second_space_id))
        self.assertEqual(len(db_utils.get_urls_to_crawl(default_space['id'])), 1)
        self.assertEqual(len(db_utils.get_urls_to_crawl(second_space_id)), 1)
        self.assertEqual(db_utils.get_chat_ids(second_space_id), [200])

        db_utils.set_notifications(second_space_id, 200, False)
        self.assertEqual(db_utils.get_chat_ids(second_space_id), [])

    def test_active_workspace_can_only_be_one_the_chat_has_joined(self):
        db_utils.init_db()
        db_utils.save_chat_id(400, 'private', 'Test chat')
        private_space_id = db_utils.create_space('Private space')

        self.assertIsNone(db_utils.set_active_space(400, private_space_id))
        invitation = db_utils.create_invitation(private_space_id)
        db_utils.join_space(400, invitation)
        self.assertEqual(db_utils.set_active_space(400, 'Private space')['id'], private_space_id)


if __name__ == '__main__':
    unittest.main()
