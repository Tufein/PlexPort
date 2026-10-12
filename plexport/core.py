import base64
import copy
from contextlib import contextmanager
import errno
import json
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sqlite3
import threading
import tempfile
import time
import urllib.error
import urllib.parse
import uuid

from .integrations import client, http_url, plex_scan

VIDEO = {'.mkv', '.mp4', '.m4v', '.avi', '.mov', '.ts', '.webm', '.mpg', '.mpeg'}
SUBTITLE = {'.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx'}
SECRETS = {'password', 'token', 'api_key'}
DEFAULT_PREFERENCES = {'quality': 'all', 'max_gb': 0, 'min_seeders': 0, 'sort': 'seeders'}
PREFERENCE_CHOICES = {'quality': ('all', '1080', '720', '2160', 'sd', 'unknown'),
                      'max_gb': (0, 2, 4, 10, 25), 'min_seeders': (0, 1, 5, 20),
                      'sort': ('seeders', 'smallest', 'title')}


def download_size(value):
    if type(value) is not int or not 0 <= value <= 1024 ** 5:
        raise ValueError('Ongeldige bestandsgrootte. Kies de download opnieuw.')
    return value


def storage_report(config, kind=None, expected_bytes=0):
    """Probe only configured directories; never create missing mounts."""
    expected_bytes = download_size(expected_bytes)
    paths = [('downloads', 'Downloadmap', config['downloader']['local_root'])]
    if kind != 'tv':
        paths.append(('movies', 'Filmmap', config['library']['movies']))
    if kind != 'movie':
        paths.append(('tv', 'Seriemap', config['library']['tv']))
    folders = []
    for key, label, value in paths:
        entry = {'key': key, 'label': label, 'ok': False, 'free': None}
        try:
            path = Path(value)
            if not path.is_dir():
                raise ValueError(label + ' is niet bereikbaar. Controleer de mapkoppeling bij Instellingen.')
            # A permissions flag alone does not verify writable SMB/NFS mounts or ACLs.
            with tempfile.TemporaryFile(prefix='.plexport-check-', dir=path) as probe:
                probe.write(b'1')
                probe.flush()
                os.fsync(probe.fileno())
            entry['free'] = shutil.disk_usage(path).free
            if key == 'downloads' and expected_bytes and entry['free'] < expected_bytes:
                raise ValueError('De downloadmap heeft te weinig vrije ruimte voor deze versie. Kies een kleiner bestand of maak ruimte vrij.')
            entry.update(ok=True, message='Bereikbaar en schrijfbaar')
        except Exception as error:
            entry['message'] = friendly_error(error)
        folders.append(entry)
    warnings = []
    if not expected_bytes:
        warnings.append('De bestandsgrootte is nog onbekend. Vrije ruimte is geen garantie dat de hele download past.')
    elif any(f['key'] != 'downloads' and f['ok'] and f['free'] < expected_bytes for f in folders):
        warnings.append('De mediamap heeft mogelijk extra ruimte nodig als PlexPort de video moet kopiëren.')
    return {'ok': all(f['ok'] for f in folders), 'folders': folders, 'warnings': warnings,
            'expected_bytes': expected_bytes,
            'note': 'Deze controle test de mappen van PlexPort. De downloader moet dezelfde downloadmap gebruiken. Andere downloads kunnen ondertussen ruimte innemen.'}


def require_storage(config, kind, expected_bytes=0):
    report = storage_report(config, kind, expected_bytes)
    for folder in report['folders']:
        if not folder['ok']:
            raise ValueError(folder['message'])
    return report


def defaults():
    media = Path(os.environ.get('PLEXPORT_MEDIA', './media')).resolve()
    downloads = str(Path(os.environ.get('PLEXPORT_DOWNLOADS', './downloads')).resolve())
    downloader_type = os.environ.get('DOWNLOADER_TYPE', 'qbittorrent')
    return {'downloader': {'type': downloader_type, 'url': os.environ.get('TRANSMISSION_URL', 'http://127.0.0.1:9091/transmission/rpc') if downloader_type == 'transmission' else os.environ.get('QBITTORRENT_URL', ''),
                           'username': os.environ.get('TRANSMISSION_USER', '') if downloader_type == 'transmission' else os.environ.get('QBITTORRENT_USER', ''), 'password': os.environ.get('TRANSMISSION_PASSWORD', '') if downloader_type == 'transmission' else '',
                           'remote_root': os.environ.get('DOWNLOADER_ROOT', downloads), 'local_root': downloads},
            'library': {'movies': str(media / 'Movies'), 'tv': str(media / 'TV Shows')},
            'plex': {'url': '', 'token': '', 'movie_section': '', 'tv_section': ''}, 'sources': [],
            'preferences': DEFAULT_PREFERENCES.copy()}


