import base64
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def http_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Gebruik een http(s)-adres zonder gebruikersnaam of wachtwoord in de URL.')
    return value.rstrip('/')


def request(url, data=None, headers=None, opener=None, with_status=False, timeout=20):
    http_url(url)
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with (opener or urllib.request.build_opener()).open(req, timeout=timeout) as response:
        result = response.read(12 * 1024 * 1024 + 1)
        if len(result) > 12 * 1024 * 1024:
            raise ValueError('Antwoord van de server is te groot.')
        return (response.status, result) if with_status else result


def single_torrent(torrent_id):
    if not isinstance(torrent_id, str) or not re.fullmatch(r'[a-fA-F0-9]{40}|[a-fA-F0-9]{64}', torrent_id):
        raise ValueError('Ongeldig torrent-ID. Er kan alleen één download worden gewijzigd.')
    return torrent_id


def same_download_dir(actual, expected):
    if not expected or actual.replace('\\', '/').rstrip('/') != expected.replace('\\', '/').rstrip('/'):
        raise ValueError('De downloadmap is veranderd. Verwijder de bestanden rechtstreeks in je downloader; PlexPort heeft niets gewist.')


class Transmission:
    def __init__(self, config):
        self.c = config
        self.session = ''

    def rpc(self, method, arguments=None):
        headers = {'Content-Type': 'application/json', 'X-Transmission-Session-Id': self.session}
        if self.c.get('username'):
            auth = base64.b64encode(f"{self.c['username']}:{self.c.get('password', '')}".encode()).decode()
            headers['Authorization'] = 'Basic ' + auth
        body = json.dumps({'method': method, 'arguments': arguments or {}}).encode()
        for attempt in range(2):
            try:
                result = json.loads(request(self.c['url'], body, headers))
                if result.get('result') != 'success':
                    raise ValueError('Transmission: ' + result.get('result', 'onbekend antwoord'))
                return result.get('arguments', {})
            except urllib.error.HTTPError as e:
                if e.code != 409 or attempt:
                    raise
                self.session = e.headers.get('X-Transmission-Session-Id', '')
                e.close()
                headers['X-Transmission-Session-Id'] = self.session

    def test(self):
        return 'Transmission ' + self.rpc('session-get').get('version', '')

    def find(self, job):
        existing = self.rpc('torrent-get', {'fields': ['hashString', 'downloadDir']})['torrents']
        matches = [t for t in existing if t['downloadDir'].rstrip('/') == job['remote_dir'].rstrip('/')]
        if len(matches) > 1:
            raise ValueError('Er staan meerdere torrents in deze downloadmap. Controleer je downloader.')
        return matches[0]['hashString'] if matches else ''

    def add(self, job):
        # Recover an accepted request after a process interruption before the ID was saved.
        existing = self.find(job)
        if existing:
            return existing
        args = {'download-dir': job['remote_dir'], 'paused': False}
        if job.get('metainfo'):
            args['metainfo'] = job['metainfo']
        else:
            args['filename'] = job['link']
        result = self.rpc('torrent-add', args)
        if 'torrent-duplicate' in result:
            raise ValueError('Deze torrent bestaat al in Transmission. Gebruik een andere torrent of verwijder eerst de oude taak in Transmission.')
        return result['torrent-added']['hashString']

    def status(self, torrent_id):
        items = self.rpc('torrent-get', {'ids': [torrent_id], 'fields': [
            'hashString', 'name', 'percentDone', 'rateDownload', 'eta', 'status',
            'error', 'errorString', 'files', 'fileStats', 'metadataPercentComplete', 'sizeWhenDone', 'peersConnected'
        ]})['torrents']
        if not items:
            raise ValueError('De torrent is niet meer aanwezig in Transmission.')
        t = items[0]
        if t['error']:
            raise ValueError('Transmission: ' + t['errorString'])
        files = [f for i, f in enumerate(t['files']) if t['fileStats'][i]['wanted']]
        complete = (t['metadataPercentComplete'] == 1 and t['sizeWhenDone'] > 0
                    and t['percentDone'] >= 1 and t['status'] not in (1, 2)
                    and all(f['bytesCompleted'] == f['length'] for f in files))
        activity = {0: 'paused', 1: 'queued', 2: 'checking', 3: 'queued',
                    4: 'downloading', 5: 'seeding', 6: 'seeding'}.get(t['status'], 'unknown')
        if t['status'] == 4:
            if t['metadataPercentComplete'] < 1:
                activity = 'metadata'
            elif t['rateDownload'] == 0 and t.get('peersConnected', 0) == 0:
                activity = 'waiting'
        return {'progress': t['percentDone'], 'speed': t['rateDownload'], 'eta': t['eta'],
                'paused': t['status'] == 0, 'complete': complete,
                'activity': activity,
                'files': [{'name': f['name'], 'size': f['length']} for f in files]}

    def action(self, torrent_id, action):
        self.rpc('torrent-stop' if action == 'pause' else 'torrent-start', {'ids': [single_torrent(torrent_id)]})

    def remove(self, torrent_id, delete_files=False, expected_dir=None):
        torrent_id = single_torrent(torrent_id)
        if delete_files:
            items = self.rpc('torrent-get', {'ids': [torrent_id], 'fields': ['hashString', 'downloadDir']})['torrents']
            if not items:
                raise ValueError('De torrent is al uit Transmission verwijderd. Verwijder de overgebleven bestanden zelf of kies bestanden behouden.')
            same_download_dir(items[0]['downloadDir'], expected_dir)
        self.rpc('torrent-remove', {'ids': [torrent_id], 'delete-local-data': delete_files})


