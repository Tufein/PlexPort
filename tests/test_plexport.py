import base64
import copy
from concurrent.futures import ThreadPoolExecutor
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
import urllib.error
import urllib.parse
import urllib.request

from plexport import __version__
from plexport.core import Store, Worker, defaults, import_media, merge_settings, new_job, public_job, public_settings, publish_file, safe_file, storage_report
from plexport.integrations import QBittorrent, Transmission, plex_sections, search_source
from plexport.server import create_server

MAGNET = 'magnet:?xt=urn:btih:' + 'a' * 40


class Stub:
    """Local contract server: no public tracker or user service is contacted."""
    def __init__(self):
        self.calls = []
        self.path = ''
        self.tag = ''
        self.complete = False
        self.reject_scan = False
        self.major = 5
        self.modern_qbit = False
        self.reject_login = False
        self.reject_add = False
        self.pending_add = False
        self.empty_login = False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, value, code=200, headers=None):
                body = json.dumps(value).encode() if isinstance(value, (dict, list)) else value.encode()
                self.send_response(code)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                outer.calls.append(('GET', self.path, dict(self.headers)))
                if outer.modern_qbit and self.path.startswith('/api/v2/') and 'QBT_SID_8080=test' not in self.headers.get('Cookie', ''):
                    self.reply('Forbidden', 403)
                    return
                if self.path.startswith('/api/v2/app/version'):
                    self.reply(f'v{outer.major}.0.0')
                elif self.path.startswith('/api/v2/torrents/info'):
                    self.reply([{'hash': 'a' * 40, 'progress': 1 if outer.complete else .4, 'dlspeed': 400,
                                 'eta': 20, 'state': 'stalledUP' if outer.complete else 'downloading',
                                 'save_path': outer.path, 'size': 5, 'amount_left': 0 if outer.complete else 3}] if outer.tag else [])
                elif self.path.startswith('/api/v2/torrents/files'):
                    self.reply([{'name': 'movie.mkv', 'size': 5, 'progress': 1 if outer.complete else .4, 'priority': 1}])
                elif self.path == '/library/sections':
                    self.reply('<MediaContainer><Directory key="1" title="Films" type="movie"/><Directory key="2" title="Series" type="show"/></MediaContainer>')
                elif self.path.endswith('/refresh'):
                    self.reply('', 503 if outer.reject_scan else 200)
                elif self.path.startswith('/torznab'):
                    self.reply('<rss xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel><item><title>Test &amp; Film</title><enclosure url="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" length="5"/><torznab:attr name="seeders" value="42"/></item></channel></rss>')
                else:
                    self.reply('', 404)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                outer.calls.append(('POST', self.path, body))
                if self.path == '/transmission/rpc':
                    if self.headers.get('X-Transmission-Session-Id') != 'session-test':
                        self.reply('', 409, {'X-Transmission-Session-Id': 'session-test'})
                        return
                    req = json.loads(body)
                    method, args = req['method'], req['arguments']
                    result = {}
                    if method == 'session-get':
                        result = {'version': '4.0.6'}
                    elif method == 'torrent-add':
                        outer.path = args['download-dir']
                        result = {'torrent-added': {'hashString': 'a' * 40}}
                    elif method == 'torrent-get':
                        if 'ids' not in args:
                            result = {'torrents': [{'hashString': 'a' * 40, 'downloadDir': outer.path}] if outer.path else []}
                        else:
                            result = {'torrents': [{'hashString': 'a' * 40, 'percentDone': 1 if outer.complete else .4,
                                                   'downloadDir': outer.path,
                                                   'rateDownload': 400, 'eta': 20, 'status': 6 if outer.complete else 4,
                                                   'error': 0, 'errorString': '', 'metadataPercentComplete': 1, 'sizeWhenDone': 5,
                                                   'files': [{'name': 'movie.mkv', 'length': 5, 'bytesCompleted': 5 if outer.complete else 2}],
                                                   'fileStats': [{'wanted': True}]}]}
                    self.reply({'result': 'success', 'arguments': result})
                elif self.path == '/api/v2/auth/login':
                    if outer.reject_login:
                        self.reply('Unauthorized' if outer.modern_qbit else 'Fails.', 401 if outer.modern_qbit else 200)
                    elif outer.empty_login:
                        self.reply('')
                    elif outer.modern_qbit:
                        self.reply('', 204, {'Set-Cookie': 'QBT_SID_8080=test; Path=/; HttpOnly; SameSite=Strict'})
                    else:
                        self.reply('Ok.', headers={'Set-Cookie': 'SID=test; Path=/'})
                elif self.path == '/api/v2/torrents/add':
                    if outer.reject_add:
                        self.reply({'success_count': 0, 'failure_count': 1, 'pending_count': 0, 'added_torrent_ids': []})
                        return
                    if self.headers.get('Content-Type', '').startswith('multipart/form-data'):
                        import re
                        outer.tag = re.search(rb'name="tags"\r\n\r\n([^\r]+)', body)[1].decode()
                        outer.path = re.search(rb'name="savepath"\r\n\r\n([^\r]+)', body)[1].decode()
                    else:
                        params = urllib.parse.parse_qs(body.decode())
                        outer.tag = params.get('tags', [''])[0]
                        outer.path = params.get('savepath', [''])[0]
                    if outer.modern_qbit:
                        self.reply({'success_count': 0 if outer.pending_add else 1, 'failure_count': 0,
                                    'pending_count': 1 if outer.pending_add else 0,
                                    'added_torrent_ids': [] if outer.pending_add else ['a' * 40]},
                                   202 if outer.pending_add else 200)
                    else:
                        self.reply('Ok.')
                elif self.path.startswith('/api/v2/torrents/'):
                    self.reply('')
                else:
                    self.reply('', 404)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class TempFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = defaults()
        self.config['downloader'].update(type='transmission', url='http://127.0.0.1:9091/transmission/rpc', local_root=str(self.root/'downloads'), remote_root='/downloads')
        self.config['library'] = {'movies': str(self.root/'movies'), 'tv': str(self.root/'tv')}
        for path in [self.config['downloader']['local_root'], *self.config['library'].values()]:
            Path(path).mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def job(self, **kwargs):
        return new_job(self.config, {'title': 'Test Film', 'kind': 'movie', 'year': '2026', 'link': MAGNET, **kwargs})

    def media(self, job, name='movie.mkv', content=b'video'):
        path = Path(job['local_dir'])/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {'name': name, 'size': len(content)}, path