def public_settings(config):
    def redact(value):
        if isinstance(value, list):
            return [redact(v) for v in value]
        if isinstance(value, dict):
            result = {}
            for key, v in value.items():
                if key in SECRETS:
                    result[key + '_set'] = bool(v)
                else:
                    result[key] = redact(v)
            return result
        return value
    return redact(config)


def merge_settings(previous, incoming):
    if not isinstance(incoming, dict):
        raise ValueError('Ongeldige instellingen.')
    result = copy.deepcopy(previous)
    result['preferences'] = {**DEFAULT_PREFERENCES, **previous.get('preferences', {})}
    if 'preferences' in incoming:
        preferences = incoming['preferences']
        if not isinstance(preferences, dict):
            raise ValueError('Ongeldige zoekvoorkeuren.')
        if set(preferences) - set(DEFAULT_PREFERENCES):
            raise ValueError('Onbekende zoekvoorkeur.')
        for key, value in preferences.items():
            expected_type = int if key in ('max_gb', 'min_seeders') else str
            if type(value) is not expected_type or value not in PREFERENCE_CHOICES[key]:
                raise ValueError('Ongeldige zoekvoorkeur: ' + key)
            result['preferences'][key] = value
    for group in ('downloader', 'library', 'plex'):
        for key in previous[group]:
            if key in incoming.get(group, {}):
                value = incoming[group][key]
                if not isinstance(value, str) or len(value) > 4096:
                    raise ValueError('Ongeldige instelling: ' + key)
                result[group][key] = value.strip() if key not in SECRETS else value
    if result['downloader']['type'] not in ('transmission', 'qbittorrent'):
        raise ValueError('Kies Transmission of qBittorrent.')
    if result['downloader']['url']:
        http_url(result['downloader']['url'])
    if result['plex']['url']:
        http_url(result['plex']['url'])
    for group, keys in (('downloader', ('local_root',)), ('library', ('movies', 'tv'))):
        for key in keys:
            if not Path(result[group][key]).is_absolute():
                raise ValueError('Gebruik een volledig mappad voor ' + key + '.')
    remote = result['downloader']['remote_root']
    if not (PurePosixPath(remote).is_absolute() or PureWindowsPath(remote).is_absolute()):
        raise ValueError('Gebruik een volledig downloadpad voor de downloader.')
    roots = [Path(result['downloader']['local_root']).resolve(), Path(result['library']['movies']).resolve(), Path(result['library']['tv']).resolve()]
    for i, root in enumerate(roots):
        for other in roots[i + 1:]:
            if root == other or root in other.parents or other in root.parents:
                raise ValueError('Downloadmap, filmmap en seriemap moeten afzonderlijke mappen zijn.')
    if 'sources' in incoming:
        if not isinstance(incoming['sources'], list) or len(incoming['sources']) > 20:
            raise ValueError('Maximaal 20 bronnen toegestaan.')
        old = {s['id']: s for s in previous['sources']}
        sources = []
        for source in incoming['sources']:
            if not isinstance(source, dict):
                raise ValueError('Ongeldige bron.')
            sid = str(source.get('id') or uuid.uuid4().hex)
            name = str(source.get('name', '')).strip()[:120]
            if not name:
                raise ValueError('Geef iedere bron een naam.')
            source_type = source.get('type', old.get(sid, {}).get('type', 'torznab'))
            if source_type not in ('torznab', 'watchsomuch'):
                raise ValueError('Onbekend brontype.')
            url = 'https://watchsomuch.to' if source_type == 'watchsomuch' else http_url(str(source.get('url', '')))
            sources.append({'id': sid, 'name': name, 'type': source_type, 'url': url,
                            'api_key': str(source.get('api_key', old.get(sid, {}).get('api_key', '')))})
        if len({s['id'] for s in sources}) != len(sources):
            raise ValueError('Dubbele bron-ID.')
        result['sources'] = sources
    return result


