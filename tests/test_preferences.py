import copy
import json
from pathlib import Path
import tempfile
import unittest

from plexport.core import Store, defaults, merge_settings, new_job, public_settings


class SearchPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state')
        self.config = defaults()
        self.config['downloader'].update(url='http://downloader.invalid:8080',
                                         local_root=str(self.root / 'downloads'), remote_root='/downloads',
                                         username='test-user', password='test-downloader-secret')
        self.config['library'] = {'movies': str(self.root / 'movies'), 'tv': str(self.root / 'tv')}
        self.config['plex'].update(url='http://plex.invalid:32400', token='test-plex-secret',
                                   movie_section='1', tv_section='2')
        self.config['sources'] = [{'id': 'test-source', 'name': 'Test source', 'type': 'torznab',
                                   'url': 'https://indexer.invalid/api', 'api_key': 'test-source-secret'}]
        self.store.save_settings(self.config)

    def raw_settings(self):
        with self.store.connect() as db:
            return db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0]

    def write_legacy(self, config):
        body = json.dumps(config)
        with self.store.connect() as db:
            db.execute('UPDATE settings SET body=? WHERE id=1', (body,))
        return body

    def test_legacy_read_supplies_defaults_without_rewriting_database(self):
        legacy = copy.deepcopy(self.config)
        legacy.pop('preferences')
        original = self.write_legacy(legacy)
        current = self.store.settings()
        self.assertEqual(current['preferences'],
                         {'quality': 'all', 'max_gb': 0, 'min_seeders': 0, 'sort': 'seeders'})
        self.assertEqual({key: value for key, value in current.items() if key != 'preferences'}, legacy)
        self.assertEqual(self.raw_settings(), original)
        current['preferences']['quality'] = '2160'
        self.assertEqual(self.store.settings()['preferences']['quality'], 'all')

    def test_partial_stored_preferences_get_fallbacks_only_in_memory(self):
        legacy = copy.deepcopy(self.config)
        legacy['preferences'] = {'quality': '1080'}
        original = self.write_legacy(legacy)
        self.assertEqual(self.store.settings()['preferences'],
                         {'quality': '1080', 'max_gb': 0, 'min_seeders': 0, 'sort': 'seeders'})
        self.assertEqual(self.raw_settings(), original)

    def test_preferences_survive_restart_and_preserve_connections_secrets_and_jobs(self):
        job = new_job(self.config, {'title': 'Preferences fixture',
                                    'link': 'magnet:?xt=urn:btih:' + 'a' * 40})
        self.store.save_job(job)
        self.assertNotIn('preferences', job['config'])
        before = self.store.settings()
        selected = {'quality': '1080', 'max_gb': 4, 'min_seeders': 5, 'sort': 'smallest'}
        response = self.store.save_settings({'preferences': selected})
        restarted = Store(self.root / 'state')
        self.assertEqual(restarted.settings()['preferences'], selected)
        for key in ('downloader', 'library', 'plex', 'sources'):
            self.assertEqual(restarted.settings()[key], before[key])
        self.assertEqual(restarted.jobs(), [job])
        self.assertEqual(response['preferences'], selected)
        self.assertTrue(response['downloader']['password_set'])
        self.assertTrue(response['plex']['token_set'])
        self.assertTrue(response['sources'][0]['api_key_set'])
        self.assertNotIn('password', response['downloader'])
        self.assertNotIn('token', response['plex'])
        self.assertNotIn('api_key', response['sources'][0])

    def test_partial_updates_and_old_settings_clients_keep_saved_preferences(self):
        self.store.save_settings({'preferences': {'quality': '2160', 'max_gb': 25}})
        self.store.save_settings({'preferences': {'sort': 'title'}})
        self.store.save_settings({'downloader': {'username': 'renamed-user'}})
        self.assertEqual(self.store.settings()['preferences'],
                         {'quality': '2160', 'max_gb': 25, 'min_seeders': 0, 'sort': 'title'})
        self.assertEqual(self.store.settings()['downloader']['username'], 'renamed-user')
        self.assertEqual(self.store.settings()['downloader']['password'], 'test-downloader-secret')

    def test_legacy_read_then_save_materializes_preferences_without_losing_credentials(self):
        legacy = copy.deepcopy(self.config)
        legacy.pop('preferences')
        self.write_legacy(legacy)
        response = self.store.save_settings({'preferences': {'max_gb': 10, 'min_seeders': 20}})
        saved = json.loads(self.raw_settings())
        self.assertEqual(saved['preferences'],
                         {'quality': 'all', 'max_gb': 10, 'min_seeders': 20, 'sort': 'seeders'})
        for key, value in legacy.items():
            self.assertEqual(saved[key], value)
        self.assertEqual(response, public_settings(saved))

    def test_invalid_preferences_are_rejected_without_changing_saved_settings(self):
        invalid = [None, [], '1080', True, 0,
                   {'quality': 'full-hd'}, {'quality': 1080}, {'quality': False},
                   {'sort': 'newest'}, {'sort': []}, {'sort': None},
                   {'max_gb': True}, {'max_gb': False}, {'max_gb': 4.0},
                   {'max_gb': '4'}, {'max_gb': -1}, {'max_gb': 8},
                   {'min_seeders': True}, {'min_seeders': 5.0}, {'min_seeders': '5'},
                   {'min_seeders': -1}, {'min_seeders': 10},
                   {'source': 'Test source'}, {'quality': '1080', 'max_gb': 3}]
        original = self.raw_settings()
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.store.save_settings({'preferences': value})
                self.assertEqual(self.raw_settings(), original)

    def test_merge_does_not_mutate_caller_settings_or_reuse_default_dictionary(self):
        incoming = {'preferences': {'quality': 'unknown', 'min_seeders': 1}}
        previous_snapshot, incoming_snapshot = copy.deepcopy(self.config), copy.deepcopy(incoming)
        merged = merge_settings(self.config, incoming)
        self.assertEqual(self.config, previous_snapshot)
        self.assertEqual(incoming, incoming_snapshot)
        self.assertEqual(merged['preferences']['quality'], 'unknown')
        merged['preferences']['quality'] = 'sd'
        self.assertEqual(defaults()['preferences']['quality'], 'all')
        self.assertEqual(self.config['preferences']['quality'], 'all')


if __name__ == '__main__':
    unittest.main()
