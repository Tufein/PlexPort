from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jellyport.core import APIConflict, Store, Worker, defaults, mapped_local_dir

HASH = 'a' * 40


class AdoptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = defaults()
        self.config['downloader'].update(url='http://downloader.local:8080', type='qbittorrent',
                                         local_root=str(self.root/'downloads'), remote_root='/downloads')
        self.config['library'] = {'movies': str(self.root/'movies'), 'tv': str(self.root/'tv')}
        for path in [self.config['downloader']['local_root'], *self.config['library'].values()]:
            Path(path).mkdir()
        (self.root/'downloads'/'Film.2020').mkdir()
        (self.root/'downloads'/'Film.2020'/'film.mkv').write_bytes(b'x' * 10)
        self.store = Store(self.root/'state')
        self.store.save_settings(self.config)
        self.worker = Worker(self.store)
        self.client = Mock()
        self.client.status.return_value = {
            'complete': True, 'save_dir': '/downloads/Film.2020', 'files': [{'name': 'film.mkv', 'size': 10}],
            'progress': 1, 'speed': 0, 'eta': 0, 'paused': False, 'activity': 'seeding'}

    def tearDown(self):
        self.temp.cleanup()

    def adopt(self, **extra):
        data = {'id': HASH, 'kind': 'movie', 'title': 'Film', 'year': '2020', **extra}
        with patch('jellyport.core.client', return_value=self.client):
            return self.worker.adopt(data)

    def test_mapping_stays_inside_the_download_root(self):
        downloader = self.config['downloader']
        self.assertEqual(mapped_local_dir(downloader, '/downloads/Film.2020'), str(self.root/'downloads'/'Film.2020'))
        for outside in ('/other/Film.2020', '/downloadsX/Film.2020', '/Downloads/Film.2020', '/downloads/../etc'):
            with self.subTest(outside=outside), self.assertRaises(ValueError):
                mapped_local_dir(downloader, outside)
        with self.assertRaises(ValueError):
            mapped_local_dir(downloader, '/downloads/missing')

    def test_adopts_completed_torrent_without_touching_downloader(self):
        job = self.adopt()
        self.assertTrue(job['adopted'])
        self.assertEqual(job['torrent_id'], HASH)
        self.assertEqual(job['state'], 'downloading')
        self.client.add.assert_not_called()
        self.client.action.assert_not_called()
        # The normal worker path imports it.
        with patch('jellyport.core.client', return_value=self.client):
            self.worker.tick()
            self.worker.tick()
        self.assertTrue(any((self.root/'movies').rglob('*.mkv')))
        self.assertTrue((self.root/'downloads'/'Film.2020'/'film.mkv').exists())

    def test_rejects_incomplete_duplicate_and_invalid_ids(self):
        self.client.status.return_value = {**self.client.status.return_value, 'complete': False}
        with self.assertRaises(ValueError):
            self.adopt()
        self.client.status.return_value['complete'] = True
        self.adopt()
        with self.assertRaises(ValueError):
            self.adopt()
        with self.assertRaises(ValueError):
            self.adopt(id='nothex')

    def test_title_history_requires_explicit_confirmation(self):
        first = self.adopt()
        other = 'b' * 40
        with self.assertRaises(APIConflict):
            self.adopt(id=other)
        self.assertEqual(len(self.store.jobs()), 1)
        second = self.adopt(id=other, confirmed_conflicts=[first['id']])
        self.assertNotEqual(second['id'], first['id'])

    def test_stop_and_delete_never_touch_the_users_torrent(self):
        job = self.adopt()
        with patch('jellyport.core.client', return_value=self.client):
            self.worker.action(job['id'], 'stop')
            self.worker.action(job['id'], 'resume')
            with self.assertRaises(ValueError):
                self.worker.action(job['id'], 'remove', delete_files=True)
            self.worker.action(job['id'], 'remove')
        self.client.action.assert_not_called()
        self.client.remove.assert_called_once()
        self.assertEqual(self.client.remove.call_args.args[1], False)
        self.assertTrue((self.root/'downloads'/'Film.2020'/'film.mkv').exists())

    def test_listing_skips_known_and_plexport_torrents_and_flags_unmapped(self):
        self.adopt()
        self.client.list_completed.return_value = [
            {'id': HASH, 'name': 'Known', 'size': 1, 'save_dir': '/downloads/Film.2020', 'tags': ''},
            {'id': 'c' * 40, 'name': 'Ours', 'size': 1, 'save_dir': '/downloads/Film.2020', 'tags': 'jellyport-x'},
            {'id': 'd' * 40, 'name': 'Elsewhere', 'size': 1, 'save_dir': '/media/other', 'tags': ''},
            {'id': 'e' * 40, 'name': 'Fine', 'size': 1, 'save_dir': '/downloads/Film.2020', 'tags': 'misc'}]
        with patch('jellyport.core.client', return_value=self.client):
            result = self.worker.existing_downloads()
        ids = {t['id']: t for t in result['torrents']}
        self.assertEqual(set(ids), {'d' * 40, 'e' * 40})
        self.assertFalse(ids['d' * 40]['importable'])
        self.assertTrue(ids['e' * 40]['importable'])


if __name__ == '__main__':
    unittest.main()