class CoreTests(TempFixture):
    def test_concurrent_enqueue_rejects_duplicates_and_returns_no_private_task_data(self):
        store = Store(self.root/'state')
        store.save_settings(self.config)
        worker = Worker(store)
        start = threading.Barrier(2)

        def enqueue():
            start.wait(timeout=3)
            try:
                return worker.enqueue({'title': 'Concurrent', 'link': MAGNET})
            except ValueError as error:
                return str(error)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: enqueue(), range(2)))
        queued = [result for result in results if isinstance(result, dict)]
        rejected = [result for result in results if isinstance(result, str)]
        self.assertEqual(len(queued), 1)
        self.assertEqual(rejected, ['Deze download staat al in PlexPort.'])
        self.assertEqual(len(store.jobs()), 1)
        self.assertEqual(queued[0]['state'], 'queued')
        for private in ('config', 'link', 'metainfo', 'local_dir', 'remote_dir', 'torrent_fingerprint'):
            self.assertNotIn(private, queued[0])

    def test_enqueue_rejects_missing_storage_and_rechecks_before_submission(self):
        store = Store(self.root/'state')
        store.save_settings(self.config)
        worker = Worker(store)
        movies = Path(self.config['library']['movies'])
        movies.rmdir()
        with self.assertRaisesRegex(ValueError, 'Filmmap'):
            worker.enqueue({'title': 'Missing storage', 'link': MAGNET})
        self.assertEqual(store.jobs(), [])
        movies.mkdir()
        # The unrelated TV folder is not required to enqueue a movie.
        Path(self.config['library']['tv']).rmdir()
        queued = worker.enqueue({'title': 'Movie', 'link': MAGNET})
        movies.rmdir()
        with patch('plexport.core.client') as downloader:
            worker.tick()
            downloader.assert_not_called()
        failed = store.job(queued['id'])
        self.assertEqual(failed['state'], 'error')
        self.assertFalse(failed.get('add_started', False))
        self.assertFalse(Path(failed['local_dir']).exists())

    def test_enqueue_rejects_legacy_tasks_without_fingerprint(self):
        store = Store(self.root/'state')
        store.save_settings(self.config)
        legacy = self.job()
        legacy.pop('torrent_fingerprint')
        store.save_job(legacy)
        with self.assertRaisesRegex(ValueError, 'staat al'):
            Worker(store).enqueue({'title': 'Duplicate', 'link': MAGNET})
        self.assertEqual(store.jobs(), [legacy])

    def test_retry_of_untouched_task_uses_windows_and_unc_download_paths(self):
        self.config['downloader']['remote_root'] = 'Z:\\Downloads'
        store = Store(self.root/'state')
        store.save_settings(self.config)
        worker = Worker(store)
        queued = worker.enqueue({'title': 'Windows paths', 'link': MAGNET})
        job = store.job(queued['id'])
        self.assertEqual(job['remote_dir'], 'Z:\\Downloads\\' + job['id'])
        job.update(state='error', retry_state='queued')
        store.save_job(job)
        new_root = self.root/'new-downloads'
        new_root.mkdir()
        store.save_settings({'downloader': {'remote_root': '\\\\nas\\downloads', 'local_root': str(new_root)}})
        worker.action(job['id'], 'retry')
        retried = store.job(job['id'])
        self.assertEqual(retried['remote_dir'], '\\\\nas\\downloads\\' + job['id'])
        self.assertEqual(retried['local_dir'], str(new_root/job['id']))

    def test_storage_reports_each_folder_without_creating_missing_mounts(self):
        Path(self.config['library']['tv']).rmdir()
        report = storage_report(self.config)
        self.assertFalse(report['ok'])
        self.assertEqual([f['ok'] for f in report['folders']], [True, True, False])
        self.assertFalse(Path(self.config['library']['tv']).exists())
        self.assertTrue(storage_report(self.config, 'movie')['ok'])
        for path in [self.config['downloader']['local_root'], self.config['library']['movies']]:
            self.assertEqual(list(Path(path).iterdir()), [])

    def test_storage_rejects_known_size_but_explains_unknown_size(self):
        usage = Mock(free=100)
        with patch('plexport.core.shutil.disk_usage', return_value=usage):
            report = storage_report(self.config, 'movie', 101)
            self.assertFalse(report['ok'])
            self.assertIn('te weinig', report['folders'][0]['message'])
            unknown = storage_report(self.config, 'movie')
            self.assertTrue(unknown['ok'])
            self.assertIn('onbekend', unknown['warnings'][0])
        for size in (-1, True, '100', 1024 ** 5 + 1):
            with self.subTest(size=size), self.assertRaises(ValueError):
                self.job(expected_bytes=size)

    def test_storage_probes_actual_write_permission(self):
        with patch('plexport.core.tempfile.TemporaryFile', side_effect=PermissionError()):
            report = storage_report(self.config, 'movie', 1)
        self.assertFalse(report['ok'])
        self.assertIn('Geen toegang', report['folders'][0]['message'])

    def test_worker_catches_missing_destination_before_submitting(self):
        Path(self.config['library']['movies']).rmdir()
        store = Store(self.root/'state')
        job = self.job()
        store.save_job(job)
        with patch('plexport.core.client') as downloader:
            Worker(store).tick()
            downloader.assert_not_called()
        failed = store.job(job['id'])
        self.assertEqual(failed['state'], 'error')
        self.assertFalse(failed.get('add_started', False))
        self.assertFalse(Path(job['local_dir']).exists())

    def test_copy_rejects_insufficient_space_and_preserves_source(self):
        source = self.root/'source'
        source.write_bytes(b'hello')
        dest = self.root/'library'/'dest.mkv'
        with patch('plexport.core.os.link', side_effect=OSError(errno.EXDEV, 'different volume')), patch('plexport.core.shutil.disk_usage', return_value=Mock(free=4)), patch('plexport.core.shutil.copy2') as copier:
            with self.assertRaisesRegex(ValueError, 'Te weinig'):
                publish_file(source, dest)
            copier.assert_not_called()
        self.assertEqual(source.read_bytes(), b'hello')
        self.assertFalse(dest.exists())
        self.assertEqual(list(dest.parent.iterdir()), [])

    def test_movie_import_preserves_source_and_is_idempotent(self):
        job = self.job()
        item, source = self.media(job)
        sub, _ = self.media(job, 'movie.nl.srt', b'subtitles')
        files = import_media(job, [item, sub])
        self.assertEqual(Path(files[0]).name, 'Test Film (2026).mkv')
        self.assertEqual(Path(files[1]).name, 'Test Film (2026).nl.srt')
        self.assertTrue(source.exists())
        self.assertTrue(os.path.samefile(source, files[0]))
        self.assertEqual(import_media(job, [item, sub]), files)

    def test_network_copy_fallback(self):
        source = self.root/'source'
        source.write_bytes(b'hello')
        dest = self.root/'library'/'dest.mkv'
        with patch('plexport.core.os.link', side_effect=OSError(errno.EXDEV, 'different volume')):
            publish_file(source, dest)
        self.assertEqual(dest.read_bytes(), b'hello')
        self.assertTrue(source.exists())
        self.assertFalse(list(dest.parent.glob('*.part')))

    def test_collision_does_not_overwrite(self):
        job = self.job()
        item, source = self.media(job)
        dest = Path(self.config['library']['movies'])/'Test Film (2026)'/'Test Film (2026).mkv'
        dest.parent.mkdir()
        dest.write_bytes(b'other')
        with self.assertRaisesRegex(ValueError, 'andere inhoud'):
            import_media(job, [item])
        self.assertEqual(dest.read_bytes(), b'other')
        self.assertEqual(source.read_bytes(), b'video')

    def test_episode_pack_and_manual_episode(self):
        job = self.job(kind='tv', title='Test Show', year='')
        first, _ = self.media(job, 'release.S02E03.mkv')
        second, _ = self.media(job, 'release.S02E04E05.mp4')
        imported = import_media(job, [first, second])
        self.assertTrue(imported[0].endswith('Season 02/Test Show - S02E03.mkv'))
        self.assertTrue(imported[1].endswith('Test Show - S02E04E05.mp4'))
        manual = self.job(kind='tv', title='Manual', year='', season=1, episode=8)
        item, _ = self.media(manual)
        self.assertTrue(import_media(manual, [item])[0].endswith('Manual - S01E08.mkv'))

    def test_missing_episode_in_pack_rejects_before_writes(self):
        job = self.job(kind='tv', year='')
        first, _ = self.media(job, 'show.S01E01.mkv')
        second, _ = self.media(job, 'unknown.mkv')
        with self.assertRaisesRegex(ValueError, 'Afleveringsnummer'):
            import_media(job, [first, second])
        self.assertEqual(list(Path(self.config['library']['tv']).iterdir()), [])

    def test_unsafe_paths_and_symlinks(self):
        for name in ('../outside.mkv', '/outside.mkv', r'C:\outside.mkv', r'..\outside.mkv'):
            with self.assertRaises(ValueError):
                safe_file(self.root, name)
        outside = tempfile.TemporaryDirectory()
        try:
            (self.root/'link').symlink_to(outside.name, target_is_directory=True)
            with self.assertRaises(ValueError):
                safe_file(self.root, 'link/movie.mkv')
        finally:
            outside.cleanup()

    def test_incomplete_and_missing_destination(self):
        job = self.job()
        item, _ = self.media(job)
        with self.assertRaisesRegex(ValueError, 'onvolledig'):
            import_media(job, [{**item, 'size': 99}])
        Path(self.config['library']['movies']).rmdir()
        with self.assertRaisesRegex(ValueError, 'niet gemount'):
            import_media(job, [item])

    def test_secret_redaction_and_preservation(self):
        self.config['downloader']['password'] = 'private-password'
        self.config['plex']['token'] = 'private-token'
        self.config['sources'] = [{'id':'x', 'name':'source', 'url':'http://127.0.0.1/api', 'api_key':'private-key'}]
        clean = public_settings(self.config)
        self.assertNotIn('private-', json.dumps(clean))
        merged = merge_settings(self.config, {'downloader': {'username': 'changed'}, 'sources':clean['sources']})
        self.assertEqual(merged['downloader']['password'], 'private-password')
        self.assertEqual(merged['sources'][0]['api_key'], 'private-key')
        self.assertNotIn('config', public_job(self.job()))

    def test_overlap_and_invalid_magnets(self):
        with self.assertRaises(ValueError):
            merge_settings(self.config, {'library': {'movies': self.config['downloader']['local_root']}})
        with self.assertRaises(ValueError):
            self.job(link='magnet:?dn=missinghash')
        with self.assertRaises(ValueError):
            self.job(link='file:///etc/passwd')


