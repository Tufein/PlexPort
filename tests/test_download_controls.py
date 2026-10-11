import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from plexport.core import Store, Worker, defaults, import_media, new_job


class DownloadControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = defaults()
        self.config['downloader'].update(url='http://downloader.local:8080', type='qbittorrent',
                                         local_root=str(self.root/'downloads'), remote_root='/downloads')
        self.config['library'] = {'movies':str(self.root/'movies'), 'tv':str(self.root/'tv')}
        for path in [self.config['downloader']['local_root'], *self.config['library'].values()]:
            Path(path).mkdir()
        self.store = Store(self.root/'state')
        self.store.save_settings(self.config)
        self.worker = Worker(self.store)
        self.job = new_job(self.config, {'title':'Controls', 'link':'magnet:?xt=urn:btih:'+'a'*40})
        self.store.save_job(self.job)

    def tearDown(self):
        self.temp.cleanup()

    def submitted(self, state='downloading'):
        self.job.update(torrent_id='a'*40, add_started=True, state=state)
        self.store.save_job(self.job)

    def test_queue_stop_survives_restart_without_submitting(self):
        with patch('plexport.core.client') as get_client:
            self.worker.action(self.job['id'], 'stop')
            worker = Worker(Store(self.root/'state'))
            worker.tick()
            get_client.assert_not_called()
            self.assertEqual(self.store.job(self.job['id'])['state'], 'stopped')
            self.assertEqual(worker.action(self.job['id'], 'resume')['state'], 'queued')

    def test_stop_blocks_import_and_resume_retains_progress(self):
        self.submitted()
        self.job['progress'] = 1
        self.store.save_job(self.job)
        c = Mock()
        with patch('plexport.core.client', return_value=c), patch('plexport.core.import_media') as importer:
            self.worker.action(self.job['id'], 'stop')
            Worker(Store(self.root/'state')).tick()
            importer.assert_not_called()
            c.status.assert_not_called()
            c.action.assert_called_once_with('a'*40, 'pause')
            resumed = self.worker.action(self.job['id'], 'resume')
            self.assertEqual(resumed['progress'], 1)
            self.assertEqual(resumed['activity'], 'unknown')
            c.action.assert_called_with('a'*40, 'resume')

    def test_stop_during_import_keeps_it_on_hold_and_completed_task_does_not_reimport(self):
        for state in ('importing', 'scan_pending', 'done', 'error'):
            with self.subTest(state=state), patch('plexport.core.client'):
                self.submitted(state)
                self.worker.action(self.job['id'], 'stop')
                self.worker.action(self.job['id'], 'stop')
                self.assertEqual(self.worker.action(self.job['id'], 'resume')['state'], state)

    def test_recover_torrent_id_before_stop_and_remove(self):
        self.job['add_started'] = True
        self.store.save_job(self.job)
        c = Mock()
        c.find.return_value = 'b'*40
        with patch('plexport.core.client', return_value=c):
            self.worker.action(self.job['id'], 'stop')
            c.find.assert_called_once()
            c.action.assert_called_once_with('b'*40, 'pause')
            self.assertEqual(self.worker.action(self.job['id'], 'resume')['state'], 'downloading')
            self.worker.action(self.job['id'], 'remove')
            c.remove.assert_called_once_with('b'*40, False, self.job['remote_dir'])

    def test_unknown_pending_submission_is_retained_and_explicit_forget_is_available(self):
        self.job['add_started'] = True
        self.store.save_job(self.job)
        c = Mock()
        c.find.return_value = ''
        with patch('plexport.core.client', return_value=c):
            for action in ('stop', 'remove'):
                with self.assertRaisesRegex(ValueError, 'nog geen torrent-ID'):
                    self.worker.action(self.job['id'], action)
                self.assertEqual(self.store.job(self.job['id']), self.job)
            self.worker.action(self.job['id'], 'remove', forget=True)
            c.remove.assert_not_called()
        self.assertEqual(self.store.jobs(), [])

    def test_failed_downloader_action_keeps_task_and_files(self):
        self.submitted()
        c = Mock()
        c.remove.side_effect = TimeoutError()
        c.action.side_effect = TimeoutError()
        with patch('plexport.core.client', return_value=c):
            for action in ('stop', 'remove'):
                with self.assertRaises(TimeoutError):
                    self.worker.action(self.job['id'], action)
                self.assertEqual(self.store.job(self.job['id']), self.job)

    def test_removing_download_files_keeps_published_plex_media(self):
        self.submitted('done')
        source = Path(self.job['local_dir'])/'film.mkv'
        source.parent.mkdir()
        source.write_bytes(b'media')
        published = import_media(self.job, [{'name':'film.mkv', 'size':5}])
        self.job['files_imported'] = published
        self.store.save_job(self.job)
        c = Mock()
        c.remove.side_effect = lambda tid, delete_files, directory: source.unlink() if delete_files else None
        with patch('plexport.core.client', return_value=c):
            self.worker.action(self.job['id'], 'remove', delete_files=True)
        self.assertFalse(source.exists())
        self.assertEqual(Path(published[0]).read_bytes(), b'media')
        self.assertEqual(self.store.jobs(), [])

    def test_normal_removal_keeps_files_and_forget_never_contacts_downloader(self):
        self.submitted()
        source = Path(self.job['local_dir'])/'film.mkv'
        source.parent.mkdir()
        source.write_bytes(b'media')
        with patch('plexport.core.client') as get_client:
            self.worker.action(self.job['id'], 'remove')
            get_client.return_value.remove.assert_called_once_with('a'*40, False, self.job['remote_dir'])
        self.assertEqual(source.read_bytes(), b'media')
        self.store.save_job(self.job)
        with patch('plexport.core.client') as get_client:
            self.worker.action(self.job['id'], 'remove', forget=True)
            get_client.assert_not_called()

    def test_cleanup_uses_original_server_paths_and_updated_credentials_only_if_same_server(self):
        self.submitted()
        self.store.save_settings({'downloader':{'username':'new-user','password':'new-pass'}})
        with patch('plexport.core.client') as get_client:
            self.worker.action(self.job['id'], 'stop')
            config = get_client.call_args.args[0]
            self.assertEqual(config['password'], 'new-pass')
            self.assertEqual(config['remote_root'], '/downloads')
        self.store.save_settings({'downloader':{'url':'http://another.local:8080'}})
        with patch('plexport.core.client') as get_client:
            self.worker.action(self.job['id'], 'remove')
            config = get_client.call_args.args[0]
            self.assertEqual(config['url'], self.config['downloader']['url'])
            get_client.return_value.remove.assert_called_once_with('a'*40, False, self.job['remote_dir'])

    def test_tick_snapshot_does_not_resurrect_deleted_task_or_crash(self):
        snapshot = copy.deepcopy(self.store.jobs())
        self.store.delete_job(self.job['id'])
        with patch.object(self.store, 'jobs', return_value=snapshot), patch('plexport.core.client') as get_client:
            self.worker.tick()
            get_client.assert_not_called()
        self.assertEqual(self.store.jobs(), [])


if __name__ == '__main__':
    unittest.main()
