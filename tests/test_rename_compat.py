import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from jellyport.core import Store
from jellyport.integrations import jellyfin_headers, media_servers, plex_scan, re_section, scan_media_servers


class RenameCompatibilityTests(unittest.TestCase):
    def test_legacy_database_and_plex_settings_are_kept(self):
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
            self.assertEqual(settings['plex'], {'url': 'http://old:32400', 'token': 'oldtoken'})
            self.assertEqual(settings['jellyfin']['token'], '')
            self.assertEqual(settings['downloader']['url'], 'http://x')

    def test_jellyfin_library_ids_and_auth_header(self):
        self.assertTrue(re_section('a1' * 16))
        self.assertTrue(re_section('a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'))
        self.assertFalse(re_section('1'))
        self.assertFalse(re_section('../x'))
        self.assertEqual(jellyfin_headers({'token': 'k"ey'})['Authorization'], 'MediaBrowser Token="key"')

    def test_media_servers_need_address_and_token(self):
        self.assertEqual(media_servers({'jellyfin': {'url': 'http://j', 'token': 't'}, 'plex': {'url': 'http://p', 'token': ''}}), ['jellyfin'])
        self.assertEqual(media_servers({'jellyfin': {'url': '', 'token': ''}, 'plex': {'url': 'http://p', 'token': 't'}}), ['plex'])
        self.assertEqual(media_servers({}), [])

    def test_plex_section_must_be_numeric(self):
        with self.assertRaises(ValueError):
            plex_scan({'url': 'http://p', 'token': 't', 'movie_section': '../x'}, 'movie')

    def test_every_configured_server_is_scanned_and_failures_are_reported(self):
        settings = {'jellyfin': {'url': 'http://j', 'token': 't'}, 'plex': {'url': 'http://p', 'token': 't'}}
        with patch('jellyport.integrations.jellyfin_scan') as jelly, patch('jellyport.integrations.plex_scan') as plex:
            scan_media_servers(settings, 'tv')
            jelly.assert_called_once_with(settings['jellyfin'], 'tv')
            plex.assert_called_once_with(settings['plex'], 'tv')
        with patch('jellyport.integrations.jellyfin_scan', side_effect=ValueError('stuk')), patch('jellyport.integrations.plex_scan') as plex:
            with self.assertRaisesRegex(ValueError, 'Jellyfin: stuk'):
                scan_media_servers(settings, 'movie')
            plex.assert_called_once()


if __name__ == '__main__':
    unittest.main()