class Store:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / 'plexport.sqlite'
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO settings VALUES (1, ?)', (json.dumps(defaults()),))
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def settings(self):
        with self.lock, self.connect() as db:
            config = json.loads(db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])
            # Existing databases gain defaults in memory; reading never changes them.
            config['preferences'] = {**DEFAULT_PREFERENCES, **config.get('preferences', {})}
            return config

    def save_settings(self, incoming):
        with self.lock, self.connect() as db:
            config = merge_settings(self.settings(), incoming)
            db.execute('UPDATE settings SET body=? WHERE id=1', (json.dumps(config),))
            return public_settings(config)

    def jobs(self):
        with self.lock, self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT body FROM jobs ORDER BY rowid DESC')]

    def job(self, job_id):
        with self.lock, self.connect() as db:
            row = db.execute('SELECT body FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row:
                raise ValueError('Download niet gevonden.')
            return json.loads(row[0])

    def save_job(self, job):
        with self.lock, self.connect() as db:
            db.execute('INSERT INTO jobs VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body', (job['id'], json.dumps(job)))

    def delete_job(self, job_id):
        with self.lock, self.connect() as db:
            db.execute('DELETE FROM jobs WHERE id=?', (job_id,))


def clean_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', str(value))
    value = re.sub(r'\s+', ' ', value).strip(' .')[:180]
    if not value or value in ('.', '..'):
        raise ValueError('Vul een geldige film- of serienaam in.')
    if re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', value):
        value = '_' + value
    return value


def new_job(config, data):
    if not config['downloader'].get('url'):
        raise ValueError('Vul eerst het adres van je qBittorrent of Transmission in bij Instellingen.')
    kind = data.get('kind', 'movie')
    if kind not in ('movie', 'tv'):
        raise ValueError('Kies film of serie.')
    expected_bytes = download_size(data.get('expected_bytes', 0))
    title = clean_name(data.get('title', ''))
    link, metainfo = str(data.get('link', '')).strip(), data.get('metainfo', '')
    if bool(link) == bool(metainfo):
        raise ValueError('Voeg één magnetlink, torrent-URL of torrentbestand toe.')
    if metainfo:
        try:
            binary = base64.b64decode(metainfo, validate=True)
        except Exception:
            raise ValueError('Ongeldig torrentbestand.') from None
        if len(binary) > 8 * 1024 * 1024 or not binary.startswith(b'd'):
            raise ValueError('Ongeldig of te groot torrentbestand (maximaal 8 MB).')
    elif link.startswith('magnet:?'):
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)
        if not any(v.startswith(('urn:btih:', 'urn:btmh:')) for v in params.get('xt', [])):
            raise ValueError('De magnetlink bevat geen torrent-ID.')
    else:
        http_url(link)
    year = str(data.get('year', '')).strip()
    if year and not re.fullmatch(r'(18|19|20|21)\d{2}', year):
        raise ValueError('Gebruik een jaartal van vier cijfers.')
    def optional_number(key):
        value = data.get(key, '')
        if value in ('', None):
            return None
        if not str(value).isdigit() or not 0 <= int(value) <= 999:
            raise ValueError('Ongeldig seizoen- of afleveringsnummer.')
        return int(value)
    sid = uuid.uuid4().hex
    c = {k: copy.deepcopy(config[k]) for k in ('downloader', 'library', 'plex')}
    local_dir = str(Path(c['downloader']['local_root']) / sid)
    remote_root = c['downloader']['remote_root']
    remote_dir = str(PureWindowsPath(remote_root) / sid) if PureWindowsPath(remote_root).drive else str(PurePosixPath(remote_root) / sid)
    return {'id': sid, 'title': title, 'year': year, 'kind': kind, 'season': optional_number('season'),
            'episode': optional_number('episode'), 'link': link, 'metainfo': metainfo,
            'torrent_fingerprint': hashlib.sha256(binary).hexdigest() if metainfo else link,
            'source': str(data.get('source', 'Handmatig'))[:120], 'config': c, 'local_dir': local_dir,
            'remote_dir': remote_dir, 'state': 'queued', 'torrent_id': '', 'created': time.time(),
            'progress': 0, 'speed': 0, 'eta': -1, 'error': '', 'files_imported': [], 'paused': False,
            'expected_bytes': expected_bytes, 'activity': 'queued'}


