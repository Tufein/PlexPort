import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import update_nas


class NasUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.app = self.root / 'installation' / 'code'
        self.data = self.root / 'installation' / 'data'
        self.backups = self.root / 'installation' / 'backups'
        self.release = self.root / 'release'
        self.app.mkdir(parents=True)
        self.data.mkdir()
        self.release.mkdir()
        for name in update_nas.RELEASE_REQUIRED + ('static/plexport.apk',):
            old = self.app / 'plexport' / name
            new = self.release / 'plexport' / name
            old.parent.mkdir(parents=True, exist_ok=True)
            new.parent.mkdir(parents=True, exist_ok=True)
            old.write_bytes(b'old runtime')
            new.write_bytes(b'new runtime')
        self.compose = self.app / 'compose.yaml'
        self.compose.write_text('saved configuration and secret')
        self.compose.chmod(0o600)
        self.download = self.root / 'installation' / 'downloads' / 'torrent.bin'
        self.download.parent.mkdir()
        self.download.write_bytes(b'existing torrent')
        self.media = self.root / 'installation' / 'media' / 'film.mkv'
        self.media.parent.mkdir()
        self.media.write_bytes(b'existing media')
        self.database = self.data / 'plexport.sqlite'
        with sqlite3.connect(self.database) as connection:
            connection.execute('CREATE TABLE tasks (title TEXT)')
            connection.execute('INSERT INTO tasks VALUES (?)', ('Active task',))
        self.manifest()

    def manifest(self):
        records = [f'{update_nas.digest(path)}  {path.relative_to(self.release)}'
                   for path in sorted((self.release / 'plexport').rglob('*')) if path.is_file()]
        (self.release / 'SHA256SUMS').write_text('\n'.join(records) + '\n')

    def update(self, source=None, sha=None):
        return update_nas.update(self.app, self.data, self.backups, source or self.release, sha)

    def tasks(self, database=None):
        with sqlite3.connect(database or self.database) as connection:
            return connection.execute('SELECT title FROM tasks').fetchall()

    def test_update_preserves_settings_tasks_media_and_runtime_metadata(self):
        runtime = self.app / 'plexport'
        runtime.chmod(0o750)
        server = runtime / 'server.py'
        server.chmod(0o640)
        before = server.stat()
        new = self.release / 'plexport' / 'new_module.py'
        new.write_text('new module')
        new.chmod(0o600)
        removed = runtime / 'retired.py'
        removed.write_text('old module removed by release')
        self.manifest()
        backup = self.update()
        self.assertEqual(server.read_bytes(), b'new runtime')
        self.assertEqual((runtime / 'static' / 'plexport.apk').read_bytes(), b'new runtime')
        self.assertFalse(removed.exists())
        self.assertEqual(server.stat().st_mode & 0o777, 0o640)
        self.assertEqual((server.stat().st_uid, server.stat().st_gid), (before.st_uid, before.st_gid))
        self.assertEqual(runtime.stat().st_mode & 0o777, 0o750)
        self.assertEqual((runtime / 'new_module.py').stat().st_mode & 0o777, 0o644)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual((backup / 'plexport.sqlite').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.tasks(), [('Active task',)])
        self.assertEqual(self.tasks(backup / 'plexport.sqlite'), [('Active task',)])
        self.assertEqual((backup / 'code' / 'plexport' / 'retired.py').read_text(), 'old module removed by release')
        self.assertEqual(self.compose.read_text(), 'saved configuration and secret')
        self.assertEqual(self.compose.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.download.read_bytes(), b'existing torrent')
        self.assertEqual(self.media.read_bytes(), b'existing media')

    def test_sqlite_wal_snapshot_contains_committed_tasks(self):
        connection = sqlite3.connect(self.database)
        self.addCleanup(connection.close)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('INSERT INTO tasks VALUES (?)', ('Committed in WAL',))
        connection.commit()
        self.assertTrue(Path(str(self.database) + '-wal').exists())
        backup = self.update()
        self.assertEqual(self.tasks(backup / 'plexport.sqlite'), [('Active task',), ('Committed in WAL',)])

    def test_code_rollback_keeps_tasks_saved_after_restart(self):
        backup = self.update()
        with sqlite3.connect(self.database) as connection:
            connection.execute('INSERT INTO tasks VALUES (?)', ('Task after update',))
        update_nas.rollback(self.app, backup)
        self.assertEqual((self.app / 'plexport' / 'server.py').read_bytes(), b'old runtime')
        self.assertEqual(self.tasks(), [('Active task',), ('Task after update',)])
        self.assertEqual(self.compose.read_text(), 'saved configuration and secret')

    def test_failed_install_rename_restores_previous_code(self):
        rename = os.replace

        def fail_install(source, destination):
            if Path(source).name == 'next':
                raise OSError('simulated storage error')
            return rename(source, destination)

        with patch.object(update_nas.os, 'replace', side_effect=fail_install):
            with self.assertRaisesRegex(OSError, 'storage error'):
                self.update()
        self.assertEqual((self.app / 'plexport' / 'server.py').read_bytes(), b'old runtime')
        self.assertEqual(self.tasks(), [('Active task',)])
        self.assertEqual(list(self.app.glob('.plexport-update-*')), [])

    def test_bad_checksum_fails_before_install_or_backup(self):
        (self.release / 'plexport' / 'server.py').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.update()
        self.assertFalse(self.backups.exists())
        self.assertEqual((self.app / 'plexport' / 'server.py').read_bytes(), b'old runtime')

    def test_unlisted_runtime_file_is_rejected(self):
        (self.release / 'plexport' / 'unlisted.py').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'cover every runtime file'):
            self.update()

    def test_consistent_manifest_cannot_hide_missing_import_or_frontend_script(self):
        for name in ('__init__.py', 'integrations.py', 'static/jobs.js'):
            with self.subTest(missing=name):
                source = self.release / 'plexport' / name
                original = source.read_bytes()
                source.unlink()
                self.manifest()
                with self.assertRaisesRegex(ValueError, 'runtime is incomplete'):
                    self.update()
                self.assertFalse(self.backups.exists())
                self.assertEqual((self.app / 'plexport' / 'server.py').read_bytes(), b'old runtime')
                source.write_bytes(original)
        self.manifest()

    def test_older_installed_runtime_can_be_updated_and_rolled_back(self):
        # Legacy releases need not have the latest jobs renderer or all modules.
        (self.app / 'plexport' / 'static' / 'jobs.js').unlink()
        backup = self.update()
        self.assertTrue((self.app / 'plexport' / 'static' / 'jobs.js').is_file())
        update_nas.rollback(self.app, backup)
        self.assertFalse((self.app / 'plexport' / 'static' / 'jobs.js').exists())

    def test_missing_manifest_and_missing_database_are_rejected(self):
        (self.release / 'SHA256SUMS').unlink()
        with self.assertRaisesRegex(ValueError, 'needs SHA256SUMS'):
            self.update()
        self.manifest()
        self.database.unlink()
        with self.assertRaisesRegex(ValueError, 'Existing plexport.sqlite'):
            self.update()
        self.assertEqual((self.app / 'plexport' / 'server.py').read_bytes(), b'old runtime')
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_symlinks_in_release_installation_and_path_parents_are_rejected(self):
        link = self.release / 'plexport' / 'link.py'
        link.symlink_to(self.compose)
        with self.assertRaisesRegex(ValueError, 'link or special file'):
            self.update()
        link.unlink()
        (self.app / 'media-link').symlink_to(self.media)
        with self.assertRaisesRegex(ValueError, 'link or special file'):
            self.update()
        (self.app / 'media-link').unlink()
        alias = self.root / 'alias'
        alias.symlink_to(self.app.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlinks'):
            update_nas.update(alias / 'code', self.data, self.backups, self.release)

    def test_unsafe_backup_locations_and_public_backups_are_rejected(self):
        for location in (self.app / 'backups', self.data / 'backups', self.app.parent):
            with self.subTest(location=location):
                with self.assertRaisesRegex(ValueError, 'Backup directory'):
                    update_nas.update(self.app, self.data, location, self.release)
        self.backups.mkdir(mode=0o755)
        self.backups.chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'must be private'):
            self.update()
        with self.assertRaisesRegex(ValueError, 'filesystem root'):
            update_nas.update(Path('/'), self.data, self.backups, self.release)

    def test_archive_requires_external_checksum_and_extracts_verified_package(self):
        archive = self.root / 'release.tar.gz'
        with tarfile.open(archive, 'w:gz') as bundle:
            bundle.add(self.release, arcname='PlexPort-release')
        with self.assertRaisesRegex(ValueError, 'published --sha256'):
            self.update(archive)
        with self.assertRaisesRegex(ValueError, 'archive checksum mismatch'):
            self.update(archive, '0' * 64)
        self.update(archive, update_nas.digest(archive))
        self.assertEqual((self.app / 'plexport' / 'server.py').read_bytes(), b'new runtime')

    def test_archive_traversal_absolute_paths_and_links_are_rejected(self):
        for name, kind in (('../escape.py', tarfile.REGTYPE), ('/escape.py', tarfile.REGTYPE),
                           ('plexport/link.py', tarfile.SYMTYPE), ('plexport/hard.py', tarfile.LNKTYPE)):
            with self.subTest(name=name):
                archive = self.root / 'unsafe.tar.gz'
                with tarfile.open(archive, 'w:gz') as bundle:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = str(self.compose) if kind != tarfile.REGTYPE else ''
                    member.size = 1 if kind == tarfile.REGTYPE else 0
                    bundle.addfile(member, io.BytesIO(b'x') if member.size else None)
                with self.assertRaises(ValueError):
                    self.update(archive, update_nas.digest(archive))
        self.assertFalse((self.root / 'escape.py').exists())
        self.assertEqual((self.app / 'plexport' / 'server.py').read_bytes(), b'old runtime')

    def test_rollback_refuses_backup_for_another_installation(self):
        backup = self.update()
        manifest = backup / 'update.json'
        metadata = json.loads(manifest.read_text())
        metadata['app_dir'] = '/unrelated/application'
        manifest.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, 'different application'):
            update_nas.rollback(self.app, backup)


if __name__ == '__main__':
    unittest.main()
