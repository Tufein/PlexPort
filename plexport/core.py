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

from .integrations import client, http_url, plex_scan, same_download_dir
from .duplicates import title_conflicts
from .selection import describe_files, episode_info, identities, metadata_token, selected_complete, validate_selection
from .storage import import_capability
from .sources import SOURCE_PRESETS

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
            if source_type not in ('torznab', 'watchsomuch', *SOURCE_PRESETS):
                raise ValueError('Onbekend brontype.')
            url = (SOURCE_PRESETS[source_type]['url'] if source_type in SOURCE_PRESETS else
                   'https://watchsomuch.to' if source_type == 'watchsomuch' else http_url(str(source.get('url', ''))))
            sources.append({'id': sid, 'name': name, 'type': source_type, 'url': url,
                            'api_key': '' if source_type in SOURCE_PRESETS else str(source.get('api_key', old.get(sid, {}).get('api_key', '')))})
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


def same_downloader(saved, current):
    return (saved['type'] == current['type']
            and saved['url'].rstrip('/') == current['url'].rstrip('/'))


def current_downloader(saved, current):
    """Keep the task's server and paths; refresh credentials for that server only."""
    config = copy.deepcopy(saved)
    if same_downloader(saved, current):
        for key in ('username', 'password'):
            config[key] = current[key]
    return config


def task_paths(downloader, job_id):
    remote = downloader['remote_root']
    remote_path = PureWindowsPath(remote) if PureWindowsPath(remote).drive else PurePosixPath(remote)
    return {'local_dir': str(Path(downloader['local_root']) / job_id),
            'remote_dir': str(remote_path / job_id)}


class APIConflict(ValueError):
    def __init__(self, message, code, **details):
        super().__init__(message)
        self.code, self.details = code, details


def title_candidate(data):
    kind = data.get('kind', 'movie')
    if kind not in ('movie', 'tv'):
        raise ValueError('Kies film of serie.')
    title = clean_name(data.get('title', ''))
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
    return {'title': title, 'year': year, 'kind': kind,
            'season': optional_number('season'), 'episode': optional_number('episode')}


