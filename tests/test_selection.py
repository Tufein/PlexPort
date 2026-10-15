import base64
import copy
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.parse
import urllib.request

from plexport.core import APIConflict, Store, Worker, defaults, import_media, new_job
from plexport.integrations import QBittorrent, Transmission
from plexport.selection import describe_files, identities, metadata_token, validate_selection
from plexport.server import create_server

HASH = 'a' * 40
MAGNET = 'magnet:?xt=urn:btih:' + HASH
FILES = [
    {'index': 0, 'name': 'Show/Show.S01E01E02.mkv', 'size': 5, 'progress': 1, 'wanted': True},
    {'index': 1, 'name': 'Show/Show.S01E01E02.nl.forced.srt', 'size': 3, 'progress': 1, 'wanted': True},
    {'index': 2, 'name': 'Show/Show.S01E03.mkv', 'size': 9, 'progress': .1, 'wanted': True},
    {'index': 3, 'name': 'Show/extras/Behind the scenes.mp4', 'size': 4, 'progress': 0, 'wanted': True},
    {'index': 4, 'name': 'Show/sample.mkv', 'size': 1, 'progress': 1, 'wanted': True},
]


class DownloaderFixture:
    """Local downloader model: no tracker, peer, NAS or production credentials."""
    def __init__(self, job):
        self.job = job
        self.contents = copy.deepcopy(FILES)
        self.ready = True
        self.paused = False
        self.path = job['remote_dir']
        self.reject = False
        self.actions = []
        self.selections = []
        self.overall_complete = False
        self.activity = 'downloading'

    def status(self, torrent_id):
        assert torrent_id == HASH
        return {'progress': .25, 'speed': 12, 'eta': 9, 'paused': self.paused,
                'complete': self.overall_complete, 'activity': self.activity,
                'metadata_ready': self.ready, 'save_dir': self.path,
                'all_files': copy.deepcopy(self.contents) if self.ready else [], 'files': []}

    def action(self, torrent_id, action):
        assert torrent_id == HASH
        self.actions.append(action)
        self.paused = action == 'pause'

    def select_files(self, torrent_id, indices, expected_dir, token):
        assert torrent_id == HASH and expected_dir == self.path
        assert metadata_token(torrent_id, self.contents) == token
        self.selections.append(indices)
        if self.reject:
            raise ValueError('Fixture rejected priorities')
        for item in self.contents:
            item['wanted'] = item['index'] in indices


class SelectionMetadataTests(unittest.TestCase):
    def test_descriptions_preserve_original_names_multi_episode_extras_and_ambiguity(self):
        described = describe_files(FILES)
        self.assertEqual(described[0]['episodes'], [1, 2])
        self.assertEqual(described[0]['name'], FILES[0]['name'])
        self.assertEqual(described[0]['reason'], 'multiple_episodes')
        self.assertEqual(described[3]['reason'], 'extra')
        self.assertFalse(described[4]['selectable'])

    def test_identity_token_uses_current_indices_names_sizes_not_progress_or_response_order(self):
        token = metadata_token(HASH, FILES)
        reordered = copy.deepcopy(FILES[::-1])
        reordered[0]['progress'] = 0
        self.assertEqual(token, metadata_token(HASH, reordered))
        for key, value in [('index', 10), ('name', 'renamed.mkv'), ('size', 999)]:
            changed = copy.deepcopy(FILES)
            changed[0][key] = value
            self.assertNotEqual(token, metadata_token(HASH, changed))

    def test_unsafe_paths_and_missing_or_duplicate_indices_are_rejected(self):
        for name in ('../escape.mkv', '/absolute.mkv', 'C:\\escape.mkv', 'a\\..\\escape.mkv', 'nul\x00.mkv'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                identities([{**FILES[0], 'name': name}])
        for index in (None, -1, True, '0'):
            with self.subTest(index=index), self.assertRaises(ValueError):
                identities([{**FILES[0], 'index': index}])
        with self.assertRaises(ValueError):
            identities([FILES[0], FILES[0]])

    def test_invalid_indices_missing_video_and_unrelated_subtitles_reject(self):
        for indices in ([], [True], ['0'], [-1], [999], [0, 0], [1], [4], [3]):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                validate_selection(FILES, indices, {})
        self.assertEqual([item['index'] for item in validate_selection(FILES, [0, 1], {})], [0, 1])
        changed = copy.deepcopy(FILES)
        changed[1]['name'] = 'Elsewhere/Show.S01E01E02.nl.srt'
        with self.assertRaisesRegex(ValueError, 'Ondertitel'):
            validate_selection(changed, [0, 1], {})

    def test_ambiguous_single_episode_requires_explicit_job_identity(self):
        file = [{**FILES[0], 'name': 'episode.mkv'}]
        with self.assertRaises(ValueError):
            validate_selection(file, [0], {})
        self.assertEqual(len(validate_selection(file, [0], {'season': 1, 'episode': 7})), 1)


class SelectionSetup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = defaults()
        self.config['downloader'].update(url='http://fixture.invalid:8080', local_root=str(self.root / 'downloads'), remote_root='/downloads')
        self.config['library'] = {'movies': str(self.root / 'movies'), 'tv': str(self.root / 'tv')}
        for value in [self.config['downloader']['local_root'], *self.config['library'].values()]:
            Path(value).mkdir()
        self.store = Store(self.root / 'state')
        self.store.save_settings(self.config)
        self.worker = Worker(self.store)
        self.job = new_job(self.config, {'kind': 'tv', 'title': 'Show', 'link': MAGNET, 'selection_requested': True})
        self.job.update(state='downloading', torrent_id=HASH, add_started=True)
        self.store.save_job(self.job)
        self.client = DownloaderFixture(self.job)
        self.patcher = patch('plexport.core.client', return_value=self.client)
        self.get_client = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def choose(self, indices=(0, 1)):
        view = self.worker.files(self.job['id'])
        return self.worker.select(self.job['id'], list(indices), view['metadata_token'])

    def write_selected(self):
        for item in FILES[:2]:
            path = Path(self.job['local_dir']) / item['name']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'x' * item['size'])


