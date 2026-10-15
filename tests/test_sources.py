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
import urllib.request

from plexport import sources
from plexport.core import Store, defaults, merge_settings, public_settings
from plexport.integrations import search_source
from plexport.server import create_server

HASH = 'a' * 40
YTS = {'id': 'y', 'type': 'yts', 'name': 'My films', 'url': 'https://untrusted.invalid'}
EZTV = {'id': 'e', 'type': 'eztv', 'name': 'My series', 'url': 'https://untrusted.invalid'}


def film(title='Sintel', year=2010, info_hash=HASH, quality='720p'):
    return {'title': title, 'year': year, 'torrents': [{'hash': info_hash, 'quality': quality, 'type': 'bluray',
             'seeds': 16, 'size_bytes': 143151596, 'date_uploaded_unix': 1718441309, 'url': 'file:///unsafe'}]}


def show(title='Cosmos', imdb='tt2395695', show_id=1128, premiered='1980-09-28'):
    return {'show': {'id': show_id, 'name': title, 'externals': {'imdb': imdb}, 'premiered': premiered,
                     'url': 'javascript:untrusted'}}


def episode(title='Cosmos S01E01 720p', info_hash=HASH, imdb='2395695', **extra):
    return {'title': title, 'hash': info_hash, 'imdb_id': imdb, 'season': '1', 'episode': '1',
            'magnet_url': 'magnet:?' + urllib.parse.urlencode({'xt': 'urn:btih:' + info_hash, 'dn': title,
                                                            'tr': 'udp://tracker.example:80/announce'}),
            'size_bytes': '12345', 'seeds': 7, 'date_released_unix': 1718441309, **extra}


def episodes(items, imdb='2395695'):
    return {'imdb_id': imdb, 'torrents_count': len(items), 'torrents': items}