def new_job(config, data):
    if not config['downloader'].get('url'):
        raise ValueError('Vul eerst het adres van je qBittorrent of Transmission in bij Instellingen.')
    candidate = title_candidate(data)
    kind = candidate['kind']
    expected_bytes = download_size(data.get('expected_bytes', 0))
    selection = data.get('selection_requested', False)
    if type(selection) is not bool or (selection and kind != 'tv'):
        raise ValueError('Afleveringen kiezen is alleen beschikbaar voor series.')
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
    sid = uuid.uuid4().hex
    c = {k: copy.deepcopy(config[k]) for k in ('downloader', 'library', 'plex')}
    job = {'id': sid, **candidate, 'link': link, 'metainfo': metainfo,
            'torrent_fingerprint': hashlib.sha256(binary).hexdigest() if metainfo else link,
            'source': str(data.get('source', 'Handmatig'))[:120], 'config': c, **task_paths(c['downloader'], sid),
            'state': 'queued', 'torrent_id': '', 'created': time.time(),
            'progress': 0, 'speed': 0, 'eta': -1, 'error': '', 'files_imported': [], 'paused': False,
            'expected_bytes': expected_bytes, 'activity': 'queued'}
    if selection:
        job.update(selection_requested=True, selection_state='waiting_metadata', selection_files=[],
                   selection_metadata=[], selection_metadata_token='', selection_error='',
                   torrent_expected_bytes=expected_bytes, expected_bytes=0)
    return job


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
            if e.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.ENOTSUP, errno.ENOSYS):
                raise
            if shutil.disk_usage(destination.parent).free < source.stat().st_size:
                raise ValueError('Te weinig vrije ruimte om deze video naar de mediamap te kopiëren. Maak ruimte vrij en kies Opnieuw proberen.')
            shutil.copy2(source, temp)
        # Reserve the final name without replacing an existing library file.
        # Use exclusive creation for shares where hardlinks are unsupported.
        try:
            os.link(temp, destination)
        except OSError as e:
            if e.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.ENOTSUP, errno.ENOSYS):
                raise
            # rename is atomic on the same share; protect with the single import worker.
            if destination.exists():
                raise ValueError('Bestand bestaat al: ' + destination.name)
            os.rename(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def import_media(job, files):
    if job.get('selection_requested'):
        if job.get('selection_state') != 'committed':
            raise ValueError('Kies en bevestig eerst de afleveringen. Er is nog niets geïmporteerd.')
        # The importer is independently guarded, even when called outside the worker.
        if metadata_token(job['torrent_id'], job['selection_metadata']) != job['selection_metadata_token']:
            raise ValueError('De opgeslagen bestandskeuze is ongeldig. Vernieuw de bestandslijst.')
        chosen = {item['index']: item for item in job['selection_metadata'] if item['index'] in job['selection_files']}
        for item in files:
            if item.get('index') not in chosen or any(item.get(key) != chosen[item['index']][key] for key in ('name', 'size')):
                raise ValueError('Bestand hoort niet bij de bevestigde keuze.')
        if not selected_complete(files, job['selection_files']):
            raise ValueError('De gekozen bestanden zijn nog niet volledig gedownload.')
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
            season, episodes = episode_info(path.name)
            if episodes:
                episode = episodes[0]
                extra = ''.join(f'E{value:02d}' for value in episodes[1:])
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

    def enqueue(self, data):
        with self.lock:
            job = new_job(self.store.settings(), data)
            existing_jobs = self.store.jobs()
            for existing in existing_jobs:
                if job['torrent_fingerprint'] == existing.get('torrent_fingerprint', existing['link']):
                    raise ValueError('Deze download staat al in PlexPort.')
            matches = title_conflicts(existing_jobs, job)
            confirmed = data.get('confirmed_conflicts', [])
            if not isinstance(confirmed, list) or any(not isinstance(value, str) for value in confirmed):
                raise ValueError('Bevestig de gevonden taken met hun taak-ID; een algemene overschrijving is niet toegestaan.')
            if any(match['id'] not in confirmed for match in matches):
                raise APIConflict('Deze titel staat al in je PlexPort-geschiedenis. Bevestig de andere versie om verder te gaan.',
                                  'title_conflict', matches=matches)
            require_storage(job['config'], job['kind'], job['expected_bytes'])
            self.store.save_job(job)
            return public_job(job)

    def preflight(self, data):
        kind = data.get('kind', 'movie')
        if kind not in ('movie', 'tv'):
            raise ValueError('Kies film of serie.')
        config = self.store.settings()
        selection = data.get('selection_requested', False)
        if type(selection) is not bool or (selection and kind != 'tv'):
            raise ValueError('Afleveringen kiezen is alleen beschikbaar voor series.')
        expected = download_size(data.get('expected_bytes', 0))
        report = storage_report(config, kind, 0 if selection else expected)
        report['import_capability'] = import_capability(config, kind, 0 if selection else expected)
        if selection:
            report['torrent_expected_bytes'] = expected
            report['warnings'].append('De grootte van je gekozen afleveringen wordt gecontroleerd zodra je de bestandskeuze bevestigt.')
        with self.lock:
            report['title_conflicts'] = title_conflicts(self.store.jobs(), title_candidate(data)) if data.get('title') else []
        return report

    def downloader(self, job):
        config = current_downloader(job['config']['downloader'], self.store.settings()['downloader'])
        return client(config)

    def _selection_status(self, job, status, downloader):
        """Persist metadata once ready, and stop downloading until an explicit choice."""
        if not status.get('metadata_ready'):
            if job.get('selection_state') == 'committed':
                job['selection_restore_committed'] = True
            job['selection_state'] = 'waiting_metadata'
            return False
        same_download_dir(status.get('save_dir', ''), job['remote_dir'])
        current = identities(status.get('all_files'))
        token = metadata_token(job['torrent_id'], current)
        previous = job.get('selection_metadata_token')
        if job.get('selection_state') == 'committed' or job.pop('selection_restore_committed', False):
            if token != previous:
                if job.get('import_started'):
                    raise ValueError('Bestandsmetadata is veranderd nadat de import begon. Herstel de oorspronkelijke bestandsnamen in de downloader en probeer opnieuw; de bevestigde keuze en gepubliceerde media zijn behouden.')
                job.update(selection_state='awaiting_selection', selection_files=[], selection_error='Bestandsmetadata is veranderd. Kies en bevestig de afleveringen opnieuw.')
            else:
                job['selection_state'] = 'committed'
                return True
        if token != previous or job.get('selection_state') in ('waiting_metadata', 'applying'):
            # Persist the import block before a downloader action that can fail.
            job.update(selection_state='awaiting_selection', selection_metadata=current,
                       selection_metadata_token=token, selection_files=[])
            self.store.save_job(job)
            downloader.action(job['torrent_id'], 'pause')
            job.update(paused=True, speed=0, activity='paused', selection_paused=True)
        elif not status.get('paused'):
            downloader.action(job['torrent_id'], 'pause')
            job.update(paused=True, speed=0, activity='paused', selection_paused=True)
        return False

    def files(self, job_id):
        with self.lock:
            job = self.store.job(job_id)
            if not job.get('selection_requested'):
                raise ValueError('Voor deze taak is afleveringen kiezen niet ingeschakeld.')
            files = []
            if job.get('torrent_id'):
                c = self.downloader(job)
                status = c.status(job['torrent_id'])
                self._selection_status(job, status, c)
                if status.get('metadata_ready'):
                    files = describe_files(status['all_files'], job.get('selection_files', []))
                self.store.save_job(job)
            return {'ok': True, 'id': job_id, 'state': job['selection_state'],
                    'metadata_token': job.get('selection_metadata_token', ''), 'files': files,
                    'error': job.get('selection_error', ''),
                    'warning': 'Magnetmetadata ophalen kan peers contacteren en kort gegevens overdragen. PlexPort pauzeert zodra de bestandslijst beschikbaar is.'}

    def select(self, job_id, indices, token):
        with self.lock:
            job = self.store.job(job_id)
            if not job.get('selection_requested') or not job.get('torrent_id'):
                raise ValueError('Wacht tot deze taak bestandsmetadata heeft.')
            if (job.get('files_imported') or job.get('import_started')
                    or any(job.get(key) in ('importing', 'scan_pending', 'done')
                           for key in ('state', 'retry_state', 'resume_state'))):
                raise ValueError('De import is al gestart. De bestandskeuze kan niet meer worden gewijzigd.')
            c = self.downloader(job)
            status = c.status(job['torrent_id'])
            self._selection_status(job, status, c)
            self.store.save_job(job)
            if not status.get('metadata_ready'):
                raise APIConflict('De downloader wacht nog op bestandsmetadata. Probeer straks opnieuw.', 'metadata_waiting')
            if not isinstance(token, str) or token != job.get('selection_metadata_token'):
                raise APIConflict('De bestandslijst is veranderd. Vernieuw de lijst en kies opnieuw.', 'metadata_changed')
            chosen = validate_selection(status['all_files'], indices, job)
            selected_bytes = sum(item['size'] for item in chosen)
            remaining_bytes = sum(item['size'] - int(item['size'] * item['progress']) for item in chosen)
            require_storage(job['config'], job['kind'], remaining_bytes)
            job.update(selection_state='applying', selection_error='')
            self.store.save_job(job)
            try:
                c.action(job['torrent_id'], 'pause')
                c.select_files(job['torrent_id'], [item['index'] for item in chosen], job['remote_dir'], token)
            except Exception as error:
                job.update(selection_state='awaiting_selection', selection_error=friendly_error(error))
                self.store.save_job(job)
                raise
            job.update(selection_state='committed', selection_files=[item['index'] for item in chosen],
                       selection_metadata=identities(status['all_files']), selection_metadata_token=token,
                       selection_episodes=[{key: item[key] for key in ('index', 'name', 'season', 'episodes')} for item in chosen],
                       selected_bytes=selected_bytes, expected_bytes=selected_bytes, selection_error='')
            # Save the confirmed choice before resuming; a failed resume is recoverable.
            self.store.save_job(job)
            if job['state'] not in ('stopped', 'error') and not job.get('selection_user_paused'):
                try:
                    c.action(job['torrent_id'], 'resume')
                    job.update(paused=False, selection_paused=False, activity='unknown')
                except Exception as error:
                    job.update(state='stopped', resume_state='downloading', paused=True, speed=0, activity='paused',
                               selection_error='Bestandskeuze bewaard. Hervat de taak om door te gaan: ' + friendly_error(error))
                self.store.save_job(job)
            return {**public_job(job), 'ok': True, 'metadata_token': token, 'state': 'committed', 'job_state': job['state']}

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
            c = self.downloader(job)
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
            c = self.downloader(job)
            status = c.status(job['torrent_id'])
            job.update({k: status[k] for k in ('progress', 'speed', 'eta', 'paused')})
            job['activity'] = status.get('activity', 'paused' if status['paused'] else 'downloading')
            if job.get('selection_requested'):
                committed = self._selection_status(job, status, c)
                if committed:
                    chosen = [item for item in status['all_files'] if item['index'] in job['selection_files']]
                    total = sum(item['size'] for item in chosen)
                    job['progress'] = sum(item['size'] * item['progress'] for item in chosen) / total if total else 0
                    # Overall torrent progress includes unwanted files and cannot prove this.
                    if (selected_complete(status['all_files'], job['selection_files'])
                            and job['activity'] not in ('checking', 'moving', 'metadata', 'allocating')):
                        job.update(files=chosen, state='importing', speed=0)
            elif status['complete']:
                job['files'] = status['files']
                job['state'] = 'importing'
                job['speed'] = 0
            self.store.save_job(job)
        elif state == 'importing':
            if job.get('selection_requested'):
                c = self.downloader(job)
                status = c.status(job['torrent_id'])
                if not self._selection_status(job, status, c):
                    job['state'] = 'downloading'
                    self.store.save_job(job)
                    return
                if (not selected_complete(status['all_files'], job['selection_files'])
                        or status.get('activity') in ('checking', 'moving', 'metadata', 'allocating')):
                    job['state'] = 'downloading'
                    self.store.save_job(job)
                    return
                job['files'] = [item for item in status['all_files'] if item['index'] in job['selection_files']]
            job['import_started'] = True
            self.store.save_job(job)
            job['import_capability'] = import_capability(job['config'], job['kind'], job.get('selected_bytes', job.get('expected_bytes', 0)))
            # The capability is advisory. Per-file copy checks below account for already
            # published files on retries, while preserving existing library content.
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
                    c = self.downloader(job)
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
                resume_blocked = (action == 'resume' and job.get('selection_requested')
                                  and job.get('selection_state') in ('awaiting_selection', 'applying'))
                if c and not resume_blocked:
                    c.action(job['torrent_id'], 'pause' if action == 'stop' else 'resume')
                if action == 'stop':
                    if job['state'] != 'stopped':
                        job['resume_state'] = job['state']
                    job.update(state='stopped', paused=True, speed=0, eta=-1, activity='paused')
                else:
                    restored = job.pop('resume_state', 'downloading' if job.get('torrent_id') else 'queued')
                    if restored == 'queued' and job.get('torrent_id'):
                        restored = 'downloading'
                    job.update(state=restored, paused=resume_blocked, activity='paused' if resume_blocked else 'queued' if restored == 'queued' else 'unknown')
                    if job.get('selection_requested') and not resume_blocked:
                        job['selection_error'] = ''
            elif action == 'retry':
                if job['state'] != 'error':
                    raise ValueError('Deze download heeft geen fout om opnieuw te proberen.')
                retry_state = job.get('retry_state', 'downloading' if job['torrent_id'] else 'queued')
                current = self.store.settings()
                saved_client = job['config']['downloader']
                same_endpoint = same_downloader(saved_client, current['downloader'])
                submitted = bool(job['torrent_id'] or job.get('add_started') or job.get('add_attempts', 0))
                if retry_state == 'queued' and submitted and not same_endpoint:
                    raise ValueError('Deze download wacht nog op antwoord van de oorspronkelijke downloader. '
                                     'Controleer of de torrent daar bestaat voordat je hem naar een andere downloader verplaatst.')
                job['state'] = job.pop('retry_state', retry_state)
                job['error'] = ''
                job['add_attempts'] = 0
                job['config']['downloader'] = current_downloader(saved_client, current['downloader'])
                job['config']['library'] = current['library']
                # Submitted torrents belong to their original server and paths.
                # Only an untouched queue item can adopt another downloader.
                if job['state'] == 'queued' and not submitted:
                    job['config'] = current
                    job.update(task_paths(current['downloader'], job_id))
            elif action in ('pause', 'resume') and job['state'] == 'downloading':
                blocked = (action == 'resume' and job.get('selection_requested')
                           and job.get('selection_state') in ('awaiting_selection', 'applying'))
                if not blocked:
                    self.downloader(job).action(job['torrent_id'], action)
                job['paused'] = action == 'pause' or blocked
                if job.get('selection_requested'):
                    job['selection_user_paused'] = action == 'pause'
            else:
                raise ValueError('Deze actie is niet beschikbaar voor deze download.')
            self.store.save_job(job)
            return public_job(job)
