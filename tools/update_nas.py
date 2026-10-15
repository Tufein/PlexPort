"""Replace only PlexPort's runtime after its service has been stopped.

Use a published release checksum. This helper never controls services, changes
Compose/settings, restores the database, or touches torrents and media.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import tarfile
import tempfile
import uuid


REQUIRED = ('__main__.py', 'core.py', 'server.py', 'static/index.html', 'static/app.js')
RELEASE_REQUIRED = (
    '__init__.py', '__main__.py', 'core.py', 'server.py', 'integrations.py',
    'watchsomuch.py', 'sources.py', 'posters.py', 'search.py', 'duplicates.py', 'storage.py', 'selection.py', 'static/index.html',
    'static/login.html', 'static/app.js', 'static/login.js', 'static/theme.js',
    'static/artwork.js', 'static/discovery.js', 'static/jobs.js', 'static/selection.js',
    'static/style.css', 'static/favicon.svg',
)


def checked_path(value):
    """Reject symlinks, including a symlink in a parent directory."""
    path = Path(os.path.abspath(value))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f'Symlinks are not supported: {part}')
    if path == Path(path.anchor):
        raise ValueError('A filesystem root is not an application path')
    return path


def check_tree(path):
    if not path.is_dir():
        raise ValueError(f'Not a directory: {path}')
    for item in (path, *path.rglob('*')):
        mode = item.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError(f'Unsupported link or special file: {item}')


def relative_name(value):
    path = PurePosixPath(value)
    if not value or '\\' in value or path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe release path')
    if str(path) in ('', '.'):
        raise ValueError('Empty release path')
    return path


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def verify_manifest(root):
    manifest = root / 'SHA256SUMS'
    if not manifest.is_file():
        raise ValueError('Release directory needs SHA256SUMS')
    if manifest.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Release manifest is too large')
    records = {}
    for line in manifest.read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-fA-F]{64}) [ *](.+)', line)
        if not match:
            raise ValueError('Invalid SHA256SUMS entry')
        name = str(relative_name(match[2]))
        if name in records:
            raise ValueError('Duplicate SHA256SUMS entry')
        path = root / name
        if not path.is_file() or digest(path) != match[1].lower():
            raise ValueError(f'Release checksum mismatch: {name}')
        records[name] = match[1].lower()
    runtime_files = {str(path.relative_to(root)) for path in (root / 'plexport').rglob('*') if path.is_file()}
    if not runtime_files or not runtime_files.issubset(records):
        raise ValueError('SHA256SUMS must cover every runtime file')


def extract_release(archive, destination):
    """Do not rely on tar extraction defaults on older NAS Python versions."""
    with tarfile.open(archive, 'r:*') as bundle:
        total = 0
        names = set()
        for member in bundle:
            name = relative_name(member.name)
            if str(name) in names or not (member.isfile() or member.isdir()):
                raise ValueError('Release archive contains duplicate paths or links/special files')
            names.add(str(name))
            total += member.size
            if total > 512 * 1024 * 1024 or len(names) > 10000:
                raise ValueError('Release archive exceeds application size limits')
            target = destination / str(name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                target.chmod(0o755)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = bundle.extractfile(member)
                if stream is None:
                    raise ValueError('Unreadable release member')
                with stream, target.open('xb') as output:
                    shutil.copyfileobj(stream, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)


def release_root(source):
    if (source / 'plexport').is_dir():
        return source
    children = list(source.iterdir())
    if len(children) == 1 and children[0].is_dir() and (children[0] / 'plexport').is_dir():
        return children[0]
    raise ValueError('Release must contain a plexport directory')


def set_metadata(destination, reference):
    desired = reference.stat()
    actual = destination.stat()
    if (actual.st_uid, actual.st_gid) != (desired.st_uid, desired.st_gid):
        os.chown(destination, desired.st_uid, desired.st_gid)
    shutil.copystat(reference, destination)


def copy_preserving(source, destination):
    shutil.copytree(source, destination)
    for item in (source, *source.rglob('*')):
        set_metadata(destination / item.relative_to(source), item)


def prepare_runtime(source, installed, stage):
    shutil.copytree(source, stage)
    owner = installed.stat()
    for item in (stage, *stage.rglob('*')):
        old = installed / item.relative_to(stage)
        if old.exists():
            if old.is_dir() != item.is_dir():
                raise ValueError('Release changes a file into a directory or vice versa')
            set_metadata(item, old)
        else:
            actual = item.stat()
            if (actual.st_uid, actual.st_gid) != (owner.st_uid, owner.st_gid):
                os.chown(item, owner.st_uid, owner.st_gid)
            # Git checkouts can be mode 0600; new runtime files must be readable.
            item.chmod(0o755 if item.is_dir() else 0o644)


def replace_runtime(app, staged, work):
    previous = work / 'previous'
    os.replace(app / 'plexport', previous)
    try:
        os.replace(staged, app / 'plexport')
    except BaseException:
        os.replace(previous, app / 'plexport')
        raise


def backup_installation(app, data, backup):
    database = data / 'plexport.sqlite'
    if not database.is_file():
        raise ValueError('Existing plexport.sqlite is required; confirm the data directory')
    backup.mkdir(mode=0o700)
    try:
        copy_preserving(app, backup / 'code')
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(backup / 'plexport.sqlite') as target:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('SQLite backup failed its integrity check')
        (backup / 'plexport.sqlite').chmod(0o600)
        (backup / 'update.json').write_text(json.dumps({'app_dir': str(app), 'data_dir': str(data)}, indent=2))
        (backup / 'update.json').chmod(0o600)
    except BaseException:
        shutil.rmtree(backup)
        raise


def validate_installation(app, data, backups):
    app, data, backups = map(checked_path, (app, data, backups))
    check_tree(app)
    check_tree(data)
    if not all((app / 'plexport' / name).is_file() for name in REQUIRED):
        raise ValueError('Application directory does not contain an installed PlexPort runtime')
    if app == data or app.is_relative_to(data):
        raise ValueError('Application code must not be the data directory or lie inside it')
    if backups == app or backups.is_relative_to(app) or backups == data or backups.is_relative_to(data):
        raise ValueError('Backup directory must be outside application code and data')
    if app.is_relative_to(backups) or data.is_relative_to(backups):
        raise ValueError('Backup directory must not contain the application or data')
    if data.is_relative_to(app / 'plexport'):
        raise ValueError('Application data must not be inside the replaceable runtime')
    return app, data, backups


def update(app_dir, data_dir, backup_dir, source_path, expected_sha256=None):
    app, data, backups = validate_installation(app_dir, data_dir, backup_dir)
    source = checked_path(source_path)
    if source == app or source.is_relative_to(app):
        raise ValueError('Release source must be outside the current installation')
    if source.is_dir():
        check_tree(source)
    elif not source.is_file():
        raise ValueError('Release source does not exist')
    with tempfile.TemporaryDirectory(prefix='plexport-release-') as extracted:
        if source.is_file():
            if not expected_sha256 or not re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha256):
                raise ValueError('An archive requires its published --sha256 checksum')
            if digest(source) != expected_sha256.lower():
                raise ValueError('Release archive checksum mismatch')
            extract_release(source, Path(extracted))
            root = release_root(Path(extracted))
        else:
            root = release_root(source)
        check_tree(root)
        verify_manifest(root)
        if not all((root / 'plexport' / name).is_file() for name in RELEASE_REQUIRED):
            raise ValueError('Release runtime is incomplete')
        backups.mkdir(mode=0o700, parents=True, exist_ok=True)
        if backups.stat().st_mode & 0o077:
            raise ValueError('Backup directory must be private (chmod 700)')
        backup = backups / ('plexport-update-' + uuid.uuid4().hex)
        backup_installation(app, data, backup)
        with tempfile.TemporaryDirectory(prefix='.plexport-update-', dir=app) as temporary:
            work = Path(temporary)
            prepare_runtime(root / 'plexport', app / 'plexport', work / 'next')
            replace_runtime(app, work / 'next', work)
        return backup


def rollback(app_dir, backup_path):
    app, backup = map(checked_path, (app_dir, backup_path))
    check_tree(app)
    check_tree(backup)
    metadata = json.loads((backup / 'update.json').read_text())
    if metadata.get('app_dir') != str(app):
        raise ValueError('Backup belongs to a different application directory')
    old = backup / 'code' / 'plexport'
    if not all((old / name).is_file() for name in REQUIRED):
        raise ValueError('Backup runtime is incomplete')
    with tempfile.TemporaryDirectory(prefix='.plexport-rollback-', dir=app) as temporary:
        work = Path(temporary)
        copy_preserving(old, work / 'next')
        replace_runtime(app, work / 'next', work)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-dir', required=True, type=Path)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--rollback', type=Path, help='Restore runtime code only; never restore an old database')
    parser.add_argument('--service-stopped', action='store_true', help='Confirm that only PlexPort has been stopped')
    args = parser.parse_args()
    if not args.service_stopped:
        parser.error('Stop the discovered PlexPort service and pass --service-stopped')
    try:
        if args.rollback:
            if args.source or args.data_dir or args.backup_dir or args.sha256:
                parser.error('--rollback cannot be combined with update options')
            rollback(args.app_dir, args.rollback)
            print('Previous runtime restored. Database, settings, media and downloads are unchanged.')
        else:
            if not (args.data_dir and args.backup_dir and args.source):
                parser.error('An update requires --data-dir, --backup-dir and --source')
            backup = update(args.app_dir, args.data_dir, args.backup_dir, args.source, args.sha256)
            print(f'Runtime updated. Private backup: {backup}')
        print('Start only PlexPort, then verify the version, saved tasks and connections.')
    except (OSError, ValueError, sqlite3.Error, tarfile.TarError) as error:
        parser.exit(1, f'Update failed: {error}\n')


if __name__ == '__main__':
    main()