class QBittorrent:
    def __init__(self, config):
        self.c = config
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        if config.get('username'):
            try:
                status, result = self.call('auth/login', {'username': config['username'], 'password': config.get('password', '')}, with_status=True)
            except urllib.error.HTTPError as error:
                if error.code == 401:
                    error.close()
                    raise ValueError('qBittorrent: aanmelden mislukt. Controleer je gebruikersnaam en Web UI-wachtwoord.') from None
                raise
            # qBittorrent 5.2 returns 204 and a port-specific session cookie.
            if status != 204 and result.strip() != b'Ok.':
                raise ValueError('qBittorrent: aanmelden mislukt. Controleer je gebruikersnaam en wachtwoord.')

    def call(self, endpoint, data=None, with_status=False):
        headers = {'Referer': self.c['url'].rstrip('/') + '/'}
        return request(self.c['url'].rstrip('/') + '/api/v2/' + endpoint,
                       urllib.parse.urlencode(data).encode() if data is not None else None, headers, self.opener, with_status)

    def test(self):
        return 'qBittorrent ' + self.call('app/version').decode()

    def find(self, job):
        tag = 'plexport-' + job['id']
        existing = json.loads(self.call('torrents/info?' + urllib.parse.urlencode({'tag': tag})))
        if len(existing) > 1:
            raise ValueError('Er staan meerdere torrents bij deze taak. Controleer qBittorrent.')
        return existing[0]['hash'] if existing else ''

    def add(self, job):
        tag = 'plexport-' + job['id']
        existing = self.find(job)
        if existing:
            return existing
        data = {'savepath': job['remote_dir'], 'tags': tag, 'autoTMM': 'false'}
        if job.get('metainfo'):
            boundary = 'PlexPort' + job['id']
            body = b''
            for key, value in data.items():
                body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="torrents"; filename="download.torrent"\r\nContent-Type: application/x-bittorrent\r\n\r\n'.encode()
            body += base64.b64decode(job['metainfo']) + f'\r\n--{boundary}--\r\n'.encode()
            result = request(self.c['url'].rstrip('/') + '/api/v2/torrents/add', body,
                             {'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Referer': self.c['url'].rstrip('/') + '/'}, self.opener)
        else:
            data['urls'] = job['link']
            result = self.call('torrents/add', data)
        if result.strip() != b'Ok.':
            try:
                added = json.loads(result)
            except (ValueError, UnicodeDecodeError):
                added = None
            # New API replies describe synchronous additions or pending metadata.
            valid_counts = isinstance(added, dict) and all(
                type(added.get(key)) is int and added[key] >= 0
                for key in ('success_count', 'failure_count', 'pending_count'))
            if not valid_counts or added['failure_count'] or not (added['success_count'] + added['pending_count']):
                raise ValueError('qBittorrent heeft de torrent niet geaccepteerd.')
        # qBittorrent inserts asynchronously. The worker retries the tagged lookup.
        return ''

    def status(self, torrent_id):
        items = json.loads(self.call('torrents/info?' + urllib.parse.urlencode({'hashes': torrent_id})))
        if not items:
            raise ValueError('De torrent is niet meer aanwezig in qBittorrent.')
        t = items[0]
        if t['state'] in ('error', 'missingFiles'):
            raise ValueError('qBittorrent: ' + t['state'] + '. Controleer opslagruimte en bestanden.')
        files = json.loads(self.call('torrents/files?' + urllib.parse.urlencode({'hash': torrent_id})))
        files = [f for f in files if f.get('priority', 1) > 0]
        complete = (t['progress'] >= 1 and t.get('amount_left', 0) == 0 and t.get('size', 0) > 0
                    and 'checking' not in t['state'].lower() and 'meta' not in t['state'].lower() and t['state'] != 'moving'
                    and all(f['progress'] == 1 for f in files))
        state = t['state']
        activity = ('checking' if 'checking' in state.lower() else
                    'metadata' if 'meta' in state.lower() else
                    'paused' if state.startswith(('paused', 'stopped')) else
                    'queued' if state.startswith('queued') else
                    'waiting' if state == 'stalledDL' else
                    'moving' if state == 'moving' else
                    'allocating' if state == 'allocating' else
                    'seeding' if state.endswith('UP') or state == 'uploading' else
                    'downloading' if state in ('downloading', 'forcedDL') else 'unknown')
        return {'progress': t['progress'], 'speed': t['dlspeed'], 'eta': t['eta'],
                'paused': t['state'] in ('pausedDL', 'stoppedDL'), 'complete': complete,
                'activity': activity,
                'files': [{'name': f['name'], 'size': f['size']} for f in files]}

    def action(self, torrent_id, action):
        torrent_id = single_torrent(torrent_id)
        version = self.call('app/version').decode().lstrip('v')
        endpoint = ('stop' if action == 'pause' else 'start') if int(version.split('.')[0]) >= 5 else ('pause' if action == 'pause' else 'resume')
        self.call('torrents/' + endpoint, {'hashes': torrent_id})

    def remove(self, torrent_id, delete_files=False, expected_dir=None):
        torrent_id = single_torrent(torrent_id)
        if delete_files:
            items = json.loads(self.call('torrents/info?' + urllib.parse.urlencode({'hashes': torrent_id})))
            if not items:
                raise ValueError('De torrent is al uit qBittorrent verwijderd. Verwijder de overgebleven bestanden zelf of kies bestanden behouden.')
            same_download_dir(items[0].get('save_path', ''), expected_dir)
        self.call('torrents/delete', {'hashes': torrent_id, 'deleteFiles': 'true' if delete_files else 'false'})