class IntegrationTests(TempFixture):
    def setUp(self):
        super().setUp()
        self.stub = Stub()

    def tearDown(self):
        self.stub.close()
        super().tearDown()

    def test_transmission_contract_and_recovery(self):
        self.config['downloader']['url'] = self.stub.url+'/transmission/rpc'
        c = Transmission(self.config['downloader'])
        self.assertIn('4.0.6', c.test())
        job = self.job()
        tid = c.add(job)
        self.assertEqual(c.add(job), tid)
        self.assertEqual(sum(1 for method, path, body in self.stub.calls if method=='POST' and path=='/transmission/rpc' and json.loads(body)['method']=='torrent-add'), 1)
        self.assertFalse(c.status(tid)['complete'])
        self.stub.complete = True
        self.assertTrue(c.status(tid)['complete'])
        c.action(tid, 'pause')
        c.action(tid, 'resume')

    def test_qbittorrent_contract_and_version_actions(self):
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url, username='user', password='pass')
        c = QBittorrent(self.config['downloader'])
        self.assertIn('5.0.0', c.test())
        job = self.job()
        self.assertEqual(c.add(job), '')
        tid = c.add(job)
        self.assertEqual(tid, 'a'*40)
        self.assertEqual(self.stub.path, job['remote_dir'])
        self.assertFalse(c.status(tid)['complete'])
        self.stub.complete = True
        self.assertTrue(c.status(tid)['complete'])
        c.action(tid, 'pause')
        self.stub.major = 4
        c.action(tid, 'resume')
        paths = [path for method, path, *_ in self.stub.calls if method=='POST']
        self.assertIn('/api/v2/torrents/stop', paths)
        self.assertIn('/api/v2/torrents/resume', paths)

    def test_remove_contracts_preserve_files_by_default_and_check_download_path(self):
        for kind in ('qbittorrent', 'transmission'):
            with self.subTest(kind=kind):
                self.config['downloader'].update(type=kind, url=self.stub.url if kind == 'qbittorrent' else self.stub.url+'/transmission/rpc')
                c = QBittorrent(self.config['downloader']) if kind == 'qbittorrent' else Transmission(self.config['downloader'])
                c.test()  # Establish Transmission's session before counting removal requests.
                job = self.job()
                self.stub.path = job['remote_dir']
                self.stub.tag = 'plexport-'+job['id']
                tid = 'a'*40
                c.remove(tid)
                c.remove(tid, True, job['remote_dir'])
                before = len(self.stub.calls)
                with self.assertRaisesRegex(ValueError, 'downloadmap is veranderd'):
                    c.remove(tid, True, '/media/Movies')
                with self.assertRaisesRegex(ValueError, 'één download'):
                    c.remove('all', True, job['remote_dir'])
                with self.assertRaises(ValueError):
                    c.remove(tid+'|'+tid)
                if kind == 'qbittorrent':
                    calls = [urllib.parse.parse_qs(body.decode()) for method,path,body in self.stub.calls if method=='POST' and path=='/api/v2/torrents/delete']
                    self.assertEqual([data['deleteFiles'] for data in calls], [['false'], ['true']])
                    self.assertTrue(all(data['hashes']==[tid] for data in calls))
                else:
                    calls = [json.loads(body)['arguments'] for method,path,body in self.stub.calls if method=='POST' and path=='/transmission/rpc' and json.loads(body)['method']=='torrent-remove']
                    self.assertEqual([data['delete-local-data'] for data in calls], [False, True])
                    self.assertTrue(all(data['ids']==[tid] for data in calls))
                # The rejected cleanup performs a lookup, but never a deletion.
                self.assertNotEqual(len(self.stub.calls), before)

    def test_qbittorrent_reports_waiting_and_never_imports_moving_or_checking(self):
        c = QBittorrent({'url': self.stub.url})
        cases = {'metaDL': 'metadata', 'forcedMetaDL': 'metadata', 'stalledDL': 'waiting',
                 'queuedDL': 'queued', 'stoppedDL': 'paused', 'checkingUP': 'checking',
                 'moving': 'moving', 'allocating': 'allocating', 'downloading': 'downloading', 'stalledUP': 'seeding'}
        for state, activity in cases.items():
            torrent = {'progress': 1, 'amount_left': 0, 'size': 5, 'dlspeed': 0, 'eta': -1, 'state': state}
            files = [{'name': 'movie.mkv', 'size': 5, 'progress': 1, 'priority': 1}]
            with self.subTest(state=state), patch.object(c, 'call', side_effect=[json.dumps([torrent]).encode(), json.dumps(files).encode()]):
                status = c.status('a' * 40)
                self.assertEqual(status['activity'], activity)
                if activity in ('checking', 'moving', 'metadata'):
                    self.assertFalse(status['complete'])

    def test_transmission_explains_metadata_queue_and_waiting(self):
        c = Transmission({'url': self.stub.url})
        torrent = {'percentDone': .4, 'rateDownload': 0, 'eta': -1, 'status': 4,
                   'error': 0, 'errorString': '', 'metadataPercentComplete': 1, 'sizeWhenDone': 5,
                   'files': [{'name': 'movie.mkv', 'length': 5, 'bytesCompleted': 2}], 'fileStats': [{'wanted': True}], 'peersConnected': 0}
        for changes, activity in [({}, 'waiting'), ({'metadataPercentComplete': .2}, 'metadata'), ({'status': 3}, 'queued'), ({'status': 2}, 'checking')]:
            with self.subTest(activity=activity), patch.object(c, 'rpc', return_value={'torrents': [{**torrent, **changes}]}):
                status = c.status('a' * 40)
                self.assertEqual(status['activity'], activity)
                self.assertFalse(status['complete'])

    def test_search_and_plex_sections(self):
        items = search_source({'url':self.stub.url+'/torznab', 'api_key':'key', 'name':'Test source'}, 'Film', 'movie')
        self.assertEqual(items[0]['title'], 'Test & Film')
        self.assertEqual(items[0]['seeders'], 42)
        self.assertEqual(items[0]['size'], 5)
        self.assertIn('cat=2000', self.stub.calls[-1][1])
        sections = plex_sections({'url':self.stub.url, 'token':'token'})
        self.assertEqual([s['id'] for s in sections], ['1', '2'])

    def test_qbittorrent_52_login_cookie_and_add_responses(self):
        self.stub.modern_qbit = True
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url, username='user', password='pass')
        c = QBittorrent(self.config['downloader'])
        self.assertIn('5.0.0', c.test())
        for pending in (False, True):
            for upload in (False, True):
                with self.subTest(pending=pending, upload=upload):
                    self.stub.pending_add = pending
                    self.stub.tag = ''
                    job = self.job()
                    if upload:
                        job['metainfo'] = base64.b64encode(b'd4:infod4:name4:testee').decode()
                        job['link'] = ''
                    self.assertEqual(c.add(job), '')
                    self.assertEqual(c.add(job), 'a' * 40)
                    self.assertEqual(self.stub.path, job['remote_dir'])

    def test_qbittorrent_rejects_failed_login_and_empty_legacy_reply(self):
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url, username='user', password='wrong')
        self.stub.reject_login = True
        for modern in (False, True):
            self.stub.modern_qbit = modern
            with self.subTest(modern=modern), self.assertRaisesRegex(ValueError, 'aanmelden mislukt'):
                QBittorrent(self.config['downloader'])
        self.stub.reject_login = False
        self.stub.modern_qbit = False
        self.stub.empty_login = True
        with self.assertRaisesRegex(ValueError, 'aanmelden mislukt'):
            QBittorrent(self.config['downloader'])

    def test_qbittorrent_rejects_failed_json_addition(self):
        self.stub.modern_qbit = True
        self.stub.reject_add = True
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url, username='user', password='pass')
        c = QBittorrent(self.config['downloader'])
        with self.assertRaisesRegex(ValueError, 'niet geaccepteerd'):
            c.add(self.job())

    def test_torrent_upload_multipart(self):
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url)
        metainfo = base64.b64encode(b'd4:infod4:name4:testee').decode()
        job = self.job(link='', metainfo=metainfo)
        c = QBittorrent(self.config['downloader'])
        c.add(job)
        body = [body for method, path, body in self.stub.calls if method=='POST' and path=='/api/v2/torrents/add'][0]
        self.assertIn(b'filename="download.torrent"', body)
        self.assertIn(base64.b64decode(metainfo), body)
        self.assertEqual(c.add(job), 'a'*40)

    def test_worker_restart_import_and_failed_scan_retry(self):
        self.config['downloader']['url'] = self.stub.url+'/transmission/rpc'
        self.config['plex'] = {'url':self.stub.url, 'token':'token', 'movie_section':'1', 'tv_section':'2'}
        store = Store(self.root/'state')
        store.save_settings(self.config)
        job = self.job()
        store.save_job(job)
        worker = Worker(store)
        worker.tick()
        self.assertEqual(store.job(job['id'])['state'], 'downloading')
        self.media(job)
        self.stub.complete = True
        # Recreate both storage and worker to simulate a process restart.
        worker = Worker(Store(self.root/'state'))
        worker.tick()
        self.assertEqual(store.job(job['id'])['state'], 'importing')
        worker.tick()
        self.assertEqual(store.job(job['id'])['state'], 'scan_pending')
        self.stub.reject_scan = True
        worker.tick()
        failed = store.job(job['id'])
        self.assertEqual(failed['state'], 'error')
        self.assertTrue(Path(failed['files_imported'][0]).exists())
        self.stub.reject_scan = False
        worker.action(job['id'], 'retry')
        worker.tick()
        self.assertEqual(store.job(job['id'])['state'], 'done')
        self.assertTrue(store.job(job['id'])['scan_requested'])

    def test_retry_keeps_submitted_torrent_on_original_downloader(self):
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url, username='old-user', password='old-password')
        store = Store(self.root/'state')
        store.save_settings(self.config)
        job = self.job()
        store.save_job(job)
        worker = Worker(store)
        worker.tick()
        worker.tick()
        failed = store.job(job['id'])
        self.assertEqual(failed['state'], 'downloading')
        failed.update(state='error', retry_state='downloading', error='Verbinding verbroken')
        store.save_job(failed)
        new_root = self.root/'new-downloads'
        new_root.mkdir()
        store.save_settings({'downloader': {'url': 'http://127.0.0.1:9', 'username': 'new-user',
                                           'password': 'new-password', 'remote_root': '/new-downloads',
                                           'local_root': str(new_root)}})

        worker.action(job['id'], 'retry')
        worker.tick()
        resumed = store.job(job['id'])
        self.assertEqual(resumed['state'], 'downloading')
        self.assertEqual(resumed['config']['downloader'], self.config['downloader'])
        self.assertEqual(resumed['remote_dir'], job['remote_dir'])
        self.assertEqual(resumed['local_dir'], job['local_dir'])
        self.assertEqual(resumed['progress'], .4)

    def test_retry_repairs_credentials_on_same_downloader(self):
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url+'/', username='old-user', password='old-password')
        store = Store(self.root/'state')
        store.save_settings(self.config)
        job = self.job()
        job.update(state='error', retry_state='downloading', torrent_id='a'*40, error='Aanmelden mislukt')
        store.save_job(job)
        self.stub.tag = 'plexport-'+job['id']
        store.save_settings({'downloader': {'url': self.stub.url, 'username': 'new-user', 'password': 'new-password'}})
        worker = Worker(store)

        worker.action(job['id'], 'retry')
        worker.tick()
        self.assertEqual(store.job(job['id'])['state'], 'downloading')
        login_body = [body for method, path, body in self.stub.calls if method == 'POST' and path == '/api/v2/auth/login'][-1]
        self.assertEqual(urllib.parse.parse_qs(login_body.decode()), {'username': ['new-user'], 'password': ['new-password']})
        self.assertEqual(store.job(job['id'])['config']['downloader']['url'], self.config['downloader']['url'])

    def test_retry_can_switch_downloader_for_untouched_queue_item(self):
        self.config['downloader'].update(type='qbittorrent', url='http://127.0.0.1:9', remote_root='/old-downloads')
        store = Store(self.root/'state')
        store.save_settings(self.config)
        job = self.job()
        job.update(state='error', retry_state='queued', error='Downloadmap ontbrak')
        store.save_job(job)
        new_root = self.root/'new-downloads'
        new_root.mkdir()
        store.save_settings({'downloader': {'url': self.stub.url, 'remote_root': '/new-downloads', 'local_root': str(new_root)}})
        worker = Worker(store)

        worker.action(job['id'], 'retry')
        worker.tick()
        worker.tick()
        resumed = store.job(job['id'])
        self.assertEqual(resumed['state'], 'downloading')
        self.assertEqual(resumed['config']['downloader']['url'], self.stub.url)
        self.assertEqual(self.stub.path, '/new-downloads/'+job['id'])
        self.assertEqual(resumed['local_dir'], str(new_root/job['id']))

    def test_retry_does_not_duplicate_pending_add_on_another_downloader(self):
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url)
        store = Store(self.root/'state')
        store.save_settings(self.config)
        job = self.job()
        store.save_job(job)
        worker = Worker(store)
        worker.tick()
        failed = store.job(job['id'])
        self.assertFalse(failed['torrent_id'])
        self.assertEqual(failed['add_attempts'], 1)
        failed.update(state='error', retry_state='queued', error='Wachten op metadata')
        store.save_job(failed)
        store.save_settings({'downloader': {'url': 'http://127.0.0.1:9'}})

        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                if legacy:
                    failed.pop('add_started')
                    store.save_job(failed)
                with self.assertRaisesRegex(ValueError, 'oorspronkelijke downloader'):
                    worker.action(job['id'], 'retry')
                self.assertEqual(store.job(job['id']), failed)
        self.assertEqual(sum(method == 'POST' and path == '/api/v2/torrents/add'
                             for method, path, _ in self.stub.calls), 1)

    def test_retry_preserves_server_after_uncertain_add_response(self):
        self.config['downloader'].update(type='qbittorrent', url=self.stub.url)
        store = Store(self.root/'state')
        store.save_settings(self.config)
        job = self.job()
        store.save_job(job)
        worker = Worker(store)

        def lost_response(submitted_job):
            # Simulate an accepted request whose response is lost before ID/count storage.
            self.assertTrue(Store(self.root/'state').job(submitted_job['id'])['add_started'])
            raise TimeoutError('Antwoord verloren')

        with patch('plexport.core.client') as get_client:
            get_client.return_value.add.side_effect = lost_response
            worker.tick()
        failed = store.job(job['id'])
        self.assertEqual(failed['state'], 'error')
        self.assertFalse(failed['torrent_id'])
        self.assertEqual(failed.get('add_attempts', 0), 0)
        store.save_settings({'downloader': {'url': 'http://127.0.0.1:9'}})
        worker = Worker(Store(self.root/'state'))

        with self.assertRaisesRegex(ValueError, 'oorspronkelijke downloader'):
            worker.action(job['id'], 'retry')
        self.assertEqual(store.job(job['id']), failed)


