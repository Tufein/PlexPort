import base64
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from plexport.core import Store
from plexport.server import create_server


class BrowserLoginTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.server, _ = create_server('127.0.0.1', 0, Store(Path(self.directory.name)), password='test-password')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f'127.0.0.1:{self.server.server_port}'
        self.basic = 'Basic ' + base64.b64encode(b'admin:test-password').decode()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def call(self, path, data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        supplied = dict(headers or {})
        if data is not None:
            supplied.setdefault('Content-Type', 'application/json')
            supplied.setdefault('X-PlexPort', '1')
        connection.request('POST' if data is not None else 'GET', path, json.dumps(data) if data is not None else None, supplied)
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read()
        connection.close()
        return result

    def login(self):
        code, headers, _ = self.call('/auth/login', {'username': 'admin', 'password': 'test-password'})
        self.assertEqual(code, 200)
        return next(value.split(';')[0] for name, value in headers if name.lower() == 'set-cookie' and value.startswith('plexport_session='))

    def test_login_page_is_public_but_data_and_apk_are_private(self):
        code, headers, body = self.call('/')
        self.assertEqual(code, 200)
        self.assertIn(b'login-form', body)
        self.assertNotIn('WWW-Authenticate', dict(headers))
        for path in ['/api/settings', '/api/status', '/plexport.apk', '/app.js']:
            code, headers, _ = self.call(path, headers={'X-PlexPort': '1'})
            self.assertEqual(code, 401)
            self.assertNotIn('WWW-Authenticate', dict(headers))
        for path in ['/login.js', '/style.css', '/theme.js']:
            self.assertEqual(self.call(path)[0], 200)

    def test_session_reads_data_and_logout_invalidates_token_and_cached_basic(self):
        cookie = self.login()
        code, _, body = self.call('/api/status', headers={'Cookie': cookie, 'X-PlexPort': '1'})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['authentication'], 'session')
        self.assertEqual(self.call('/', headers={'Cookie': cookie})[0], 200)
        code, headers, _ = self.call('/auth/logout', {}, {'Cookie': cookie})
        self.assertEqual(code, 200)
        self.assertTrue(any('Max-Age=0' in value for name, value in headers if name == 'Set-Cookie'))
        self.assertEqual(self.call('/api/status', headers={'Cookie': cookie, 'X-PlexPort': '1'})[0], 401)
        code, _, body = self.call('/', headers={'Cookie': 'plexport_signed_out=1', 'Authorization': self.basic})
        self.assertEqual(code, 200)
        self.assertIn(b'login-form', body)

    def test_login_failure_rate_limit_and_credentials_not_echoed(self):
        for _ in range(8):
            code, _, body = self.call('/auth/login', {'username': 'admin', 'password': 'wrong-password'})
            self.assertEqual(code, 401)
            self.assertNotIn(b'wrong-password', body)
        code, headers, _ = self.call('/auth/login', {'username': 'admin', 'password': 'test-password'})
        self.assertEqual(code, 429)
        self.assertIn('Retry-After', dict(headers))

    def test_session_expires_and_tampered_cookie_fails(self):
        cookie = self.login()
        self.assertEqual(self.call('/api/status', headers={'Cookie': cookie+'x', 'X-PlexPort': '1'})[0], 401)
        from plexport import server
        future = server.time.monotonic() + 13 * 3600
        with patch('plexport.server.time.monotonic', return_value=future):
            self.assertEqual(self.call('/api/status', headers={'Cookie': cookie, 'X-PlexPort': '1'})[0], 401)

    def test_login_and_authenticated_requests_keep_origin_and_header_checks(self):
        body = {'username': 'admin', 'password': 'test-password'}
        self.assertEqual(self.call('/auth/login', body, {'Origin': 'https://another.example'})[0], 403)
        self.assertEqual(self.call('/auth/login', body, {'X-PlexPort': 'wrong'})[0], 403)
        cookie = self.login()
        self.assertEqual(self.call('/api/settings', headers={'Cookie': cookie})[0], 403)
        self.assertEqual(self.call('/auth/logout', {}, {'Cookie': cookie, 'Origin': 'https://another.example'})[0], 403)
        self.assertEqual(self.call('/api/status', headers={'Cookie': cookie, 'X-PlexPort': '1'})[0], 200)

    def test_android_basic_challenge_and_existing_api_clients_still_work(self):
        native = {'User-Agent': 'Mozilla/5.0 (Linux; Android 15; device; wv) Version/4.0 Chrome/130 Mobile Safari/537.36'}
        code, headers, _ = self.call('/', headers=native)
        self.assertEqual(code, 401)
        self.assertIn('WWW-Authenticate', dict(headers))
        code, headers, body = self.call('/', headers={**native, 'Authorization': self.basic})
        self.assertEqual(code, 200)
        self.assertIn(b'page-overview', body)
        self.assertNotIn('Set-Cookie', dict(headers))
        self.assertEqual(self.call('/api/status', headers={'Authorization': self.basic, 'X-PlexPort': '1'})[0], 200)
        self.assertEqual(self.call('/', headers={'Authorization': 'Basic invalid'})[0], 401)

    def test_cookie_flags_and_browser_basic_upgrade(self):
        code, headers, _ = self.call('/', headers={'Authorization': self.basic})
        self.assertEqual(code, 200)
        value = next(v for k,v in headers if k == 'Set-Cookie')
        self.assertIn('HttpOnly', value)
        self.assertIn('SameSite=Strict', value)
        self.assertNotIn('Max-Age', value)
        _, headers, _ = self.call('/auth/login', {'username': 'admin', 'password': 'test-password'}, {'Origin': 'https://'+self.host})
        self.assertIn('; Secure', next(v for k,v in headers if k == 'Set-Cookie' and v.startswith('plexport_session=')))


if __name__ == '__main__':
    unittest.main()
