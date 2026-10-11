import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import threading
import urllib.parse
import webbrowser

from .core import Store, Worker, defaults, friendly_error, new_job, public_job, public_settings
from .integrations import client, plex_scan, plex_sections, search_source

STATIC = Path(__file__).parent / 'static'


def create_server(host, port, store, password=''):
    worker = Worker(store)
    checks = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Avoid logging search queries, tokens, or torrent links.
            if len(args) > 1 and str(args[1]) != '200':
                print('PlexPort HTTP', args[1])

        def send(self, value, status=200, content_type='application/json; charset=utf-8'):
            body = json.dumps(value, ensure_ascii=False).encode() if isinstance(value, (dict, list)) else value
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
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
            if password:
                expected = 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()
                if not hmac.compare_digest(self.headers.get('Authorization', ''), expected):
                    self.send_response(401)
                    self.send_header('WWW-Authenticate', 'Basic realm="PlexPort", charset="UTF-8"')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return False
            if self.path.startswith('/api/'):
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
                if not self.allowed():
                    return
                parsed = urllib.parse.urlsplit(self.path)
                if parsed.path == '/api/status':
                    jobs = [public_job(j) for j in store.jobs()]
                    self.send({'jobs': jobs, 'checks': checks.copy(), 'configured_sources': len(store.settings()['sources'])})
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
                    names = {'/': 'index.html', '/app.js': 'app.js', '/theme.js': 'theme.js', '/style.css': 'style.css', '/favicon.svg': 'favicon.svg', '/plexport.apk': 'plexport.apk'}
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
                if not self.allowed():
                    return
                length = int(self.headers.get('Content-Length', 0))
                if length <= 0 or length > 12 * 1024 * 1024:
                    raise ValueError('Verzoek ontbreekt of is te groot.')
                if self.headers.get_content_type() != 'application/json':
                    raise ValueError('JSON-verzoek vereist.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Ongeldig verzoek.')
                if self.path == '/api/settings':
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
                        store.save_job(job)
                    self.send(public_job(job), 201)
                elif self.path == '/api/action':
                    self.send(worker.action(str(data.get('id', '')), str(data.get('action', ''))))
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
                            import shutil
                            paths = [config['downloader']['local_root'], config['library']['movies'], config['library']['tv']]
                            for path in paths:
                                if not Path(path).is_dir() or not os.access(path, os.W_OK):
                                    raise ValueError('Map bestaat niet of is niet schrijfbaar: ' + path)
                            extra = {'free': shutil.disk_usage(config['library']['movies']).free}
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
