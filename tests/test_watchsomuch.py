import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import urllib.parse

from plexport.core import Store, Worker, defaults, merge_settings, new_job
from plexport.integrations import search_source
from plexport import watchsomuch as wsm

MAGNET = 'magnet:?xt=urn:btih:' + 'a' * 40 + '&dn=Example'
LINK = wsm.BASE + '/Movie/123-HQ/Download-456/Example'
RSS = '<rss><channel><item><title>Example (2020)</title><link>https://watchsomuch.to/Movie/123-HQ/Example</link></item></channel></rss>'
ROWS = '''<div class="header"><div class="seed">Seeds</div></div>
<a class="torrent hd" data-torrent="456" data-title="Example S02E03 720p" href="/Movie/123-HQ/Download-456/Example">
<div class="info"><div class="size"><div class="sizeBar"></div>1.5 GB</div><div class="seed">12</div><div class="seed">999</div></div></a>
<a class="torrent" data-torrent="789" data-title="Untrusted" href="https://other.invalid/Movie/123-HQ/Download-789/Other"></a>'''


class WatchSoMuchTests(unittest.TestCase):
    def setUp(self):
        wsm._cache.clear()

    def test_search_uses_kind_keeps_variants_and_does_not_fetch_magnets(self):
        for kind, endpoint, keyword in [('movie', 'ajMovieTorrents', 'Movies'), ('tv', 'ajTVTorrents', 'TV')]:
            with self.subTest(kind=kind), patch('plexport.watchsomuch.fetch', side_effect=[RSS, ROWS]) as fetch:
                result = search_source({'type':'watchsomuch', 'name':'My source'}, 'Example', kind)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['seeders'], 12)
                self.assertEqual(result[0]['size'], 1610612736)
                self.assertEqual(result[0]['library_title'], 'Example')
                self.assertEqual(result[0]['year'], '2020')
                self.assertEqual(result[0]['link'], LINK)
                if kind == 'tv':
                    self.assertEqual((result[0]['season'], result[0]['episode']), ('02', '03'))
                params = urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args_list[0].args[0]).query)
                self.assertEqual(params['Search'], [keyword + ' Example'])
                self.assertEqual(fetch.call_args_list[1].args[0], '/Movies/' + endpoint + '.aspx?mid=123')
                self.assertEqual(fetch.call_count, 2)
            with patch('plexport.watchsomuch.fetch') as fetch:
                cached = wsm.search({'name':'Renamed'}, 'Example', kind)
                self.assertEqual(cached[0]['source'], 'Renamed')
                fetch.assert_not_called()

    def test_search_bounds_requests_and_rejects_non_feed(self):
        many = RSS.replace('</channel>', RSS[RSS.index('<item>'):RSS.index('</item>')+7] * 8 + '</channel>')
        with patch('plexport.watchsomuch.fetch', side_effect=[many] + [ROWS] * 5) as fetch:
            self.assertEqual(len(wsm.search({'name':'Source'}, 'Example', 'movie')), 1)
            self.assertEqual(fetch.call_count, 6)
        with patch('plexport.watchsomuch.fetch', return_value='<html>Sign in</html>'):
            with self.assertRaisesRegex(ValueError, 'zoekfeed'):
                wsm.search({'name':'Source'}, 'Other', 'movie')

    def test_actor_search_keeps_only_credited_films_and_bounds_requests(self):
        def item(title, mid, cast):
            return ('<item><title>%s</title><link>https://watchsomuch.to/Movie/%s-HQ/X</link>'
                    '<description>&lt;br /&gt;Starring: %s&lt;br /&gt;&lt;p&gt;Plot&lt;/p&gt;</description></item>' % (title, mid, cast))
        feed = '<rss><channel>' + item('Big(1988)', 123, 'Tom Hanks, Elizabeth Perkins') \
            + item('Tom Hanks: The Nomad(2023)', 124, 'Josie Ellis') \
            + item('Elvis(2022)', 125, 'Austin Butler, T\u00f4m Hanks') + '</channel></rss>'
        rows = ROWS.replace('/Movie/123-', '/Movie/%s-')
        calls = []

        def fetch(path):
            calls.append(path)
            if path.startswith('/RSS/'):
                return feed
            mid = path.rsplit('mid=', 1)[1]
            return rows % (mid, mid)

        with patch('plexport.watchsomuch.fetch', side_effect=fetch):
            result = wsm.search({'name': 'Source'}, 'tom hanks', 'movie', 'actor')
        self.assertEqual({r['library_title'] for r in result}, {'Big', 'Elvis'})
        self.assertEqual(result[0]['cast'].split(', ')[0].casefold() in ('tom hanks', 't\u00f4m hanks'), True)
        self.assertEqual(len(calls), 3)  # one feed plus the two credited films
        # Actor results are cached separately from title results.
        with patch('plexport.watchsomuch.fetch', side_effect=[RSS, ROWS]):
            self.assertEqual(wsm.search({'name': 'Source'}, 'tom hanks', 'movie')[0]['library_title'], 'Example')
        self.assertEqual(wsm.cast_of('<br />Starring: A B, C D<br />'), ['A B', 'C D'])
        self.assertEqual(wsm.cast_of('no cast'), [])

    def test_resolve_uses_selected_magnet_and_fails_closed(self):
        html = '<a href="magnet:?xt=urn:btih:' + 'b'*40 + '">Related</a><input id="txtMagnetLink" value="' + MAGNET.replace('&', '&amp;') + '">'
        with patch('plexport.watchsomuch.fetch', return_value=html) as fetch:
            self.assertEqual(wsm.resolve(LINK), MAGNET)
            self.assertEqual(fetch.call_args.args[0], '/Movies/ajTorrentDetails.aspx?movie=123&key=456')
        for html in ('<html>Blocked</html>', '<input id="txtMagnetLink" value="https://other.invalid">', '<input id="txtMagnetLink" value="magnet:?xt=urn:btih:bad">'):
            with patch('plexport.watchsomuch.fetch', return_value=html), self.assertRaisesRegex(ValueError, 'magnetlink'):
                wsm.resolve(LINK)
        with patch('plexport.watchsomuch.fetch') as fetch:
            for url in (MAGNET, LINK.replace('watchsomuch.to', 'other.invalid'), LINK.replace('https:', 'http:')):
                self.assertEqual(wsm.resolve(url), url)
            fetch.assert_not_called()

    def test_source_roundtrip_and_legacy_torznab(self):
        c = defaults()
        c['sources'] = [{'id':'old', 'name':'Old', 'url':'https://example.org/api', 'api_key':'secret'}]
        merged = merge_settings(c, {'sources':[{'id':'old', 'name':'Old', 'url':'https://example.org/api'},
                                               {'id':'wsm', 'name':'WatchSoMuch', 'type':'watchsomuch', 'url':'https://other.invalid'}]})
        self.assertEqual(merged['sources'][0]['api_key'], 'secret')
        self.assertEqual(merged['sources'][0]['type'], 'torznab')
        self.assertEqual(merged['sources'][1]['url'], wsm.BASE)
        with self.assertRaisesRegex(ValueError, 'brontype'):
            merge_settings(c, {'sources':[{'name':'Unknown', 'type':'unknown'}]})

    def test_worker_resolves_before_downloader_and_preserves_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            c = defaults()
            c['downloader'].update(url='http://localhost:8080', local_root=folder, remote_root='/downloads')
            c['library'] = {'movies': str(Path(folder) / 'movies'), 'tv': str(Path(folder) / 'tv')}
            for path in c['library'].values():
                Path(path).mkdir()
            job = new_job(c, {'title':'Example', 'link':LINK})
            store = Store(Path(folder) / 'data')
            downloader = Mock()
            downloader.add.return_value = 'torrent-id'
            with patch('plexport.watchsomuch.resolve', return_value=MAGNET) as resolve, patch('plexport.core.client', return_value=downloader):
                Worker(store).step(job)
                resolve.assert_called_once_with(LINK)
            self.assertEqual(downloader.add.call_args.args[0]['link'], MAGNET)
            self.assertEqual(job['torrent_fingerprint'], LINK)
            self.assertEqual(job['state'], 'downloading')
            self.assertEqual(store.job(job['id'])['link'], MAGNET)


if __name__ == '__main__':
    unittest.main()