def public_job(job):
    return {k: v for k, v in job.items() if k not in {'config', 'metainfo', 'link', 'remote_dir', 'local_dir', 'torrent_fingerprint'}}


def safe_file(root, name):
    p = PurePosixPath(name.replace('\\', '/'))
    if p.is_absolute() or '..' in p.parts or PureWindowsPath(name).drive:
        raise ValueError('Onveilig bestandspad in torrent.')
    target = (root / str(p)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Bestand valt buiten de ingestelde map.')
    return target


def publish_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if os.path.samefile(source, destination):
            return
        # An interrupted import may already have published a copy; compare exact bytes.
        if source.stat().st_size == destination.stat().st_size:
            with source.open('rb') as a, destination.open('rb') as b:
                while True:
                    first, second = a.read(1024 * 1024), b.read(1024 * 1024)
                    if first != second:
                        break
                    if not first:
                        return
        raise ValueError('Bestand bestaat al met andere inhoud: ' + destination.name)
    temp = destination.parent / ('.plexport-' + uuid.uuid4().hex + '.part')
    try:
        try:
            os.link(source, temp)
        except OSError as e:
            if e.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.ENOTSUP):
                raise
            if shutil.disk_usage(destination.parent).free < source.stat().st_size:
                raise ValueError('Te weinig vrije ruimte om deze video naar de mediamap te kopiëren. Maak ruimte vrij en kies Opnieuw proberen.')
            shutil.copy2(source, temp)
        # Reserve the final name without replacing an existing library file.
        # Use exclusive creation for shares where hardlinks are unsupported.
        try:
            os.link(temp, destination)
        except OSError as e:
            if e.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.ENOTSUP):
                raise
            # rename is atomic on the same share; protect with the single import worker.
            if destination.exists():
                raise ValueError('Bestand bestaat al: ' + destination.name)
            os.rename(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def import_media(job, files):
    root = Path(job['local_dir']).resolve()
    candidates = []
    for f in files:
        path = safe_file(root, f['name'])
        if path.suffix.lower() not in VIDEO | SUBTITLE:
            continue
        if not path.is_file() or path.stat().st_size != f['size']:
            raise ValueError('Downloadbestand nog niet bereikbaar of onvolledig. Controleer de gedeelde downloadmap: ' + f['name'])
        if re.search(r'(?i)(?:^|[ ._\-/])sample(?:[ ._\-/]|$)', f['name']):
            continue
        candidates.append((f, path))
    videos = [p for _, p in candidates if p.suffix.lower() in VIDEO]
    if not videos:
        raise ValueError('Geen ondersteunde videobestanden gevonden. Uitgepakte video is vereist; archieven worden niet geïmporteerd.')
    title = job['title'] + (f" ({job['year']})" if job['year'] else '')
    library = Path(job['config']['library']['movies' if job['kind'] == 'movie' else 'tv']).resolve()
    if not library.is_dir():
        raise ValueError('De Plex-mediamap bestaat niet of is niet gemount: ' + str(library))
    main = max(videos, key=lambda p: p.stat().st_size)
    plan = []
    for f, path in candidates:
        if job['kind'] == 'movie':
            base = title if path == main else path.stem
            if path.suffix.lower() in SUBTITLE:
                # Keep language suffixes (e.g. .nl.forced) while matching the main video.
                suffix = path.stem[len(main.stem):] if path.stem.startswith(main.stem) else ''
                base = title + suffix if suffix or path.stem == main.stem else path.stem
            name = title + '/' + clean_name(base) + path.suffix.lower()
        else:
            match = re.search(r'(?i)S(\d{1,3})[ ._-]*E(\d{1,3})((?:E\d{1,3})*)', path.stem)
            if match:
                season, episode = int(match[1]), int(match[2])
                extra = match[3].upper()
            elif job['season'] is not None and job['episode'] is not None and len(videos) == 1:
                season, episode, extra = job['season'], job['episode'], ''
            else:
                raise ValueError('Afleveringsnummer ontbreekt in ' + path.name + '. Gebruik S01E01 in bestandsnamen of vul seizoen en aflevering in voor één aflevering.')
            languages = re.search(r'(?i)((?:\.[a-z]{2,3})?(?:\.forced|\.sdh)?)$', path.stem) if path.suffix.lower() in SUBTITLE else None
            lang = languages[1] if languages else ''
            name = f'{title}/Season {season:02d}/{title} - S{season:02d}E{episode:02d}{extra}{lang}{path.suffix.lower()}'
        destination = safe_file(library, name)
        if destination.is_relative_to(root) or root.is_relative_to(destination.parent):
            raise ValueError('Downloadmap en Plex-map mogen niet overlappen.')
        plan.append((path, destination))
    if len({str(dest) for _, dest in plan}) != len(plan):
        raise ValueError('Meerdere bestanden zouden dezelfde Plex-naam krijgen. Controleer de torrent.')
    imported = []
    for source, destination in plan:
        publish_file(source, destination)
        imported.append(str(destination))
    return imported


def friendly_error(error):
    if isinstance(error, urllib.error.HTTPError):
        error.close()
        return f'De gekoppelde server antwoordt met HTTP {error.code}. Controleer adres en toegangsgegevens.'
    if isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return 'De gekoppelde server is niet bereikbaar. Controleer of hij draait en of het adres klopt.'
    if isinstance(error, PermissionError):
        return 'Geen toegang tot de ingestelde map. Controleer de schrijfrechten en netwerkverbinding.'
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return 'Onvoldoende vrije ruimte in de doelmap.'
    if isinstance(error, ValueError):
        return str(error)[:800]
    return 'Verwerking mislukt. Controleer de gekoppelde diensten en mappen en probeer opnieuw.'


class Worker:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.stop = threading.Event()

    def step(self, job):
        state = job['state']
        if state == 'queued':
            if not (job.get('add_started') or job.get('torrent_id')):
                require_storage(job['config'], job['kind'], job.get('expected_bytes', 0))
            if not Path(job['config']['downloader']['local_root']).is_dir():
                raise ValueError('De downloadmap bestaat niet of is niet gemount. Controleer de instellingen.')
            Path(job['local_dir']).mkdir(parents=True, exist_ok=True)
            if not job.get('metainfo'):
                from .watchsomuch import resolve
                resolved = resolve(job['link'])
                if resolved != job['link']:
                    job['link'] = resolved
                    self.store.save_job(job)
            c = client(job['config']['downloader'])
            # A request may be accepted even if its response or our process is lost.
            # Keep this marker before adding so retries cannot silently switch servers.
            job['add_started'] = True
            self.store.save_job(job)
            job['torrent_id'] = c.add(job)
            job['add_attempts'] = job.get('add_attempts', 0) + 1
            if job['torrent_id']:
                job['state'] = 'downloading'
                job['metainfo'] = ''
            elif job['add_attempts'] >= 5:
                raise ValueError('qBittorrent heeft geen nieuwe taak aangemaakt. De torrent bestaat mogelijk al; controleer qBittorrent.')
            self.store.save_job(job)
        elif state == 'downloading':
            status = client(job['config']['downloader']).status(job['torrent_id'])
            job.update({k: status[k] for k in ('progress', 'speed', 'eta', 'paused')})
            job['activity'] = status.get('activity', 'paused' if status['paused'] else 'downloading')
            if status['complete']:
                job['files'] = status['files']
                job['state'] = 'importing'
                job['speed'] = 0
            self.store.save_job(job)
        elif state == 'importing':
            job['files_imported'] = import_media(job, job['files'])
            job['state'] = 'scan_pending' if job['config']['plex'].get('url') and job['config']['plex'].get('token') else 'done'
            job['scan_requested'] = False
            job['finished'] = time.time()
            self.store.save_job(job)
        elif state == 'scan_pending':
            # Current Plex credentials/library selection may have been repaired since the download.
            plex_scan(self.store.settings()['plex'], job['kind'])
            job['scan_requested'] = True
            job['state'] = 'done'
            self.store.save_job(job)

    def tick(self):
        for item in self.store.jobs():
            with self.lock:
                try:
                    job = self.store.job(item['id'])
                except ValueError:
                    # A user can remove a task after this tick's snapshot was read.
                    continue
                if job['state'] in ('done', 'error', 'stopped'):
                    continue
                try:
                    self.step(job)
                except Exception as e:
                    job['retry_state'] = job['state']
                    job['state'] = 'error'
                    job['speed'] = 0
                    job['error'] = friendly_error(e)
                    self.store.save_job(job)

    def run(self):
        while not self.stop.is_set():
            self.tick()
            self.stop.wait(4)

    def action(self, job_id, action, delete_files=False, forget=False):
        if type(delete_files) is not bool or type(forget) is not bool:
            raise ValueError('Ongeldige keuze voor verwijderen.')
        if ((delete_files or forget) and action != 'remove') or (delete_files and forget):
            raise ValueError('Ongeldige keuze voor verwijderen.')
        with self.lock:
            job = self.store.job(job_id)
            if action in ('stop', 'remove') or (action == 'resume' and job['state'] == 'stopped'):
                c = None
                if not forget and (job.get('torrent_id') or job.get('add_started')):
                    config = copy.deepcopy(job['config']['downloader'])
                    current = self.store.settings()['downloader']
                    if config['type'] == current['type'] and config['url'].rstrip('/') == current['url'].rstrip('/'):
                        for key in ('username', 'password'):
                            config[key] = current[key]
                    c = client(config)
                    if not job.get('torrent_id'):
                        job['torrent_id'] = c.find(job)
                        if not job['torrent_id']:
                            raise ValueError('Je downloader heeft nog geen torrent-ID voor deze taak. Probeer straks opnieuw of controleer de taak in je downloader. Je kunt ook alleen de taak uit de lijst halen.')
                        self.store.save_job(job)
                if action == 'remove':
                    if c:
                        c.remove(job['torrent_id'], delete_files, job['remote_dir'])
                    self.store.delete_job(job_id)
                    return {'removed': True, 'id': job_id, 'files_deleted': delete_files and c is not None, 'forgotten': forget}
                if c:
                    c.action(job['torrent_id'], 'pause' if action == 'stop' else 'resume')
                if action == 'stop':
                    if job['state'] != 'stopped':
                        job['resume_state'] = job['state']
                    job.update(state='stopped', paused=True, speed=0, eta=-1, activity='paused')
                else:
                    restored = job.pop('resume_state', 'downloading' if job.get('torrent_id') else 'queued')
                    if restored == 'queued' and job.get('torrent_id'):
                        restored = 'downloading'
                    job.update(state=restored, paused=False, activity='queued' if restored == 'queued' else 'unknown')
            elif action == 'retry':
                if job['state'] != 'error':
                    raise ValueError('Deze download heeft geen fout om opnieuw te proberen.')
                retry_state = job.get('retry_state', 'downloading' if job['torrent_id'] else 'queued')
                current = self.store.settings()
                saved_client = job['config']['downloader']
                same_endpoint = (current['downloader']['type'] == saved_client['type']
                                 and current['downloader']['url'].rstrip('/') == saved_client['url'].rstrip('/'))
                submitted = bool(job['torrent_id'] or job.get('add_started') or job.get('add_attempts', 0))
                if retry_state == 'queued' and submitted and not same_endpoint:
                    raise ValueError('Deze download wacht nog op antwoord van de oorspronkelijke downloader. '
                                     'Controleer of de torrent daar bestaat voordat je hem naar een andere downloader verplaatst.')
                job['state'] = job.pop('retry_state', retry_state)
                job['error'] = ''
                job['add_attempts'] = 0
                if same_endpoint:
                    for key in ('username', 'password'):
                        saved_client[key] = current['downloader'][key]
                job['config']['library'] = current['library']
                # Submitted torrents belong to their original server and paths.
                # Only an untouched queue item can adopt another downloader.
                if job['state'] == 'queued' and not submitted:
                    job['config'] = current
                    remote = job['config']['downloader']['remote_root']
                    job['remote_dir'] = str(PureWindowsPath(remote) / job_id) if PureWindowsPath(remote).drive else str(PurePosixPath(remote) / job_id)
                    job['local_dir'] = str(Path(current['downloader']['local_root']) / job_id)
            elif action in ('pause', 'resume') and job['state'] == 'downloading':
                client(job['config']['downloader']).action(job['torrent_id'], action)
                job['paused'] = action == 'pause'
            else:
                raise ValueError('Deze actie is niet beschikbaar voor deze download.')
            self.store.save_job(job)
            return public_job(job)
