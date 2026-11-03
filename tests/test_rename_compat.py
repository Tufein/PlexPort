import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from jellyport.core import Store
from jellyport.integrations import jellyfin_headers, re_section


class RenameCompatibilityTests(unittest.TestCase):
    def test_legacy_database_and_plex_settings_are_kept_and_not_reused(self):
        with tempfile.TemporaryDirectory() as root:
            legacy = Path(root) / 'plexport.sqlite'
            db = sqlite3.connect(legacy)
            db.execute('CREATE TABLE settings (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('CREATE TABLE jobs (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('INSERT INTO settings VALUES (1, ?)', (json.dumps({'downloader': {'type': 'qbittorrent', 'url': 'http://x'}, 'library': {}, 'plex': {'url': 'http://old:32400', 'token': 'oldtoken'}, 'sources': []}),))
            db.commit()
            db.close()
            store = Store(root)
            self.assertEqual(store.path, legacy)
            settings = store.settings()
            self.assertNotIn('plex', settings)
            self.assertEqual(settings['jellyfin']['token'], '')
            self.assertEqual(settings['downloader']['url'], 'http://x')

    def test_jellyfin_library_ids_and_auth_header(self):
        self.assertTrue(re_section('a1' * 16))
        self.assertTrue(re_section('a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'))
        self.assertFalse(re_section('1'))
        self.assertFalse(re_section('../x'))
        self.assertEqual(jellyfin_headers({'token': 'k"ey'})['Authorization'], 'MediaBrowser Token="key"')


if __name__ == '__main__':
    unittest.main()