class SourceAdaptersTests(unittest.TestCase):
    def setUp(self):
        sources._cache.clear()

    def test_yts_uses_official_new_api_ignores_config_url_and_returns_confirmed_identity(self):
        with patch('plexport.sources.fetch_json', return_value={'status': 'ok', 'data': {'movies': [film()]}}) as fetch:
            result = search_source(YTS, 'Sintel', 'movie')
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual((row['library_title'], row['year'], row['kind']), ('Sintel', '2010', 'movie'))
        self.assertIn('720p bluray', row['title'])
        self.assertEqual(row['source'], 'My films')
        self.assertEqual(row['size'], 143151596)
        self.assertEqual(row['seeders'], 16)
        parsed = urllib.parse.urlsplit(fetch.call_args.args[0])
        self.assertEqual(parsed.hostname, 'movies-api.accel.li')
        self.assertEqual(urllib.parse.parse_qs(parsed.query), {'query_term': ['Sintel'], 'limit': ['50'], 'page': ['1']})
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(row['link']).query)
        self.assertEqual(params, {'xt': ['urn:btih:' + HASH], 'dn': [row['title']]})
        self.assertTrue(row['published'].startswith('2024-'))

    def test_yts_preserves_versions_and_known_missing_year_does_not_get_guessed(self):
        movie = film(year=None)
        movie['torrents'].append({**movie['torrents'][0], 'hash': 'b' * 40, 'quality': '1080p'})
        with patch('plexport.sources.fetch_json', return_value={'status': 'ok', 'data': {'movies': [movie]}}):
            result = sources.search(YTS, 'Sint', 'movie')
        self.assertEqual(len(result), 2)
        self.assertEqual({row['year'] for row in result}, {''})
        self.assertEqual(len({row['link'] for row in result}), 2)

    def test_unsupported_media_and_actor_modes_make_no_request(self):
        with patch('plexport.sources.fetch_json') as fetch:
            for source, kind, mode in [(YTS, 'tv', 'title'), (EZTV, 'movie', 'title'),
                                       (YTS, 'movie', 'actor'), (EZTV, 'tv', 'actor')]:
                self.assertEqual(search_source(source, 'Query', kind, mode), [])
            fetch.assert_not_called()

    def test_empty_invalid_and_huge_queries_make_no_request(self):
        with patch('plexport.sources.fetch_json') as fetch:
            for query in ('', 'x', '  ', '**', 'a' * 201, None, {}, 33):
                with self.subTest(query=query), self.assertRaises(ValueError):
                    sources.search(YTS, query, 'movie')
            fetch.assert_not_called()

    def test_yts_malformed_json_shapes_have_actionable_error_and_are_not_cached(self):
        for body in ([], None, {'status': 'error'}, {'status': 'ok'}, {'status': 'ok', 'data': []},
                     {'status': 'ok', 'data': {'movies': {}}}, {'status': 'ok', 'data': {}},
                     {'status': 'ok', 'data': {'movie_count': 2}},
                     {'status': 'ok', 'data': {'movie_count': True}},
                     {'status': 'ok', 'data': {'movie_count': 3, 'movies': []}}):
            with self.subTest(body=body), patch('plexport.sources.fetch_json', return_value=body) as fetch:
                with self.assertRaisesRegex(ValueError, 'YTS'):
                    sources.search(YTS, 'Sintel', 'movie')
                self.assertEqual(sources._cache, {})

    def test_yts_ignores_bad_entries_hashes_unrelated_names_and_numeric_types(self):
        movies = [None, [], film(title='Unrelated'), film(info_hash='file:///evil'),
                  {'title': 'Sintel', 'torrents': {}}, film()]
        movies[-1]['torrents'] = [None, {}, {**movies[-1]['torrents'][0], 'seeds': True, 'size_bytes': -5}]
        with patch('plexport.sources.fetch_json', return_value={'status': 'ok', 'data': {'movies': movies}}):
            rows = sources.search(YTS, 'Sintel', 'movie')
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['seeders'], rows[0]['size']), (0, 0))

    def test_eztv_matches_tvmaze_names_before_imdb_lookup_and_uses_confirmed_show_year(self):
        suggestions = [show('Unrelated'), show('Cosmos', imdb=None), show(), show('COSMOS', premiered='2020-01-01')]
        with patch('plexport.sources.fetch_json', side_effect=[suggestions, episodes([episode()])]) as fetch:
            rows = sources.search(EZTV, 'Cosmos', 'tv')
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args_list[0].args[0]).query), {'q': ['Cosmos']})
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args_list[1].args[0]).query)
        self.assertEqual(params, {'imdb_id': ['2395695'], 'limit': ['100'], 'page': ['1']})
        row = rows[0]
        self.assertEqual((row['library_title'], row['year'], row['season'], row['episode']), ('Cosmos', '1980', '1', '1'))
        self.assertEqual((row['size'], row['seeders']), (12345, 7))
        self.assertEqual(row['metadata_source'], 'TVmaze')
        self.assertEqual(row['metadata_url'], 'https://www.tvmaze.com/shows/1128')
        self.assertNotIn('tr=', row['link'])
        self.assertTrue(row['published'].startswith('2024-'))

    def test_eztv_name_matching_supports_literal_substrings_unicode_and_all_query_tokens(self):
        self.assertTrue(sources._compatible('Star Trek: Strange New Worlds', 'star trek'))
        self.assertTrue(sources._compatible('Cosmos', 'Cos'))
        self.assertTrue(sources._compatible('Séries: One', 'series one'))
        self.assertFalse(sources._compatible('The Winter', 'Sintel'))
        with patch('plexport.sources.fetch_json', return_value=[show('The Winter'), show('Sister Wives')]) as fetch:
            self.assertEqual(sources.search(EZTV, 'Sintel', 'tv'), [])
            self.assertEqual(fetch.call_count, 1)

    def test_episode_query_uses_show_name_and_multi_episode_identity_stays_ambiguous(self):
        torrents = [episode('Cosmos S01E01E02 720p', info_hash='b' * 40),
                    episode('Cosmos S01E01-E03 720p', info_hash='c' * 40),
                    episode('Cosmos S01 COMPLETE', info_hash='d' * 40),
                    episode('Cosmos S01E01 S02E01', info_hash='e' * 40)]
        with patch('plexport.sources.fetch_json', side_effect=[[show()], episodes(torrents)]) as fetch:
            rows = sources.search(EZTV, 'Cosmos S01E01', 'tv')
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args_list[0].args[0]).query), {'q': ['Cosmos']})
        self.assertEqual([row['episode'] for row in rows], ['', '', '', ''])
        self.assertEqual([row['season'] for row in rows], ['1', '1', '1', ''])

    def test_eztv_invalid_show_and_torrent_shapes_are_skipped_or_reported(self):
        suggestions = [None, {}, {'show': []}, show(imdb='ttBAD'), show(title='Cosmos\nInjected'), show()]
        torrents = [None, {}, episode(imdb='9999999'), episode(info_hash='not-a-hash'), episode()]
        with patch('plexport.sources.fetch_json', side_effect=[suggestions, episodes(torrents)]):
            self.assertEqual(len(sources.search(EZTV, 'Cosmos', 'tv')), 1)
        for payloads in ([{}], [[show()], []], [[show()], {'torrents': {}}]):
            sources._cache.clear()
            with patch('plexport.sources.fetch_json', side_effect=payloads), self.assertRaises(ValueError):
                sources.search(EZTV, 'Cosmos', 'tv')

    def test_missing_premiere_is_unknown_instead_of_release_year_and_link_is_canonical(self):
        with patch('plexport.sources.fetch_json', side_effect=[[show(premiered=None, show_id='unsafe')], episodes([episode()])]):
            row = sources.search(EZTV, 'Cosmos', 'tv')[0]
        self.assertEqual(row['year'], '')
        self.assertEqual(row['metadata_url'], 'https://www.tvmaze.com')

    def test_yts_has_one_request_and_caps_movie_variant_inputs_and_global_results(self):
        movies = []
        for i in range(60):
            movie = film(title='Sintel ' + str(i))
            movie['torrents'] = [{**movie['torrents'][0], 'hash': f'{i * 30 + j:040x}'} for j in range(30)]
            movies.append(movie)
        with patch('plexport.sources.fetch_json', return_value={'status': 'ok', 'data': {'movies': movies}}) as fetch:
            rows = sources.search(YTS, 'Sintel', 'movie')
        self.assertEqual(len(rows), 250)
        self.assertEqual(fetch.call_count, 1)
        self.assertTrue(all(row['library_title'] != 'Sintel 59' for row in rows))

    def test_eztv_caps_show_requests_per_show_torrents_and_global_results(self):
        suggestions = [show('Cosmos ' + str(i), imdb='tt' + f'{i + 1:07d}') for i in range(1000)]
        def fetch(url):
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            if 'tvmaze' in url:
                return suggestions
            imdb = params['imdb_id'][0]
            return episodes([episode('Cosmos S01E01 720p', info_hash=f'{int(imdb) * 1000 + i:040x}', imdb=imdb) for i in range(1000)], imdb)
        with patch('plexport.sources.fetch_json', side_effect=fetch) as request:
            rows = sources.search(EZTV, 'Cosmos', 'tv')
        self.assertEqual(request.call_count, 4)
        self.assertEqual(len(rows), 250)
        self.assertEqual(len({row['link'] for row in rows}), 250)

    def test_cache_is_short_bounded_shared_by_provider_and_rename_safe_with_no_disk_history(self):
        with patch('plexport.sources.fetch_json', return_value={'status': 'ok', 'data': {'movies': [film()]}}) as fetch:
            with patch('plexport.sources.time.monotonic', return_value=10):
                first = sources.search(YTS, 'Sintel', 'movie')
            first[0]['library_title'] = 'Changed in browser'
            with patch('plexport.sources.time.monotonic', return_value=309):
                second = sources.search({**YTS, 'name': 'Renamed'}, 'SINTEL', 'movie')
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(second[0]['source'], 'Renamed')
            self.assertEqual(second[0]['library_title'], 'Sintel')
            with patch('plexport.sources.time.monotonic', return_value=310):
                sources.search(YTS, 'Sintel', 'movie')
            self.assertEqual(fetch.call_count, 2)
        sources._cache.clear()
        with patch('plexport.sources.fetch_json', return_value={'status': 'ok', 'data': {'movies': []}}):
            for i in range(40):
                sources.search(YTS, 'Title ' + str(i), 'movie')
        self.assertEqual(len(sources._cache), 32)
        self.assertNotIn(('yts', 'title 0', 'movie'), sources._cache)

    def test_empty_results_cache_but_network_errors_remain_actionable_and_not_cached(self):
        with patch('plexport.sources.fetch_json', return_value={'status': 'ok', 'data': {'movie_count': 0}}) as fetch:
            self.assertEqual(sources.search(YTS, 'Missing', 'movie'), [])
            self.assertEqual(sources.search(YTS, 'Missing', 'movie'), [])
            self.assertEqual(fetch.call_count, 1)
        sources._cache.clear()
        with patch('plexport.sources.fetch_json', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                sources.search(YTS, 'Missing', 'movie')
        self.assertEqual(sources._cache, {})

    def test_eztv_error_objects_missing_positive_lists_and_wrong_show_header_are_errors(self):
        for payload in ({}, {'error': 'Temporarily unavailable'}, {'imdb_id': '2395695', 'torrents_count': 7},
                        {'imdb_id': '2395695', 'torrents_count': True},
                        {'imdb_id': '9999999', 'torrents_count': 0},
                        {'imdb_id': '2395695', 'torrents_count': 0, 'torrents': [episode()]}):
            sources._cache.clear()
            with self.subTest(payload=payload), patch('plexport.sources.fetch_json', side_effect=[[show()], payload]):
                with self.assertRaisesRegex(ValueError, 'EZTV'):
                    sources.search(EZTV, 'Cosmos', 'tv')
                self.assertEqual(sources._cache, {})
        with patch('plexport.sources.fetch_json', side_effect=[[show()], {'imdb_id': '2395695', 'torrents_count': 0}]):
            self.assertEqual(sources.search(EZTV, 'Cosmos', 'tv'), [])

    def test_season_only_and_zero_placeholder_never_become_confirmed_single_episode(self):
        self.assertEqual(sources._episode('Show S01 1080p', {'season': '1', 'episode': '0'}), ('1', ''))
        self.assertEqual(sources._episode('Show 1080p', {'season': '1', 'episode': '0'}), ('1', ''))
        self.assertEqual(sources._episode('Show S00E00 1080p', {'season': '0', 'episode': '0'}), ('0', '0'))


class ProviderTransportAndMagnetTests(unittest.TestCase):
    def test_only_fixed_https_hosts_and_safe_same_host_redirects_are_accepted(self):
        for url in ('http://eztvx.to/api/get-torrents', 'https://other.invalid', 'file:///etc/passwd',
                    'https://user:secret@eztvx.to/api/get-torrents', 'https://eztvx.to:80/api/get-torrents',
                    'https://eztvx.to/api#get-torrents', 'https://eztvx.to:bad/api'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                sources.fetch_json(url)
        req = urllib.request.Request(sources.EZTV_API)
        redirects = sources._OfficialRedirects()
        for url in ('https://evil.invalid/api', sources.TVMAZE_API, 'http://eztvx.to/api'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                redirects.redirect_request(req, None, 302, '', {}, url)
        redirect = redirects.redirect_request(req, None, 302, '', {}, sources.EZTV_API + '?page=1')
        self.assertEqual(redirect.full_url, sources.EZTV_API + '?page=1')

    def test_transport_bounds_reads_timeouts_and_rejects_malformed_json(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.geturl.return_value = sources.YTS_API
        opener = Mock()
        opener.open.return_value = response
        with patch('plexport.sources.urllib.request.build_opener', return_value=opener):
            response.read.return_value = b'{"status":"ok"}'
            self.assertEqual(sources.fetch_json(sources.YTS_API), {'status': 'ok'})
            self.assertEqual(opener.open.call_args.kwargs['timeout'], 8)
            response.read.assert_called_with(sources.MAX_BYTES + 1)
            for body in (b'not json', b'\xff', b'x' * (sources.MAX_BYTES + 1)):
                response.read.return_value = body
                with self.subTest(body_size=len(body)), self.assertRaises(ValueError):
                    sources.fetch_json(sources.YTS_API)

    def test_magnet_hash_and_protocol_whitelist_never_forward_untrusted_network_controls(self):
        valid = episode()['magnet_url']
        self.assertTrue(sources._magnet(HASH, 'Title', valid).startswith('magnet:?'))
        self.assertNotIn('tr=', sources._magnet(HASH, 'Title', valid))
        for hash_value in ('not a hash', 'a' * 39, 'a' * 41, None, 10):
            self.assertEqual(sources._magnet(hash_value, 'Title'), '')
        for magnet in ('https://example.org/file.torrent', 'javascript:alert(1)',
                       valid + '&ws=file%3A%2F%2F%2Fetc%2Fpasswd', valid + '&xs=https%3A%2F%2Fevil.invalid',
                       valid.replace(HASH, 'b' * 40), valid.replace('udp%3A', 'file%3A'),
                       valid + '&xt=urn:btih:' + HASH, valid + '#fragment'):
            with self.subTest(magnet=magnet):
                self.assertEqual(sources._magnet(HASH, 'Title', magnet), '')


class SourceSettingsAndHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / 'state')
        self.server, _ = create_server('127.0.0.1', 0, self.store, password='source-fixture')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.authorization = 'Basic ' + base64.b64encode(b'admin:source-fixture').decode()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def get(self, kind='movie', mode='title'):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        path = '/api/search?' + urllib.parse.urlencode({'q': 'Cosmos', 'kind': kind, 'mode': mode})
        connection.request('GET', path, headers={'Authorization': self.authorization, 'X-PlexPort': '1'})
        response = connection.getresponse()
        status, body = response.status, json.loads(response.read())
        connection.close()
        return status, body

    def test_preset_urls_are_locked_names_editable_and_legacy_secrets_preserved(self):
        config = defaults()
        config['sources'] = [{'id': 'old', 'name': 'Private', 'url': 'https://private.invalid/api', 'api_key': 'keep-secret'},
                             {'id': 'w', 'type': 'watchsomuch', 'name': 'WSM', 'url': 'https://watchsomuch.to', 'api_key': 'old-secret'}]
        incoming = {'sources': [{'id': 'old', 'name': 'Renamed private', 'url': 'https://private.invalid/api'},
                                {'id': 'w', 'name': 'Renamed WSM'},
                                {**YTS, 'api_key': 'unused-secret'}, EZTV]}
        result = merge_settings(config, incoming)
        self.assertEqual(result['sources'][0]['api_key'], 'keep-secret')
        self.assertEqual(result['sources'][0]['type'], 'torznab')
        self.assertEqual(result['sources'][1]['api_key'], 'old-secret')
        self.assertEqual(result['sources'][1]['url'], 'https://watchsomuch.to')
        self.assertEqual(result['sources'][2]['url'], 'https://yts.gg')
        self.assertEqual(result['sources'][3]['url'], 'https://eztvx.to')
        self.assertEqual(result['sources'][2]['api_key'], '')
        self.assertEqual(merge_settings(result, public_settings(result)), result)
        self.store.save_settings(result)
        reloaded = Store(Path(self.directory.name) / 'state').settings()
        self.assertEqual(reloaded['sources'], result['sources'])

    def test_search_dispatches_only_compatible_sources_and_keeps_actor_only_wsm(self):
        self.store.save_settings({'sources': [YTS, EZTV, {'id': 'w', 'name': 'WSM', 'type': 'watchsomuch'}]})
        with patch('plexport.server.search_source', return_value=[]) as fetch:
            code, body = self.get('movie')
            self.assertEqual(code, 200)
            self.assertEqual(body['searched_sources'], 2)
            self.assertEqual({call.args[0]['type'] for call in fetch.call_args_list}, {'yts', 'watchsomuch'})
            fetch.reset_mock()
            code, body = self.get('tv')
            self.assertEqual(code, 200)
            self.assertEqual(body['searched_sources'], 2)
            self.assertEqual({call.args[0]['type'] for call in fetch.call_args_list}, {'eztv', 'watchsomuch'})
            fetch.reset_mock()
            code, body = self.get('movie', 'actor')
            self.assertEqual(code, 200)
            self.assertEqual(body['searched_sources'], 1)
            self.assertEqual([call.args[0]['type'] for call in fetch.call_args_list], ['watchsomuch'])

    def test_incompatible_sources_have_actionable_message_and_no_provider_request(self):
        self.store.save_settings({'sources': [YTS]})
        with patch('plexport.server.search_source') as fetch:
            code, body = self.get('tv')
            self.assertEqual(code, 400)
            self.assertIn('series', body['error'])
            code, body = self.get('movie', 'actor')
            self.assertEqual(code, 400)
            self.assertIn('WatchSoMuch', body['error'])
            fetch.assert_not_called()

    def test_provider_failure_is_reported_by_source_without_hiding_other_results(self):
        self.store.save_settings({'sources': [YTS, EZTV, {'id': 'w', 'name': 'WSM', 'type': 'watchsomuch'}]})
        def fetch(source, *args):
            if source['type'] == 'yts':
                raise TimeoutError()
            return [{'title': 'Cosmos', 'library_title': 'Cosmos', 'link': 'magnet:?xt=urn:btih:' + HASH, 'seeders': 3}]
        with patch('plexport.server.search_source', side_effect=fetch):
            code, body = self.get('movie')
        self.assertEqual(code, 200)
        self.assertEqual(len(body['results']), 1)
        self.assertEqual(body['errors'][0]['source'], 'My films')
        self.assertNotIn('untrusted.invalid', json.dumps(body))

    def test_all_attempted_sources_failure_count_excludes_incompatible_configured_sources(self):
        self.store.save_settings({'sources': [YTS, EZTV]})
        with patch('plexport.server.search_source', side_effect=TimeoutError()) as fetch:
            code, body = self.get('movie')
        self.assertEqual(code, 200)
        self.assertEqual(body['results'], [])
        self.assertEqual(body['searched_sources'], 1)
        self.assertEqual(len(body['errors']), body['searched_sources'])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.args[0]['type'], 'yts')


if __name__ == '__main__':
    unittest.main()
