import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import secrets
import threading
import time
import urllib.parse
import webbrowser

from .core import Store, Worker, defaults, friendly_error, new_job, public_job, public_settings, require_storage, storage_report
from .integrations import client, plex_scan, plex_sections, search_source

STATIC = Path(__file__).parent / 'static'


def create_server(host, port, store, password=''):
    worker = Worker(store)
    checks = {}
    sessions = {}
    failures = {}
    auth_lock = threading.Lock()
    cookie_name = 'plexport_session'

    def new_session():
        now = time.monotonic()
        with auth_lock:
            for token, expires in list(sessions.items()):
                if expires <= now:
                    del sessions[token]
            if len(sessions) >= 1024:
                del sessions[next(iter(sessions))]
            token = secrets.token_urlsafe(32)
            sessions[token] = now + 12 * 3600
        return token

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Avoid logging search queries, tokens, or torrent links.
            if len(args) > 1 and str(args[1]) != '200':
                print('PlexPort HTTP', args[1])

        def send(self, value, status=200, content_type='application/json; charset=utf-8', headers=None):
            body = json.dumps(value, ensure_ascii=False).encode() if isinstance(value, (dict, list)) else value
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
            for name, value in headers or []:
                self.send_header(name, value)
            if getattr(self, 'session_upgrade', None):
                self.send_header('Set-Cookie', self.session_cookie(self.session_upgrade))
            self.end_headers()
            self.wfile.write(body)

        def cookies(self):
            try:
                jar = SimpleCookie()
                jar.load(self.headers.get('Cookie', ''))
                return {name: value.value for name, value in jar.items()}
            except Exception:
                return {}

        def session_cookie(self, token, clear=False):
            # Browser HTTPS origins also cover a TLS reverse proxy without trusting forwarded headers.
            https_origin = self.headers.get('Origin') == 'https://' + self.headers.get('Host', '')
            secure = '; Secure' if hasattr(self.connection, 'cipher') or https_origin else ''
            return f'{cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict{secure}' + ('; Max-Age=0' if clear else '')

        def authenticated(self):
            self.authentication = 'none'
            if not password:
                return True
            jar = self.cookies()
            with auth_lock:
                if sessions.get(jar.get(cookie_name, ''), 0) > time.monotonic():
                    self.authentication = 'session'
                    return True
            expected = 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()
            if jar.get('plexport_signed_out') != '1' and hmac.compare_digest(self.headers.get('Authorization', ''), expected):
                self.authentication = 'basic'
                return True
            return False

        def native_client(self):
            # Existing Android WebViews rely on the HTTP authentication challenge.
            user_agent = self.headers.get('User-Agent', '')
            return 'Android' in user_agent and '; wv)' in user_agent

        def allowed(self, public=False):
            raw_host = self.headers.get('Host', '')
            parsed = urllib.parse.urlsplit('http://' + raw_host)
            if not password:
                hostname = parsed.hostname or ''
                try:
                    local = ipaddress.ip_address(hostname).is_loopback
                except ValueError:
                    local = hostname.lower() == 'localhost'
                if not local:
                    self.send({'error': 'Alleen lokale toegang toegestaan.'}, 403)
                    return False
            if not public and not self.authenticated():
                headers = []
                if self.native_client():
                    headers.append(('WWW-Authenticate', 'Basic realm="PlexPort", charset="UTF-8"'))
                self.send({'error': 'Meld je opnieuw aan bij PlexPort.'}, 401, headers=headers)
                return False
            if self.path.startswith(('/api/', '/auth/')):
                if self.headers.get('X-PlexPort') != '1':
                    self.send({'error': 'Ongeldig app-verzoek.'}, 403)
                    return False
                origin = self.headers.get('Origin')
                if origin and origin not in ('http://' + raw_host, 'https://' + raw_host):
                    self.send({'error': 'Verzoek vanaf een andere website geweigerd.'}, 403)
                    return False
            return True

        def do_GET(self):
            try:
                parsed = urllib.parse.urlsplit(self.path)
                public_assets = {'/login': 'login.html', '/login.js': 'login.js', '/theme.js': 'theme.js', '/style.css': 'style.css', '/favicon.svg': 'favicon.svg'}
                if parsed.path in public_assets:
                    if not self.allowed(public=True):
                        return
                    filename = public_assets[parsed.path]
                    self.send((STATIC / filename).read_bytes(), content_type=mimetypes.guess_type(filename)[0] or 'application/octet-stream')
                    return
                if parsed.path == '/' and not self.authenticated() and not self.native_client() and not self.headers.get('Authorization'):
                    if self.allowed(public=True):
                        self.send((STATIC / 'login.html').read_bytes(), content_type='text/html; charset=utf-8')
                    return
                if parsed.path == '/' and self.cookies().get('plexport_signed_out') == '1' and not self.authenticated() and not self.native_client():
                    if self.allowed(public=True):
                        self.send((STATIC / 'login.html').read_bytes(), content_type='text/html; charset=utf-8')
                    return
                if not self.allowed():
                    return
                if parsed.path == '/' and self.authentication == 'basic' and not self.native_client():
                    # Upgrade browser-cached Basic credentials to an explicit session.
                    self.session_upgrade = new_session()
                if parsed.path == '/api/status':
                    jobs = [public_job(j) for j in store.jobs()]
                    self.send({'jobs': jobs, 'checks': checks.copy(), 'configured_sources': len(store.settings()['sources']), 'authentication': self.authentication})
                elif parsed.path == '/api/settings':
                    self.send(public_settings(store.settings()))
                elif parsed.path == '/api/search':
                    params = urllib.parse.parse_qs(parsed.query)
                    query = params.get('q', [''])[0].strip()
                    kind = params.get('kind', ['movie'])[0]
                    if len(query) < 2 or len(query) > 200 or kind not in ('movie', 'tv'):
                        raise ValueError('Vul minimaal twee tekens in en kies film of serie.')
                    sources = store.settings()['sources']
                    if not sources:
                        raise ValueError('Voeg eerst een bron toe bij Instellingen, zoals WatchSoMuch of een Torznab-feed.')
                    results, errors = [], []
                    with ThreadPoolExecutor(max_workers=5) as pool:
                        futures = {pool.submit(search_source, source, query, kind): source for source in sources}
                        for future in as_completed(futures):
                            try:
                                results.extend(future.result())
                            except Exception as e:
                                errors.append({'source': futures[future]['name'], 'error': friendly_error(e)})
                    results.sort(key=lambda r: r['seeders'], reverse=True)
                    self.send({'results': results[:250], 'errors': errors})
                else:
                    names = {'/': 'index.html', '/app.js': 'app.js', '/discovery.js': 'discovery.js', '/theme.js': 'theme.js', '/style.css': 'style.css', '/favicon.svg': 'favicon.svg', '/plexport.apk': 'plexport.apk'}
                    filename = names.get(parsed.path)
                    if not filename:
                        self.send({'error': 'Niet gevonden.'}, 404)
                        return
                    content_type = 'application/vnd.android.package-archive' if filename.endswith('.apk') else mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                    self.send((STATIC / filename).read_bytes(), content_type=content_type)
            except Exception as e:
                self.send({'error': friendly_error(e)}, 400)

        def do_POST(self):
            try:
                login = self.path == '/auth/login'
                if not self.allowed(public=login):
                    return
                length = int(self.headers.get('Content-Length', 0))
                if length <= 0 or length > (4096 if login else 12 * 1024 * 1024):
                    raise ValueError('Verzoek ontbreekt of is te groot.')
                if self.headers.get_content_type() != 'application/json':
                    raise ValueError('JSON-verzoek vereist.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Ongeldig verzoek.')
                if login:
                    if not password:
                        self.send({'ok': True})
                        return
                    username, supplied = data.get('username'), data.get('password')
                    if not isinstance(username, str) or not isinstance(supplied, str):
                        raise ValueError('Vul je gebruikersnaam en wachtwoord in.')
                    now, address = time.monotonic(), self.client_address[0]
                    with auth_lock:
                        for key, attempts in list(failures.items()):
                            failures[key] = [t for t in attempts if t > now - 60]
                            if not failures[key]:
                                del failures[key]
                        attempts = failures.setdefault(address, [])
                        if len(attempts) >= 8:
                            self.send({'error': 'Te vaak geprobeerd. Wacht een minuut en probeer opnieuw.'}, 429, headers=[('Retry-After', '60')])
                            return
                        valid = hmac.compare_digest(username.encode(), b'admin') and hmac.compare_digest(supplied.encode(), password.encode())
                        if not valid:
                            attempts.append(now)
                        else:
                            failures.pop(address, None)
                    if not valid:
                        self.send({'error': 'De gebruikersnaam of het wachtwoord klopt niet. Probeer opnieuw.'}, 401)
                        return
                    self.send({'ok': True}, headers=[('Set-Cookie', self.session_cookie(new_session())), ('Set-Cookie', 'plexport_signed_out=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')])
                elif self.path == '/auth/logout':
                    with auth_lock:
                        sessions.pop(self.cookies().get(cookie_name, ''), None)
                    self.send({'ok': True}, headers=[('Set-Cookie', self.session_cookie('', clear=True)), ('Set-Cookie', 'plexport_signed_out=1; Path=/; HttpOnly; SameSite=Strict')])
                elif self.path == '/api/settings':
                    with worker.lock:
                        result = store.save_settings(data)
                        checks.clear()
                    self.send(result)
                elif self.path == '/api/jobs':
                    with worker.lock:
                        job = new_job(store.settings(), data)
                        for existing in store.jobs():
                            same = job['torrent_fingerprint'] == existing.get('torrent_fingerprint', existing['link'])
                            if same:
                                raise ValueError('Deze download staat al in PlexPort.')
                        require_storage(job['config'], job['kind'], job['expected_bytes'])
                        store.save_job(job)
                    self.send(public_job(job), 201)
                elif self.path == '/api/action':
                    self.send(worker.action(str(data.get('id', '')), str(data.get('action', '')),
                                            data.get('delete_files', False), data.get('forget', False)))
                elif self.path == '/api/preflight':
                    kind = data.get('kind', 'movie')
                    if kind not in ('movie', 'tv'):
                        raise ValueError('Kies film of serie.')
                    self.send(storage_report(store.settings(), kind, data.get('expected_bytes', 0)))
                elif self.path == '/api/test':
                    target = data.get('target')
                    config = store.settings()
                    try:
                        if target == 'downloader':
                            message = client(config['downloader']).test()
                            extra = {}
                        elif target == 'plex':
                            sections = plex_sections(config['plex'])
                            message = 'Plex bereikbaar · ' + str(len(sections)) + ' bibliotheken'
                            extra = {'sections': sections}
                        elif target == 'storage':
                            report = storage_report(config)
                            failed = next((f for f in report['folders'] if not f['ok']), None)
                            if failed:
                                checks[target] = {'ok': False, 'message': failed['message']}
                                self.send({'message': failed['message'], **report}, 400)
                                return
                            extra = {'folders': report['folders'], 'free': min(f['free'] for f in report['folders'])}
                            message = 'Download- en Plex-mappen zijn bereikbaar'
                        else:
                            raise ValueError('Onbekende verbinding.')
                        checks[target] = {'ok': True, 'message': message}
                        self.send({'ok': True, 'message': message, **extra})
                    except Exception as e:
                        message = friendly_error(e)
                        checks[target] = {'ok': False, 'message': message}
                        self.send({'ok': False, 'message': message}, 400)
                elif self.path == '/api/scan':
                    plex_scan(store.settings()['plex'], data.get('kind', 'movie'))
                    self.send({'message': 'Plex-bibliotheekscan aangevraagd.'})
                else:
                    self.send({'error': 'Niet gevonden.'}, 404)
            except Exception as e:
                self.send({'error': friendly_error(e)}, 400)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server, worker


def main():
    parser = argparse.ArgumentParser(description='PlexPort')
    parser.add_argument('--host', default=os.environ.get('PLEXPORT_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PLEXPORT_PORT', '8765')))
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    password = os.environ.get('PLEXPORT_PASSWORD', '')
    if args.host not in ('127.0.0.1', 'localhost', '::1') and not password:
        parser.error('Stel PLEXPORT_PASSWORD in voor toegang vanaf andere apparaten.')
    for path in [defaults()['downloader']['local_root'], *defaults()['library'].values()]:
        Path(path).mkdir(parents=True, exist_ok=True)
    store = Store(os.environ.get('PLEXPORT_DATA', './data'))
    server, worker = create_server(args.host, args.port, store, password)
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    print(f'PlexPort is beschikbaar op http://{args.host}:{args.port}')
    if args.open:
        webbrowser.open(f'http://127.0.0.1:{args.port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        worker.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