class SelectionWorkerTests(SelectionSetup):
    def test_opt_in_validation_and_old_tasks_are_unchanged(self):
        legacy = new_job(self.config, {'title': 'Film', 'link': MAGNET})
        self.assertNotIn('selection_state', legacy)
        for data in ({'kind': 'movie', 'selection_requested': True}, {'kind': 'tv', 'selection_requested': 'yes'}):
            with self.assertRaises(ValueError):
                new_job(self.config, {'title': 'Wrong', 'link': MAGNET, **data})

    def test_metadata_delay_waits_without_invented_indices_or_import(self):
        self.client.ready = False
        self.client.overall_complete = True
        self.worker.tick()
        view = self.worker.files(self.job['id'])
        self.assertEqual(view['state'], 'waiting_metadata')
        self.assertEqual(view['files'], [])
        self.assertIn('peers', view['warning'])
        self.assertEqual(self.store.job(self.job['id'])['state'], 'downloading')
        self.assertEqual(list(Path(self.config['library']['tv']).iterdir()), [])

    def test_metadata_pauses_and_requires_commit_even_when_overall_complete(self):
        self.client.overall_complete = True
        self.worker.tick()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['selection_state'], 'awaiting_selection')
        self.assertEqual(job['state'], 'downloading')
        self.assertEqual(self.client.actions, ['pause'])
        self.assertFalse(self.client.selections)
        self.assertTrue(job['paused'])

    def test_commit_filters_download_and_import_and_preserves_multi_episode_and_subtitle(self):
        self.write_selected()
        result = self.choose()
        self.assertEqual(result['selection_files'], [0, 1])
        self.assertEqual(result['selection_episodes'][0]['episodes'], [1, 2])
        self.assertEqual(self.client.selections, [[0, 1]])
        self.assertEqual(self.client.actions[-1], 'resume')
        self.worker.tick()
        self.assertEqual(self.store.job(self.job['id'])['state'], 'importing')
        self.worker.tick()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['state'], 'done')
        self.assertEqual(len(job['files_imported']), 2)
        self.assertTrue(any(path.endswith('Show - S01E01E02.mkv') for path in job['files_imported']))
        self.assertTrue(any(path.endswith('Show - S01E01E02.nl.forced.srt') for path in job['files_imported']))
        self.assertTrue(all(Path(path).is_file() for path in job['files_imported']))
        self.assertFalse((Path(self.job['local_dir']) / FILES[2]['name']).exists())

    def test_overall_progress_does_not_make_incomplete_selected_file_importable(self):
        self.choose()
        self.client.contents[0]['progress'] = .99
        self.client.overall_complete = True
        self.worker.tick()
        self.assertEqual(self.store.job(self.job['id'])['state'], 'downloading')

    def test_checking_selected_complete_files_still_waits(self):
        self.choose()
        self.client.activity = 'checking'
        self.worker.tick()
        self.assertEqual(self.store.job(self.job['id'])['state'], 'downloading')

    def test_changed_indices_or_metadata_require_new_confirmation_before_mutation(self):
        view = self.worker.files(self.job['id'])
        self.client.contents[0]['name'] = 'Show/Show.S01E10.mkv'
        with self.assertRaises(APIConflict) as error:
            self.worker.select(self.job['id'], [0], view['metadata_token'])
        self.assertEqual(error.exception.code, 'metadata_changed')
        self.assertEqual(self.client.selections, [])
        self.assertEqual(self.store.job(self.job['id'])['selection_state'], 'awaiting_selection')

    def test_changed_metadata_after_commit_blocks_import_and_clears_previous_choice(self):
        self.choose()
        self.client.contents[0]['name'] = 'Show/Show.S01E10.mkv'
        self.worker.tick()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['state'], 'downloading')
        self.assertEqual(job['selection_state'], 'awaiting_selection')
        self.assertEqual(job['selection_files'], [])

    def test_client_rejection_keeps_actionable_task_then_retry_can_commit(self):
        self.client.reject = True
        with self.assertRaisesRegex(ValueError, 'Fixture rejected'):
            self.choose()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['state'], 'downloading')
        self.assertEqual(job['selection_state'], 'awaiting_selection')
        self.assertIn('Fixture rejected', job['selection_error'])
        self.worker.tick()
        self.assertEqual(self.store.job(self.job['id'])['state'], 'downloading')
        self.client.reject = False
        self.choose()
        self.assertEqual(self.store.job(self.job['id'])['selection_state'], 'committed')

    def test_restart_during_selection_and_stop_resume_preserve_original_paths_and_choice(self):
        self.worker.files(self.job['id'])
        self.worker = Worker(Store(self.root / 'state'))
        self.worker.action(self.job['id'], 'stop')
        self.choose()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['state'], 'stopped')
        self.assertTrue(self.client.paused)
        self.worker = Worker(Store(self.root / 'state'))
        self.worker.action(self.job['id'], 'resume')
        job = self.store.job(self.job['id'])
        self.assertEqual(job['selection_files'], [0, 1])
        self.assertEqual(job['selection_state'], 'committed')
        self.assertEqual(job['remote_dir'], self.job['remote_dir'])
        self.assertFalse(self.client.paused)

    def test_restart_during_applying_never_imports_unconfirmed_files(self):
        self.worker.files(self.job['id'])
        job = self.store.job(self.job['id'])
        job['selection_state'] = 'applying'
        self.store.save_job(job)
        Worker(Store(self.root / 'state')).tick()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['selection_state'], 'awaiting_selection')
        self.assertEqual(job['state'], 'downloading')

    def test_original_server_and_path_guards_cannot_be_bypassed_by_settings_edit(self):
        self.store.save_settings({'downloader': {'url': 'http://new.invalid', 'remote_root': '/other', 'password': 'different'}})
        self.client.path = '/other/' + self.job['id']
        with self.assertRaisesRegex(ValueError, 'downloadmap'):
            self.worker.files(self.job['id'])
        passed = self.get_client.call_args.args[0]
        self.assertEqual(passed['url'], self.config['downloader']['url'])
        self.assertEqual(self.client.selections, [])

    def test_import_rechecks_completion_and_current_metadata_between_worker_steps(self):
        self.choose()
        self.worker.tick()
        self.client.contents[0]['progress'] = .5
        self.worker.tick()
        self.assertEqual(self.store.job(self.job['id'])['state'], 'downloading')

    def test_importer_also_rejects_unconfirmed_or_unselected_files(self):
        with self.assertRaisesRegex(ValueError, 'bevestig'):
            import_media(self.job, FILES)
        self.choose()
        job = self.store.job(self.job['id'])
        with self.assertRaisesRegex(ValueError, 'bevestigde keuze'):
            import_media(job, FILES)

    def test_transient_missing_metadata_restores_confirmed_choice_after_restart(self):
        self.choose()
        self.client.ready = False
        self.worker.tick()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['selection_state'], 'waiting_metadata')
        self.assertEqual(job['selection_files'], [0, 1])
        self.client.ready = True
        Worker(Store(self.root / 'state')).tick()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['selection_state'], 'committed')
        self.assertEqual(job['selection_files'], [0, 1])

    def test_failed_resume_preserves_choice_and_exposes_stopped_resume_action(self):
        original = self.client.action
        def action(torrent_id, choice):
            if choice == 'resume':
                raise ValueError('Fixture resume failed')
            return original(torrent_id, choice)
        with patch.object(self.client, 'action', side_effect=action):
            result = self.choose()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['state'], 'stopped')
        self.assertEqual(result['selection_state'], 'committed')
        self.assertEqual(job['selection_files'], [0, 1])
        self.worker.action(self.job['id'], 'resume')
        self.assertFalse(self.client.paused)

    def test_initial_space_checks_use_unknown_selection_then_selected_remaining_bytes(self):
        item = {'kind': 'tv', 'title': 'Space', 'link': MAGNET + '&dn=space', 'selection_requested': True, 'expected_bytes': 1000}
        with patch('plexport.core.require_storage') as require:
            result = self.worker.enqueue(item)
        self.assertEqual(result['torrent_expected_bytes'], 1000)
        self.assertEqual(result['expected_bytes'], 0)
        self.assertEqual(require.call_args.args[2], 0)
        with patch('plexport.core.require_storage') as require:
            self.choose((0, 2))
        self.assertEqual(require.call_args.args[2], 9)
        job = self.store.job(self.job['id'])
        self.assertEqual(job['expected_bytes'], 14)
        self.assertEqual(job['selected_bytes'], 14)

    def test_insufficient_selected_download_space_keeps_task_paused_and_unconfirmed(self):
        view = self.worker.files(self.job['id'])
        with patch('plexport.core.require_storage', side_effect=ValueError('Te weinig vrije ruimte')):
            with self.assertRaisesRegex(ValueError, 'Te weinig'):
                self.worker.select(self.job['id'], [0, 2], view['metadata_token'])
        self.assertEqual(self.store.job(self.job['id'])['selection_state'], 'awaiting_selection')
        self.assertTrue(self.client.paused)
        self.assertEqual(self.client.selections, [])

    def test_spaced_multi_episode_filename_preserves_all_episodes_in_import_name(self):
        self.client.contents[0]['name'] = 'Show/Show.S01E01.E02.mkv'
        self.choose((0,))
        path = Path(self.job['local_dir']) / self.client.contents[0]['name']
        path.parent.mkdir(parents=True)
        path.write_bytes(b'x' * 5)
        self.worker.tick()
        self.worker.tick()
        job = self.store.job(self.job['id'])
        self.assertEqual(job['state'], 'done')
        self.assertTrue(job['files_imported'][0].endswith('Show - S01E01E02.mkv'))

    def test_partial_import_error_and_stopped_import_cannot_rewrite_confirmed_choice(self):
        view = self.worker.files(self.job['id'])
        self.choose()
        job = self.store.job(self.job['id'])
        for state in ({'state': 'error', 'retry_state': 'importing'},
                      {'state': 'stopped', 'resume_state': 'importing'},
                      {'state': 'error', 'retry_state': 'downloading', 'import_started': True}):
            self.store.save_job({**job, **state})
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'import is al gestart'):
                self.worker.select(self.job['id'], [2], view['metadata_token'])
            self.assertEqual(self.store.job(self.job['id'])['selection_files'], [0, 1])

    def test_metadata_changes_after_import_began_keep_the_original_confirmed_snapshot(self):
        self.choose()
        job = self.store.job(self.job['id'])
        job['import_started'] = True
        self.store.save_job(job)
        self.client.contents[0]['name'] = 'Show/Show.S01E10.mkv'
        self.worker.tick()
        saved = self.store.job(self.job['id'])
        self.assertEqual(saved['state'], 'error')
        self.assertEqual(saved['selection_files'], [0, 1])
        self.assertEqual(saved['selection_metadata'], job['selection_metadata'])
        self.assertIn('nadat de import begon', saved['error'])


