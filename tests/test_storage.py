import copy
import errno
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from plexport.storage import import_capability


class ImportCapabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.downloads, self.movies, self.tv = [self.root / name for name in ('downloads', 'movies', 'tv')]
        for path in (self.downloads, self.movies, self.tv):
            path.mkdir()
            (path / 'existing.mkv').write_bytes(b'existing user media')
        self.config = {'downloader': {'local_root': str(self.downloads), 'remote_root': '/downloads',
                                      'url': 'http://client.invalid', 'password': 'fixture-secret'},
                       'library': {'movies': str(self.movies), 'tv': str(self.tv)}}
        self.before = copy.deepcopy(self.config)

    def assert_clean(self):
        self.assertEqual(self.config, self.before)
        for path in (self.downloads, self.movies, self.tv):
            self.assertEqual([p.name for p in path.iterdir()], ['existing.mkv'])
            self.assertEqual((path / 'existing.mkv').read_bytes(), b'existing user media')

    def test_actual_link_is_observed_and_existing_media_and_settings_are_preserved(self):
        with patch('plexport.storage.shutil.disk_usage', return_value=SimpleNamespace(free=500)):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'hardlink')
        self.assertIs(result['supported'], True)
        self.assertEqual(result['additional_bytes'], 0)
        self.assertEqual(result['required_library_bytes'], 0)
        self.assertEqual(result['required_shared_bytes'], 100)
        self.assertIs(result['space_ok'], True)
        self.assertIn('momentopname', result['note'])
        self.assertIsNone(result['error'])
        self.assert_clean()

    def test_tv_probe_uses_only_selected_destination_and_unique_temporary_names(self):
        real_link = os.link
        used = []
        def observe(source, destination):
            self.assertEqual(Path(source).parent, self.downloads)
            self.assertEqual(Path(destination).parent, self.tv)
            used.extend((str(source), str(destination)))
            real_link(source, destination)
        with patch('plexport.storage.os.link', side_effect=observe):
            self.assertEqual(import_capability(self.config, 'tv')['method'], 'hardlink')
            self.assertEqual(import_capability(self.config, 'tv')['method'], 'hardlink')
        self.assertEqual(len(set(used)), 4)
        self.assert_clean()

    def test_unknown_size_never_claims_zero_extra_space(self):
        for failure in (None, OSError(errno.EXDEV, 'different filesystem')):
            with self.subTest(failure=failure), patch('plexport.storage.os.link', wraps=os.link,
                                                     side_effect=failure):
                result = import_capability(self.config, 'movie')
            self.assertIsNone(result['additional_bytes'])
            self.assertIsNone(result['space_ok'])
            self.assertIsNone(result['required_download_bytes'])
        self.assert_clean()

    def test_cross_filesystem_and_unsupported_links_confirm_writable_copy_destination(self):
        for number in {errno.EXDEV, errno.EOPNOTSUPP, errno.ENOSYS}:
            with self.subTest(errno=number), patch('plexport.storage.os.link', side_effect=OSError(number, 'link unavailable')):
                result = import_capability(self.config, 'movie', 100)
            self.assertEqual(result['method'], 'copy')
            self.assertIs(result['supported'], False)
            self.assertEqual(result['additional_bytes'], 100)
            self.assertIsNone(result['error'])
            self.assert_clean()

    def test_shared_copy_needs_both_download_and_copy_without_adding_free_readings(self):
        with patch('plexport.storage.os.link', side_effect=OSError(errno.EXDEV, 'dataset boundary')):
            with patch('plexport.storage.shutil.disk_usage', side_effect=[SimpleNamespace(free=150), SimpleNamespace(free=180)]):
                result = import_capability(self.config, 'movie', 100)
            self.assertIs(result['shared_filesystem'], True)
            self.assertEqual(result['required_shared_bytes'], 200)
            self.assertEqual(result['download_free_bytes'], 150)
            self.assertEqual(result['library_free_bytes'], 180)
            self.assertIs(result['space_ok'], False)
            with patch('plexport.storage.shutil.disk_usage', return_value=SimpleNamespace(free=200)):
                self.assertIs(import_capability(self.config, 'movie', 100)['space_ok'], True)
        self.assert_clean()

    def test_separate_storage_checks_each_free_reading_against_its_own_requirement(self):
        real_stat = Path.stat
        def devices(path, *args, **kwargs):
            value = real_stat(path, *args, **kwargs)
            if path == self.movies:
                fields = list(value)
                fields[2] += 1
                return os.stat_result(fields)
            return value
        with patch('plexport.storage.Path.stat', devices), patch('plexport.storage.os.link', side_effect=OSError(errno.EXDEV, 'other disk')):
            with patch('plexport.storage.shutil.disk_usage', side_effect=[SimpleNamespace(free=100), SimpleNamespace(free=100)]):
                result = import_capability(self.config, 'movie', 100)
            self.assertIs(result['shared_filesystem'], False)
            self.assertIs(result['space_ok'], True)
            self.assertIsNone(result['required_shared_bytes'])
            with patch('plexport.storage.shutil.disk_usage', side_effect=[SimpleNamespace(free=500), SimpleNamespace(free=99)]):
                self.assertIs(import_capability(self.config, 'movie', 100)['space_ok'], False)
            with patch('plexport.storage.shutil.disk_usage', side_effect=[SimpleNamespace(free=99), SimpleNamespace(free=500)]):
                self.assertIs(import_capability(self.config, 'movie', 100)['space_ok'], False)
        self.assert_clean()

    def test_hardlink_still_needs_download_space(self):
        with patch('plexport.storage.shutil.disk_usage', return_value=SimpleNamespace(free=99)):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'hardlink')
        self.assertIs(result['space_ok'], False)
        self.assert_clean()

    def test_permission_and_other_link_errors_are_unknown_not_confirmed_copy(self):
        for number in (errno.EACCES, errno.EPERM, errno.EIO):
            with self.subTest(errno=number), patch('plexport.storage.os.link', side_effect=OSError(number, 'fixture')):
                result = import_capability(self.config, 'movie', 100)
            self.assertEqual(result['method'], 'unknown')
            self.assertIsNone(result['supported'])
            self.assertIsNone(result['additional_bytes'])
            self.assertIsNone(result['space_ok'])
            self.assertTrue(result['error'])
            self.assert_clean()

    def test_missing_root_is_not_created_and_no_unselected_root_is_required(self):
        (self.tv / 'existing.mkv').unlink()
        self.tv.rmdir()
        self.assertEqual(import_capability(self.config, 'movie')['method'], 'hardlink')
        result = import_capability(self.config, 'tv', 100)
        self.assertEqual(result['method'], 'unknown')
        self.assertIn('mediamap', result['error'])
        self.assertFalse(self.tv.exists())
        self.assertEqual(list(self.downloads.glob('.plexport-*')), [])
        self.assertEqual(self.config, self.before)

    def test_disappearing_folder_cleans_source_and_does_not_recreate_folder(self):
        def disappear(*_):
            (self.movies / 'existing.mkv').unlink()
            self.movies.rmdir()
            raise FileNotFoundError(errno.ENOENT, 'gone')
        with patch('plexport.storage.os.link', side_effect=disappear):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'unknown')
        self.assertIn('verdwenen', result['error'])
        self.assertEqual(list(self.downloads.glob('.plexport-*')), [])
        self.assertFalse(self.movies.exists())

    def test_read_failure_cleans_both_probe_files(self):
        real_read = Path.read_bytes
        def read(path):
            if path.name.startswith('.plexport-import-'):
                raise PermissionError(errno.EACCES, 'read denied')
            return real_read(path)
        with patch('plexport.storage.Path.read_bytes', read):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'unknown')
        self.assertTrue(result['error'])
        self.assert_clean()

    def test_failed_source_creation_does_not_claim_copy_or_change_media(self):
        with patch('plexport.storage.tempfile.mkstemp', side_effect=OSError(errno.ENOSPC, 'full')):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'unknown')
        self.assertIn('geen vrije ruimte', result['error'])
        self.assertIsNone(result['space_ok'])
        self.assert_clean()

    def test_existing_destination_collision_is_never_removed(self):
        collision = self.movies / '.plexport-import-fixture'
        collision.write_bytes(b'unrelated existing file')
        try:
            with patch('plexport.storage.uuid.uuid4', return_value=SimpleNamespace(hex='fixture')):
                with patch('plexport.storage.os.link', side_effect=OSError(errno.EXDEV, 'other disk')):
                    result = import_capability(self.config, 'movie', 100)
            self.assertEqual(result['method'], 'unknown')
            self.assertEqual(collision.read_bytes(), b'unrelated existing file')
            self.assertEqual(list(self.downloads.glob('.plexport-*')), [])
        finally:
            collision.unlink()
        self.assert_clean()

    def test_bad_readback_does_not_claim_hardlink_support(self):
        with patch('plexport.storage.Path.read_bytes', return_value=b'wrong bytes'):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'unknown')
        self.assertIn('teruggelezen', result['error'])
        self.assert_clean()

    def test_unwritable_copy_destination_is_unknown_and_source_is_cleaned(self):
        real_open = Path.open
        def denied(path, *args, **kwargs):
            if path.name.startswith('.plexport-import-') and args and args[0] == 'xb':
                raise PermissionError(errno.EACCES, 'copy denied')
            return real_open(path, *args, **kwargs)
        with patch('plexport.storage.os.link', side_effect=OSError(errno.EXDEV, 'other disk')):
            with patch('plexport.storage.Path.open', denied):
                result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'unknown')
        self.assertIn('maprechten', result['error'])
        self.assert_clean()

    def test_cleanup_failure_is_reported_and_other_file_is_still_removed(self):
        real_unlink = os.unlink
        blocked = []
        def denied(path, *args, **kwargs):
            if Path(path).parent == self.movies and Path(path).name.startswith('.plexport-import-'):
                blocked.append(Path(path))
                raise PermissionError(errno.EACCES, 'cleanup denied')
            return real_unlink(path, *args, **kwargs)
        with patch('plexport.storage.os.unlink', side_effect=denied):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'unknown')
        self.assertIsNone(result['supported'])
        self.assertEqual(result['cleanup_errors'], [str(blocked[0])])
        self.assertIn('verwijderd', result['error'])
        self.assertEqual(list(self.downloads.glob('.plexport-*')), [])
        for path in set(blocked):
            path.unlink()
        self.assert_clean()

    def test_transient_cleanup_failure_is_retried_without_leaving_files(self):
        real_unlink = os.unlink
        first = True
        def transient(path, *args, **kwargs):
            nonlocal first
            if first:
                first = False
                raise OSError(errno.EBUSY, 'busy')
            return real_unlink(path, *args, **kwargs)
        with patch('plexport.storage.os.unlink', side_effect=transient):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'hardlink')
        self.assertEqual(result['cleanup_errors'], [])
        self.assert_clean()

    def test_free_space_failure_is_unknown_and_leaves_no_probe_files(self):
        with patch('plexport.storage.shutil.disk_usage', side_effect=PermissionError(errno.EACCES, 'quota read denied')):
            result = import_capability(self.config, 'movie', 100)
        self.assertEqual(result['method'], 'unknown')
        self.assertIsNone(result['space_ok'])
        self.assertIsNone(result['additional_bytes'])
        self.assert_clean()

    def test_invalid_inputs_fail_before_any_files_are_created(self):
        for size in (-1, True, '100', 1.5, None, 1024 ** 5 + 1):
            with self.subTest(size=size), self.assertRaises(ValueError):
                import_capability(self.config, 'movie', size)
        with self.assertRaises(ValueError):
            import_capability(self.config, 'music', 100)
        self.assert_clean()


if __name__ == '__main__':
    unittest.main()