def client(config):
    return QBittorrent(config) if config['type'] == 'qbittorrent' else Transmission(config)


def plex_sections(config):
    if not config.get('url') or not config.get('token'):
        raise ValueError('Vul het Plex-adres en je Plex-token in bij Instellingen.')
    body = request(http_url(config['url']) + '/library/sections', headers={'X-Plex-Token': config['token']})
    root = ET.fromstring(body)
    return [{'id': e.attrib['key'], 'title': e.attrib.get('title', ''), 'type': e.attrib.get('type', '')} for e in root.findall('Directory')]


def plex_scan(config, kind):
    key = config.get('movie_section' if kind == 'movie' else 'tv_section')
    if not key:
        raise ValueError('Kies de bijbehorende Plex-bibliotheek bij Instellingen.')
    if not re_section(key):
        raise ValueError('Ongeldig Plex-bibliotheeknummer.')
    request(http_url(config['url']) + '/library/sections/' + key + '/refresh', headers={'X-Plex-Token': config['token']})


def re_section(value):
    return isinstance(value, str) and value.isdigit()


def search_source(source, query, kind, mode='title'):
    if source.get('type') == 'watchsomuch':
        from .watchsomuch import search
        return search(source, query, kind, mode)
    parsed = urllib.parse.urlsplit(http_url(source['url']))
    params = dict(urllib.parse.parse_qsl(parsed.query))
    params.update({'t': 'search', 'q': query, 'apikey': source.get('api_key', ''), 'cat': '2000' if kind == 'movie' else '5000', 'limit': '50'})
    url = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(params)))
    root = ET.fromstring(request(url))
    if root.tag == 'error':
        raise ValueError('De bron heeft de zoekopdracht geweigerd. Controleer de API-sleutel.')
    results = []
    for item in root.findall('.//item'):
        attrs = {e.attrib.get('name'): e.attrib.get('value') for e in item if e.tag.endswith('attr')}
        enclosure = item.find('enclosure')
        link = attrs.get('magneturl') or (enclosure.attrib.get('url') if enclosure is not None else None) or item.findtext('link')
        if not link:
            continue
        def number(value):
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0
        results.append({'title': item.findtext('title', 'Naamloos'), 'link': link, 'source': source['name'],
                        'size': number(item.findtext('size') or (enclosure.attrib.get('length') if enclosure is not None else 0)),
                        'seeders': number(attrs.get('seeders')), 'published': item.findtext('pubDate', '')})
    return results