class SelectionAPIAndConflictTests(SelectionSetup):
    def setUp(self):
        super().setUp()
        self.authorization = 'Basic ' + base64.b64encode(b'admin:local-fixture-password').decode()
        self.server, self.api_worker = create_server('127.0.0.1', 0, self.store, password='local-fixture-password')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        super().tearDown()

    def post(self, endpoint, data):
        req = urllib.request.Request(self.url + endpoint, json.dumps(data).encode(),
                                     {'Content-Type': 'application/json', 'X-PlexPort': '1', 'Authorization': self.authorization})
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_http_selection_wait_commit_and_changed_token(self):
        code, view = self.post('/api/files', {'id': self.job['id']})
        self.assertEqual(code, 200)
        self.assertEqual(view['state'], 'awaiting_selection')
        code, error = self.post('/api/select', {'id': self.job['id'], 'files': [0], 'metadata_token': 'old'})
        self.assertEqual((code, error['code']), (409, 'metadata_changed'))
        code, result = self.post('/api/select', {'id': self.job['id'], 'files': [0, 1], 'metadata_token': view['metadata_token']})
        self.assertEqual(code, 200)
        self.assertEqual(result['state'], 'committed')
        self.assertEqual(result['selection_files'], [0, 1])

    def test_authenticated_index_scripts_are_all_served_as_javascript(self):
        class Scripts(HTMLParser):
            def __init__(self):
                super().__init__()
                self.sources = []

            def handle_starttag(self, tag, attrs):
                if tag == 'script':
                    source = dict(attrs).get('src', '')
                    parsed = urllib.parse.urlsplit(source)
                    if source and not parsed.scheme and not parsed.netloc:
                        self.sources.append(source)

        parser = Scripts()
        request = urllib.request.Request(self.url + '/', headers={'Authorization': self.authorization})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 200)
            parser.feed(response.read().decode())
        self.assertIn('/selection.js', parser.sources)
        for source in parser.sources:
            with self.subTest(script=source):
                request = urllib.request.Request(urllib.parse.urljoin(self.url, source),
                                                 headers={'Authorization': self.authorization})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(response.headers.get_content_type(), ('text/javascript', 'application/javascript'))
                    self.assertGreater(len(response.read()), 0)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.url + '/selection.js')
        self.assertEqual(error.exception.code, 401)
        error.exception.close()

    def test_preflight_returns_history_and_optional_capability_without_secrets(self):
        code, report = self.post('/api/preflight', {'kind': 'tv', 'title': 'Show', 'expected_bytes': 14})
        self.assertEqual(code, 200)
        self.assertEqual(report['title_conflicts'][0]['id'], self.job['id'])
        self.assertIn('method', report['import_capability'])
        self.assertTrue(report['ok'])
        for key in ('config', 'remote_dir', 'local_dir', 'torrent_fingerprint'):
            self.assertNotIn(key, report['title_conflicts'][0])

    def test_title_conflict_requires_current_ids_and_fingerprint_cannot_be_overridden(self):
        payload = {'kind': 'tv', 'title': 'Show', 'link': MAGNET + '&dn=another'}
        code, error = self.post('/api/jobs', payload)
        self.assertEqual((code, error['code']), (409, 'title_conflict'))
        self.assertEqual(error['matches'][0]['id'], self.job['id'])
        code, result = self.post('/api/jobs', {**payload, 'confirmed_conflicts': [self.job['id']]})
        self.assertEqual(code, 201)
        code, error = self.post('/api/jobs', {**payload, 'confirmed_conflicts': [self.job['id'], result['id']]})
        self.assertEqual(code, 400)
        self.assertIn('al in PlexPort', error['error'])
        code, error = self.post('/api/jobs', {**payload, 'link': MAGNET + '&dn=third', 'confirmed_conflicts': [self.job['id']]})
        self.assertEqual((code, error['code']), (409, 'title_conflict'))

    def test_concurrent_new_versions_have_one_winner_and_one_explicit_conflict(self):
        self.store.delete_job(self.job['id'])
        barrier = threading.Barrier(2)
        def enqueue(number):
            barrier.wait()
            try:
                return self.api_worker.enqueue({'kind': 'movie', 'title': 'Parallel', 'year': '2025', 'link': MAGNET + '&dn=' + str(number)})
            except APIConflict as error:
                return error
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(enqueue, [1, 2]))
        self.assertEqual(len(self.store.jobs()), 1)
        self.assertEqual(sum(isinstance(item, APIConflict) for item in result), 1)


