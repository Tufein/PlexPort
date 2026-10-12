import base64
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.parse

from plexport.core import DEFAULT_PREFERENCES, Store, defaults, new_job
from plexport.server import create_server


class SearchAndPreferencesHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.config = defaults()
        self.config['downloader'].update(type='qbittorrent', url='http://downloader.invalid:8080',
                                         username='download-user', password='download-test-secret',
                                         local_root=str(self.root / 'downloads'), remote_root='/downloads')
        self.config['library'] = {'movies': str(self.root / 'movies'), 'tv': str(self.root / 'tv')}
        self.config['plex'].update(url='http://plex.invalid:32400', token='plex-test-secret')
        self.config['sources'] = [
            {'id': 'a', 'name': 'Source A', 'type': 'torznab', 'url': 'http://source-a.invalid/api', 'api_key': 'source-a-test-secret'},
            {'id': 'b', 'name': 'Source B', 'type': 'torznab', 'url': 'http://source-b.invalid/api', 'api_key': 'source-b-test-secret'},
        ]
        self.store = Store(self.root / 'state')
        self.store.save_settings(self.config)
        self.server, _ = create_server('127.0.0.1', 0, self.store, password='http-test-password')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.authorization = 'Basic ' + base64.b64encode(b'admin:http-test-password').decode()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def call(self, path, data=None, authenticated=True, api_header=True):
        # Each request has its own connection, as separate devices or tabs do.
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        headers = {}
        if authenticated:
            headers['Authorization'] = self.authorization
        if api_header:
            headers['X-PlexPort'] = '1'
        if data is not None:
            headers['Content-Type'] = 'application/json'
        connection.request('POST' if data is not None else 'GET', path,
                           json.dumps(data) if data is not None else None, headers)
        response = connection.getresponse()
        status, body = response.status, json.loads(response.read())
        connection.close()
        return status, body

    def search(self, query, kind='movie', **kwargs):
        return self.call('/api/search?' + urllib.parse.urlencode({'q': query, 'kind': kind}), **kwargs)

    def test_wildcard_search_uses_literal_anchor_sorts_and_preserves_selection_data(self):
        matches = [
            {'title': 'Harry.Potter.2020.1080p', 'library_title': 'Harry Potter', 'year': '2020',
             'source': 'Source A', 'seeders': 12, 'size': 12345, 'link': 'magnet:?xt=urn:btih:' + 'a' * 40},
            {'title': 'Harry Potter S01E02 720p', 'source': 'Source B', 'seeders': 24, 'size': 54321,
             'season': '01', 'episode': '02', 'link': 'https://source-b.invalid/torrent?id=123&token=chosen'},
        ]
        before = copy.deepcopy(matches)

        def source_search(source, term, kind):
            self.assertEqual(term, 'Potter')
            self.assertEqual(kind, 'tv')
            index = 0 if source['id'] == 'a' else 1
            return [matches[index], {'title': 'Potter without Harry', 'source': source['name'],
                                     'seeders': 99, 'link': 'magnet:other'}]

        with patch('plexport.server.search_source', side_effect=source_search) as fetch:
            status, body = self.search('Harry*Potter', 'tv')
        self.assertEqual(status, 200)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(body['results'], [matches[1], matches[0]])
        self.assertEqual(body['errors'], [])
        self.assertTrue(body['search']['wildcard'])
        self.assertTrue(body['search']['notice'])
        self.assertEqual(matches, before)

    def test_actor_search_only_asks_watchsomuch_sources(self):
        self.config['sources'].append({'id': 'w', 'name': 'WatchSoMuch', 'type': 'watchsomuch', 'url': 'https://watchsomuch.to'})
        self.store.save_settings(self.config)
        row = {'title': 'Big 1080p', 'source': 'WatchSoMuch', 'seeders': 5, 'link': 'x', 'cast': 'Tom Hanks'}
        with patch('plexport.server.search_source', return_value=[row]) as fetch:
            status, body = self.call('/api/search?' + urllib.parse.urlencode({'q': 'Tom Hanks', 'kind': 'movie', 'mode': 'actor'}))
        self.assertEqual(status, 200)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.args[0]['id'], 'w')
        self.assertEqual(fetch.call_args.args[3], 'actor')
        self.assertEqual(body['results'], [row])
        for query, mode in (('Tom*', 'actor'), ('Tom Hanks', 'other')):
            status, body = self.call('/api/search?' + urllib.parse.urlencode({'q': query, 'kind': 'movie', 'mode': mode}))
            self.assertEqual(status, 400)

    def test_actor_search_needs_a_watchsomuch_source(self):
        with patch('plexport.server.search_source') as fetch:
            status, body = self.call('/api/search?' + urllib.parse.urlencode({'q': 'Tom Hanks', 'kind': 'movie', 'mode': 'actor'}))
        self.assertEqual(status, 400)
        self.assertIn('WatchSoMuch', body['error'])
        fetch.assert_not_called()

    def test_wildcard_filter_is_applied_before_global_result_limit(self):
        excluded = [{'title': 'Unrelated movie', 'seeders': 1000 + i, 'link': 'magnet:unrelated'} for i in range(300)]
        selected = {'title': 'Harry Potter', 'seeders': 1, 'link': 'magnet:chosen'}
        with patch('plexport.server.search_source', side_effect=lambda source, term, kind:
                   excluded if source['id'] == 'a' else [selected]):
            status, body = self.search('Harry*Potter')
        self.assertEqual(status, 200)
        self.assertEqual(body['results'], [selected])

    def test_global_result_limit_remains_bounded_after_wildcard_filter(self):
        rows = [{'title': 'Harry Potter ' + str(i), 'seeders': i, 'link': 'magnet:' + str(i)} for i in range(300)]
        with patch('plexport.server.search_source', side_effect=lambda source, term, kind: rows if source['id'] == 'a' else []):
            status, body = self.search('Harry*Potter')
        self.assertEqual(status, 200)
        self.assertEqual(len(body['results']), 250)
        self.assertEqual(body['results'][0], rows[-1])
        self.assertEqual(body['results'][-1], rows[50])

    def test_ordinary_search_preserves_provider_query_and_existing_result_behavior(self):
        row = {'title': 'Another title', 'seeders': 9, 'link': 'magnet:literal-selection'}
        with patch('plexport.server.search_source', return_value=[row]) as fetch:
            status, body = self.search('  Spider-Man (2020) [1080p]  ')
        self.assertEqual(status, 200)
        self.assertEqual(body['results'], [row, row])
        self.assertEqual(body['search'], {'wildcard': False, 'notice': ''})
        for call in fetch.call_args_list:
            self.assertEqual(call.args[1:], ('Spider-Man (2020) [1080p]', 'movie'))

    def test_invalid_wildcards_and_overlong_query_fail_before_contacting_sources(self):
        with patch('plexport.server.search_source') as fetch:
            for query in ('**', '*?*?', '*a*b*', 'x' * 201):
                with self.subTest(query=query):
                    status, body = self.search(query)
                    self.assertEqual(status, 400)
                    self.assertTrue(body['error'])
            fetch.assert_not_called()

    def test_search_requires_authentication_and_api_header(self):
        with patch('plexport.server.search_source', return_value=[]) as fetch:
            self.assertEqual(self.search('Star*', authenticated=False)[0], 401)
            self.assertEqual(self.search('Star*', api_header=False)[0], 403)
            fetch.assert_not_called()
            self.assertEqual(self.search('Star*')[0], 200)
            self.assertEqual(fetch.call_count, 2)

    def test_empty_wildcard_results_keep_explanation_and_partial_source_errors(self):
        with patch('plexport.server.search_source', return_value=[]):
            status, body = self.search('Star*')
        self.assertEqual(status, 200)
        self.assertEqual(body['results'], [])
        self.assertEqual(body['errors'], [])
        self.assertTrue(body['search']['wildcard'])
        self.assertTrue(body['search']['notice'])
        row = {'title': 'Star Wars', 'seeders': 2, 'link': 'magnet:available'}

        def partial(source, term, kind):
            if source['id'] == 'b':
                raise ValueError('Bron tijdelijk niet bereikbaar.')
            return [row]

        with patch('plexport.server.search_source', side_effect=partial):
            status, body = self.search('Star*')
        self.assertEqual(status, 200)
        self.assertEqual(body['results'], [row])
        self.assertEqual(body['errors'], [{'source': 'Source B', 'error': 'Bron tijdelijk niet bereikbaar.'}])
        self.assertTrue(body['search']['wildcard'])

    def test_preferences_save_and_reload_across_connections_keep_checks_credentials_and_jobs(self):
        job = new_job(self.store.settings(), {'title': 'Keep this task', 'link': 'magnet:?xt=urn:btih:' + 'b' * 40})
        self.store.save_job(job)
        before_config = self.store.settings()
        before_jobs = self.store.jobs()
        downloader = Mock()
        downloader.test.return_value = 'Downloader bereikbaar'
        with patch('plexport.server.client', return_value=downloader):
            self.assertEqual(self.call('/api/test', {'target': 'downloader'})[0], 200)
        status, initial = self.call('/api/status')
        self.assertEqual(status, 200)
        self.assertTrue(initial['checks']['downloader']['ok'])
        preferences = {'quality': '1080', 'max_gb': 10, 'min_seeders': 5, 'sort': 'smallest'}
        status, saved = self.call('/api/settings', {'preferences': preferences})
        self.assertEqual(status, 200)
        self.assertEqual(saved['preferences'], preferences)
        self.assertEqual(self.call('/api/settings')[1]['preferences'], preferences)
        self.assertEqual(self.call('/api/status')[1]['checks'], initial['checks'])
        self.assertEqual(self.store.jobs(), before_jobs)
        after_config = self.store.settings()
        for group in ('downloader', 'library', 'plex', 'sources'):
            self.assertEqual(after_config[group], before_config[group])
        self.assertTrue(saved['downloader']['password_set'])
        self.assertTrue(saved['plex']['token_set'])
        self.assertNotIn('password', saved['downloader'])
        self.assertNotIn('token', saved['plex'])
        self.assertEqual(Store(self.root / 'state').settings()['preferences'], preferences)

    def test_legacy_database_exposes_preference_defaults_without_mutating_records_on_read(self):
        legacy = self.store.settings()
        legacy.pop('preferences')
        legacy_body = json.dumps(legacy)
        with self.store.connect() as database:
            database.execute('UPDATE settings SET body=? WHERE id=1', (legacy_body,))
        for _ in range(2):
            status, body = self.call('/api/settings')
            self.assertEqual(status, 200)
            self.assertEqual(body['preferences'], DEFAULT_PREFERENCES)
        with self.store.connect() as database:
            stored = database.execute('SELECT body FROM settings WHERE id=1').fetchone()[0]
        self.assertEqual(stored, legacy_body)
        status, body = self.call('/api/settings', {'preferences': {'quality': '2160'}})
        self.assertEqual(status, 200)
        self.assertEqual(body['preferences'], {**DEFAULT_PREFERENCES, 'quality': '2160'})

    def test_invalid_preference_save_and_missing_auth_leave_saved_state_unchanged(self):
        before = self.store.settings()
        before_jobs = self.store.jobs()
        for preferences in ({'quality': '4k'}, {'min_seeders': True}, {'max_gb': '10'}, {'unknown': 'value'}):
            with self.subTest(preferences=preferences):
                self.assertEqual(self.call('/api/settings', {'preferences': preferences})[0], 400)
                self.assertEqual(self.store.settings(), before)
        self.assertEqual(self.call('/api/settings', {'preferences': {'quality': '1080'}}, authenticated=False)[0], 401)
        self.assertEqual(self.call('/api/settings', {'preferences': {'quality': '1080'}}, api_header=False)[0], 403)
        self.assertEqual(self.store.settings(), before)
        self.assertEqual(self.store.jobs(), before_jobs)


if __name__ == '__main__':
    unittest.main()