class ServerTests(TempFixture):
    def setUp(self):
        super().setUp()
        self.store = Store(self.root/'state')
        self.store.save_settings(self.config)
        self.server, self.worker = create_server('127.0.0.1', 0, self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        super().tearDown()

    def call(self, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url+path, data=data, headers={'X-PlexPort':'1', 'Content-Type':'application/json', **(headers or {})})
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, json.loads(response.read())

    def test_real_app_http_queue_dedup_and_secret_redaction(self):
        code, job = self.call('/api/jobs', {'title':'API Film', 'link':MAGNET})
        self.assertEqual(code, 201)
        self.assertEqual(job['state'], 'queued')
        self.assertNotIn('link', job)
        with self.assertRaises(urllib.error.HTTPError) as duplicate:
            self.call('/api/jobs', {'title':'API Film', 'link':MAGNET})
        self.assertEqual(duplicate.exception.code, 400)
        duplicate.exception.close()
        status = self.call('/api/status')[1]
        self.assertEqual(len(status['jobs']), 1)
        self.assertEqual(status['version'], __version__)
        self.call('/api/settings', {'plex':{'token':'secret'}})
        settings = self.call('/api/settings')[1]
        self.assertTrue(settings['plex']['token_set'])
        self.assertNotIn('secret', json.dumps(settings))

    def test_http_stop_resume_remove_and_strict_cleanup_options(self):
        _, job = self.call('/api/jobs', {'title':'Controls', 'link':MAGNET})
        self.assertEqual(self.call('/api/action', {'id':job['id'], 'action':'stop'})[1]['state'], 'stopped')
        self.assertEqual(self.call('/api/action', {'id':job['id'], 'action':'resume'})[1]['state'], 'queued')
        for bad in ({'delete_files':'false'}, {'forget':'false'}, {'forget':True,'delete_files':True}):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.call('/api/action', {'id':job['id'], 'action':'remove', **bad})
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        result = self.call('/api/action', {'id':job['id'], 'action':'remove'})[1]
        self.assertTrue(result['removed'])
        self.assertFalse(result['files_deleted'])
        self.assertEqual(self.call('/api/status')[1]['jobs'], [])

    def test_preflight_and_submit_do_not_queue_into_missing_destination(self):
        Path(self.config['library']['movies']).rmdir()
        code, report = self.call('/api/preflight', {'kind': 'movie', 'expected_bytes': 100})
        self.assertEqual(code, 200)
        self.assertFalse(report['ok'])
        self.assertEqual(len(report['folders']), 2)
        with self.assertRaises(urllib.error.HTTPError) as refused:
            self.call('/api/jobs', {'title': 'Film', 'link': MAGNET, 'expected_bytes': 100})
        self.assertEqual(refused.exception.code, 400)
        refused.exception.close()
        self.assertEqual(self.store.jobs(), [])

    def test_preflight_validates_size_and_keeps_secrets_private(self):
        self.store.save_settings({'downloader': {'password': 'preflight-secret'}})
        _, report = self.call('/api/preflight', {'kind': 'tv', 'expected_bytes': 100})
        self.assertTrue(report['ok'])
        self.assertNotIn('preflight-secret', json.dumps(report))
        self.assertEqual([f['key'] for f in report['folders']], ['downloads', 'tv'])
        with self.assertRaises(urllib.error.HTTPError) as invalid:
            self.call('/api/preflight', {'kind': 'tv', 'expected_bytes': '100'})
        self.assertEqual(invalid.exception.code, 400)
        invalid.exception.close()

    def test_cross_origin_and_dns_rebinding_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as blocked:
            self.call('/api/jobs', {'title':'Film','link':MAGNET}, {'Origin':'https://example.com'})
        self.assertEqual(blocked.exception.code, 403)
        blocked.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as rebound:
            self.call('/api/status', headers={'Host':'attacker.example'})
        self.assertEqual(rebound.exception.code, 403)
        rebound.exception.close()
        self.assertEqual(self.store.jobs(), [])

    def test_static_assets_and_path_traversal(self):
        with urllib.request.urlopen(self.url+'/') as response:
            self.assertIn(b'<html lang="nl">', response.read())
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        with urllib.request.urlopen(self.url+'/jobs.js') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'PlexPortJobs', response.read())
        with self.assertRaises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(self.url+'/../data/plexport.sqlite')
        self.assertEqual(missing.exception.code, 404)
        missing.exception.close()

    def test_basic_auth_protects_remote_mode(self):
        protected, _ = create_server('127.0.0.1', 0, self.store, password='private')
        thread = threading.Thread(target=protected.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{protected.server_port}/api/status'
        try:
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(url)
            self.assertEqual(denied.exception.code, 401)
            denied.exception.close()
            auth = 'Basic '+base64.b64encode(b'admin:private').decode()
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization':auth,'X-PlexPort':'1'})) as response:
                self.assertEqual(response.status, 200)
        finally:
            protected.shutdown()
            protected.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