class FilePriorityContractTests(unittest.TestCase):
    def setUp(self):
        self.files = copy.deepcopy(FILES[:3])
        self.calls = []
        self.remote = '/downloads/fixture'
        self.owner = self
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.reply_qbit()

            def do_POST(self):
                if self.path == '/transmission/rpc':
                    body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    fixture.calls.append(body)
                    args = body['arguments']
                    if body['method'] == 'torrent-get':
                        response = {'torrents': [{'hashString': HASH, 'name': 'Show', 'percentDone': .2,
                            'rateDownload': 0, 'eta': 0, 'status': 0, 'error': 0, 'errorString': '',
                            'metadataPercentComplete': 1, 'sizeWhenDone': 17, 'peersConnected': 0,
                            'downloadDir': fixture.remote,
                            'files': [{'name': f['name'], 'length': f['size'], 'bytesCompleted': int(f['size'] * f['progress'])} for f in fixture.files],
                            'fileStats': [{'wanted': f['wanted']} for f in fixture.files]}]}
                    else:
                        for f in fixture.files:
                            if f['index'] in args.get('files-unwanted', []):
                                f['wanted'] = False
                            if f['index'] in args.get('files-wanted', []):
                                f['wanted'] = True
                        response = {}
                    self.reply({'result': 'success', 'arguments': response})
                else:
                    self.reply_qbit()

            def reply_qbit(self):
                path = urllib.parse.urlsplit(self.path).path
                params = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode())
                fixture.calls.append((self.path, params))
                if path.endswith('/info'):
                    self.reply([{'hash': HASH, 'name': 'Show', 'progress': .2, 'dlspeed': 0, 'eta': 0,
                                 'state': 'stoppedDL', 'amount_left': 9, 'size': 17, 'save_path': fixture.remote}])
                elif path.endswith('/files'):
                    self.reply([{**f, 'priority': 1 if f['wanted'] else 0} for f in fixture.files][::-1])
                elif path.endswith('/filePrio'):
                    for f in fixture.files:
                        if str(f['index']) in params['id'][0].split('|'):
                            f['wanted'] = params['priority'][0] != '0'
                    self.reply(None)
                else:
                    self.send_error(404)

            def reply(self, value):
                data = b'' if value is None else json.dumps(value).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_qbittorrent_uses_actual_indices_explicit_single_hash_and_verified_priorities(self):
        c = QBittorrent({'url': self.url})
        token = metadata_token(HASH, self.files)
        c.select_files(HASH, [0, 1], self.remote, token)
        changes = [params for path, params in self.calls if 'filePrio' in path]
        self.assertEqual(changes, [{'hash': [HASH], 'id': ['2|1|0'], 'priority': ['0']},
                                   {'hash': [HASH], 'id': ['0|1'], 'priority': ['1']}])
        self.assertEqual([f['index'] for f in self.files if f['wanted']], [0, 1])

    def test_transmission_uses_only_this_hash_and_never_sends_empty_all_files_arrays(self):
        c = Transmission({'url': self.url + '/transmission/rpc'})
        token = metadata_token(HASH, self.files)
        c.select_files(HASH, [0, 1], self.remote, token)
        changes = [call for call in self.calls if call['method'] == 'torrent-set']
        self.assertEqual(changes[0]['arguments'], {'ids': [HASH], 'files-wanted': [0, 1], 'files-unwanted': [2]})
        self.calls.clear()
        c.select_files(HASH, [0, 1, 2], self.remote, token)
        changes = [call for call in self.calls if call['method'] == 'torrent-set']
        self.assertNotIn('files-unwanted', changes[0]['arguments'])

    def test_both_clients_reject_changed_metadata_locations_and_all_torrent_ids_before_mutating(self):
        for c in (QBittorrent({'url': self.url}), Transmission({'url': self.url + '/transmission/rpc'})):
            for torrent, path, token in [('all', self.remote, 'old'), (HASH, '/different', metadata_token(HASH, self.files)),
                                         (HASH, self.remote, 'old')]:
                with self.subTest(client=type(c).__name__, torrent=torrent, path=path), self.assertRaises(ValueError):
                    c.select_files(torrent, [0], path, token)
        self.assertFalse(any(isinstance(call, dict) and call['method'] == 'torrent-set' or isinstance(call, tuple) and 'filePrio' in call[0] for call in self.calls))


if __name__ == '__main__':
    unittest.main()
