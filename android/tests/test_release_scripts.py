"""Release guards must preserve the published APK and require the original key."""
from pathlib import Path
import contextlib
import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
import unittest


ANDROID = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('publish_apk', ANDROID / 'publish_apk.py')
PUBLISH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLISH)


class SigningSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copyfile(ANDROID / 'prepare_signing.py', self.root / 'prepare_signing.py')

    def run_setup(self):
        return subprocess.run([sys.executable, str(self.root / 'prepare_signing.py')],
                              capture_output=True, text=True)

    def test_missing_key_requires_restoring_backup_without_creating_files(self):
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('bestaande releasesleutel ontbreekt', result.stderr)
        self.assertFalse((self.root / '.signing').exists())

    def test_partial_backup_is_never_replaced(self):
        private = self.root / '.signing'
        private.mkdir()
        key = private / 'plexport-release.jks'
        key.write_bytes(b'fixture existing key')
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('onvolledig', result.stderr)
        self.assertEqual(key.read_bytes(), b'fixture existing key')
        self.assertFalse((private / 'signing.properties').exists())

    def test_existing_backup_is_reused_without_reading_or_changing_it(self):
        private = self.root / '.signing'
        private.mkdir()
        (private / 'plexport-release.jks').write_bytes(b'fixture existing key')
        (private / 'signing.properties').write_text('fixture existing settings')
        before = {path.name: path.read_bytes() for path in private.iterdir()}
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {path.name: path.read_bytes() for path in private.iterdir()})
        self.assertEqual(result.stdout, '')


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'app/build/outputs/apk/release').mkdir(parents=True)
        (self.root / 'app/build.gradle').write_text("versionName '1.3.0'\n")
        (self.root / 'dist').mkdir()
        self.previous = self.root / 'dist/PlexPort-1.2.0.apk'
        self.previous.write_text('a' * 64)
        self.built = self.root / 'app/build/outputs/apk/release/app-release.apk'
        self.built.write_text('a' * 64)
        self.apksigner = self.root / 'fixture-apksigner'
        self.apksigner.write_text(
            '#!' + sys.executable + '\n'
            'import pathlib, sys\n'
            'digest = pathlib.Path(sys.argv[-1]).read_text()\n'
            'if digest == "unsigned": sys.exit(1)\n'
            'print("Signer #1 certificate SHA-256 digest: " + digest)\n')
        self.apksigner.chmod(0o755)

    def publish(self, personal=False):
        with contextlib.redirect_stdout(io.StringIO()):
            return PUBLISH.publish(self.root, self.apksigner, personal)

    def test_matching_certificate_publishes_apk_and_checksum(self):
        target = self.publish()
        self.assertEqual(target.read_bytes(), self.built.read_bytes())
        self.assertIn('  PlexPort-1.3.0.apk\n', target.with_suffix('.apk.sha256').read_text())
        self.assertEqual(self.previous.read_text(), 'a' * 64)

    def test_different_certificate_cannot_replace_existing_distribution(self):
        target = self.root / 'dist/PlexPort-1.3.0.apk'
        target.write_text('a' * 64)
        self.built.write_text('b' * 64)
        with self.assertRaisesRegex(SystemExit, 'wijkt af'):
            self.publish()
        self.assertEqual(target.read_text(), 'a' * 64)
        self.assertFalse(target.with_suffix('.apk.sha256').exists())

    def test_unsigned_apk_is_never_published(self):
        self.built.write_text('unsigned')
        with self.assertRaises(subprocess.CalledProcessError):
            self.publish()
        self.assertFalse((self.root / 'dist/PlexPort-1.3.0.apk').exists())

    def test_missing_previous_apk_prevents_unverified_upgrade(self):
        self.previous.unlink()
        with self.assertRaisesRegex(SystemExit, 'gepubliceerde APK ontbreekt'):
            self.publish()
        self.assertFalse((self.root / 'dist/PlexPort-1.3.0.apk').exists())

    def test_personal_build_remains_separate_from_published_apks(self):
        self.built.write_text('b' * 64)
        target = self.publish(personal=True)
        self.assertEqual(target, self.root / 'dist/personal/PlexPort-1.3.0.apk')
        self.assertEqual(self.previous.read_text(), 'a' * 64)
        self.assertFalse((self.root / 'dist/PlexPort-1.3.0.apk').exists())


if __name__ == '__main__':
    unittest.main()
