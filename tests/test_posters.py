import base64
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from html import escape
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.parse

from plexport.core import Store
from plexport import posters
from plexport.server import create_server


JPEG = b'\xff\xd8\xff\xe0example-poster\xff\xd9'
CATALOG = 'https://watchsomuch.to/Movie/123-HQ/Example-2020'
IMAGE = 'https://watchsomuch.to/Media/PosterS/000000123_Small.jpg'


def feed(items=None):
    items = items or [('Example(2020)', CATALOG, '/Media/PosterS/000000123_Small.jpg')]
    return ('<rss><channel>' + ''.join('<item><title>' + escape(title) + '</title><link>' + escape(url)
            + '</link><description>' + escape('<img src="' + src + '"/>') + '</description></item>'
            for title, url, src in items) + '</channel></rss>').encode()


class Response:
    def __init__(self, body, url=IMAGE, content_type='image/jpeg', length=None):
        self.body = body
        self.url = url
        self.headers = Message()
        self.headers['Content-Type'] = content_type
        if length is not None:
            self.headers['Content-Length'] = str(length)
        self.requested = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def geturl(self):
        return self.url

    def read(self, limit):
        self.requested.append(limit)
        return self.body[:limit]


class PosterTests(unittest.TestCase):
    def setUp(self):
        self.cache = posters.PosterCache()

    def test_exact_title_year_and_category_then_local_cache(self):
        with patch('plexport.posters.read_public', side_effect=[feed(), JPEG]) as read:
            result = self.cache.lookup('  EXAMPLE  ', '2020', 'movie')
            self.assertRegex(result['image_url'], r'^/posters/[a-f0-9]{64}\.jpg$')
            self.assertEqual(result['source_url'], CATALOG)
            self.assertEqual(result['source_name'], 'WatchSoMuch')
            self.assertIn('Search=Movies+EXAMPLE', read.call_args_list[0].args[0])
            self.assertEqual(read.call_args_list[1].args[0], IMAGE)
            self.assertEqual(self.cache.lookup('example', '2020', 'movie'), result)
            self.assertEqual(read.call_count, 2)
        key = result['image_url'].split('/')[-1][:-4]
        self.assertEqual(self.cache.image(key), JPEG)
        with patch('plexport.posters.read_public', side_effect=[feed(), JPEG]) as read:
            self.cache.lookup('Example', '2020', 'tv')
            self.assertIn('Search=TV+Example', read.call_args_list[0].args[0])

    def test_remakes_unknown_year_and_fuzzy_matches_are_not_guessed(self):
        entries = [('Example(2020)', CATALOG, '/Media/PosterS/000000123_Small.jpg'),
                   ('Example(2024)', CATALOG.replace('123', '456'), '/Media/PosterS/000000456_Small.jpg')]
        for title, year in [('Example', ''), ('Example', '2022'), ('Exampl', '2020')]:
            with self.subTest(title=title, year=year), patch('plexport.posters.read_public', return_value=feed(entries)) as read:
                self.assertEqual(posters.PosterCache().lookup(title, year), {'image_url': ''})
                self.assertEqual(read.call_count, 1)
        with patch('plexport.posters.read_public', side_effect=[feed(entries), JPEG]) as read:
            self.assertTrue(self.cache.lookup('Example', '2024')['image_url'])
            self.assertIn('000000456_Small.jpg', read.call_args_list[1].args[0])

    def test_artwork_must_belong_to_matching_catalog_on_fixed_https_host(self):
        bad_images = ['http://watchsomuch.to/Media/PosterS/000000123_Small.jpg',
                      '//evil.example/Media/PosterS/000000123_Small.jpg',
                      'https://watchsomuch.to.evil.example/Media/PosterS/000000123_Small.jpg',
                      'https://user:password@watchsomuch.to/Media/PosterS/000000123_Small.jpg',
                      'https://watchsomuch.to:444/Media/PosterS/000000123_Small.jpg',
                      '/Media/PosterS/000000456_Small.jpg', '/Media/PosterS/../private.jpg',
                      '/Media/PosterS/000000123_Small.jpg?url=http://localhost/',
                      'https://watchsomuch.to/Media/PosterS/000000123_Small.jpg#fragment']
        for image in bad_images:
            with self.subTest(image=image), patch('plexport.posters.read_public', return_value=feed([('Example(2020)', CATALOG, image)])) as read:
                self.assertEqual(posters.PosterCache().lookup('Example', '2020'), {'image_url': ''})
                self.assertEqual(read.call_count, 1)
        for url in [CATALOG.replace('watchsomuch.to', 'localhost'), CATALOG + '?x=1', CATALOG.replace('https:', 'http:')]:
            with self.subTest(url=url), patch('plexport.posters.read_public', return_value=feed([('Example(2020)', url, IMAGE)])) as read:
                self.assertEqual(posters.PosterCache().lookup('Example', '2020'), {'image_url': ''})
                self.assertEqual(read.call_count, 1)

    def test_offline_or_missing_artwork_is_optional_and_negative_cached(self):
        for value in [TimeoutError(), b'<html>Blocked</html>', b'not xml']:
            with self.subTest(value=value), patch('plexport.posters.read_public', side_effect=value if isinstance(value, Exception) else None, return_value=value) as read:
                cache = posters.PosterCache()
                self.assertEqual(cache.lookup('Example', '2020'), {'image_url': ''})
                self.assertEqual(cache.lookup('Example', '2020'), {'image_url': ''})
                self.assertEqual(read.call_count, 1)
                with patch('plexport.posters.time.monotonic', return_value=time.monotonic() + 301):
                    cache.lookup('Example', '2020')
                self.assertEqual(read.call_count, 2)

    def test_duplicate_requests_collapse_and_outbound_concurrency_is_limited(self):
        started, release = threading.Event(), threading.Event()
        def read(url, limit, image=False):
            if not image:
                started.set()
                self.assertTrue(release.wait(2))
                return feed()
            return JPEG
        with patch('plexport.posters.read_public', side_effect=read) as request, ThreadPoolExecutor(max_workers=4) as pool:
            first = pool.submit(self.cache.lookup, 'Example', '2020')
            self.assertTrue(started.wait(1))
            duplicate = pool.submit(self.cache.lookup, 'Example', '2020')
            release.set()
            self.assertEqual(first.result(), duplicate.result())
            self.assertEqual(request.call_count, 2)
        active, peak = 0, 0
        lock = threading.Lock()
        def concurrent(url, limit, image=False):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.04)
            with lock:
                active -= 1
            return b'<rss><channel/></rss>'
        with patch('plexport.posters.read_public', side_effect=concurrent), ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(self.cache.lookup, [f'Example {n}' for n in range(6)]))
        self.assertLessEqual(peak, 2)

    def test_memory_eviction_invalidates_metadata_without_arbitrary_fetches(self):
        with patch('plexport.posters.IMAGE_COUNT_LIMIT', 1), patch('plexport.posters.METADATA_LIMIT', 1):
            with patch('plexport.posters.read_public', side_effect=[feed(), JPEG]):
                first = self.cache.lookup('Example', '2020')
            second_feed = feed([('Other(2020)', CATALOG.replace('123', '456'), '/Media/PosterS/000000456_Small.jpg')])
            with patch('plexport.posters.read_public', side_effect=[second_feed, JPEG]):
                self.cache.lookup('Other', '2020')
            self.assertEqual(len(self.cache.metadata), 1)
            self.assertEqual(len(self.cache.images), 1)
            self.assertEqual(self.cache.image_bytes, len(JPEG))
            self.assertIsNone(self.cache.image(first['image_url'].split('/')[-1][:-4]))
            with patch('plexport.posters.read_public') as read:
                self.assertIsNone(self.cache.image('http://localhost/private'))
                self.assertIsNone(self.cache.image('a' * 64))
                read.assert_not_called()

    def test_invalid_lookup_parameters_fail_before_network_access(self):
        with patch('plexport.posters.read_public') as read:
            for title, year, kind in [('', '', 'movie'), ('x' * 201, '', 'movie'), ('Example', '1887', 'movie'),
                                      ('Example', '2200', 'movie'), ('Example', '20x0', 'movie'), ('Example', '', 'book')]:
                with self.subTest(title=title, year=year, kind=kind), self.assertRaises(ValueError):
                    self.cache.lookup(title, year, kind)
            read.assert_not_called()

    def test_network_body_type_length_magic_timeout_and_redirects_are_restricted(self):
        cases = [Response(b'<html/>', content_type='text/html'), Response(b'not JPEG'),
                 Response(JPEG, length=posters.IMAGE_LIMIT + 1), Response(JPEG, length='bad'),
                 Response(b'\xff\xd8\xff' + b'x' * posters.IMAGE_LIMIT),
                 Response(JPEG, url='https://localhost/private')]
        for response in cases:
            with self.subTest(response=response), patch('plexport.posters.urllib.request.build_opener') as build:
                build.return_value.open.return_value = response
                with self.assertRaises(ValueError):
                    posters.read_public(IMAGE, posters.IMAGE_LIMIT, image=True)
                self.assertEqual(build.return_value.open.call_args.kwargs['timeout'], 6)
                self.assertIsInstance(build.call_args.args[0], posters.NoRedirect)
        response = Response(JPEG)
        with patch('plexport.posters.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            self.assertEqual(posters.read_public(IMAGE, posters.IMAGE_LIMIT, image=True), JPEG)
            self.assertEqual(response.requested, [posters.IMAGE_LIMIT + 1])
        self.assertIsNone(posters.NoRedirect().redirect_request(None, None, 302, 'Found', {}, 'http://localhost/'))
        response = Response(b'x' * (posters.FEED_LIMIT + 1), url=CATALOG, content_type='application/rss+xml')
        with patch('plexport.posters.urllib.request.build_opener') as build:
            build.return_value.open.return_value = response
            with self.assertRaises(ValueError):
                posters.read_public(CATALOG, posters.FEED_LIMIT)
            self.assertEqual(response.requested, [posters.FEED_LIMIT + 1])

    def test_real_http_redirect_is_not_followed_to_another_resource(self):
        calls = []
        class RedirectHandler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                calls.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/private-target')
                self.send_header('Content-Length', '0')
                self.end_headers()

        server = ThreadingHTTPServer(('127.0.0.1', 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(urllib.error.HTTPError):
                posters.read_public(f'http://127.0.0.1:{server.server_port}/redirect', posters.FEED_LIMIT)
            self.assertEqual(calls, ['/redirect'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class PosterHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.server, _ = create_server('127.0.0.1', 0, Store(Path(self.directory.name)), password='test-password')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.headers = {'Authorization': 'Basic ' + base64.b64encode(b'admin:test-password').decode(), 'X-PlexPort': '1'}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def call(self, path, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        connection.request('GET', path, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_metadata_and_images_are_authenticated_and_only_cached_images_are_served(self):
        path = '/api/artwork?title=Example&year=2020&kind=movie'
        with patch('plexport.posters.read_public', side_effect=[feed(), JPEG]) as read:
            self.assertEqual(self.call(path)[0], 401)
            self.assertEqual(self.call(path, {'Authorization': self.headers['Authorization']})[0], 403)
            code, headers, body = self.call(path, self.headers)
            self.assertEqual(code, 200)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            image_path = json.loads(body)['image_url']
            self.assertEqual(read.call_count, 2)
            self.assertEqual(self.call(image_path)[0], 401)
            code, headers, body = self.call(image_path, {'Authorization': self.headers['Authorization']})
            self.assertEqual(code, 200)
            self.assertEqual(body, JPEG)
            self.assertEqual(headers['Content-Type'], 'image/jpeg')
            self.assertEqual(headers['Cache-Control'], 'private, max-age=600')
            self.assertIn("img-src 'self' data:", headers['Content-Security-Policy'])
            self.assertEqual(self.call('/posters/' + 'a' * 64 + '.jpg', self.headers)[0], 404)
            self.assertEqual(self.call('/posters/http://localhost/private', self.headers)[0], 404)
            self.assertEqual(read.call_count, 2)

    def test_cross_origin_invalid_input_and_offline_metadata(self):
        with patch('plexport.posters.read_public', side_effect=TimeoutError()) as read:
            path = '/api/artwork?title=Example&year=2020&kind=movie'
            self.assertEqual(self.call(path, dict(self.headers, Origin='https://evil.example'))[0], 403)
            for path in ['/api/artwork', '/api/artwork?title=Example&year=199&kind=movie', '/api/artwork?title=Example&kind=book']:
                self.assertEqual(self.call(path, self.headers)[0], 400)
            read.assert_not_called()
            code, _, body = self.call('/api/artwork?title=Example&year=2020&kind=movie', self.headers)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body), {'image_url': ''})


if __name__ == '__main__':
    unittest.main()
