"""Build a deterministic NAS source bundle from one committed Git revision."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


def git(*args):
    return subprocess.check_output(['git', *args])


def build(ref='HEAD', output='dist'):
    commit = git('rev-parse', '--verify', ref + '^{commit}').decode().strip()
    version_source = git('show', commit + ':plexport/__init__.py').decode()
    version = re.search(r"^__version__ = ['\"](\d+\.\d+\.\d+)['\"]$", version_source, re.M)
    if not version:
        raise ValueError('The revision must declare a semantic server version')
    version = version.group(1)
    records = []
    for entry in git('ls-tree', '-rz', commit).split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, sha = meta.decode().split()
        name = name.decode()
        path = PurePosixPath(name)
        if path.parts[0] == 'dist':
            continue  # Never recursively include previous release archives.
        forbidden = {'.signing', '.env', 'data', 'downloads', 'media', 'verification', '.venv', '__pycache__'}
        if forbidden.intersection(path.parts) or path.suffix in {'.sqlite', '.db', '.jks', '.keystore', '.pyc'}:
            raise ValueError('Private or generated path is tracked: ' + name)
        if kind != 'blob' or mode not in {'100644', '100755'}:
            raise ValueError('Only regular tracked files can enter a release: ' + name)
        records.append((name, git('cat-file', 'blob', sha), int(mode[-3:], 8)))
    manifest = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                       for name, data, _ in records).encode()
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ('PlexPort-' + version + '.tar.gz')
    with archive.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as bundle:
            for name, data, mode in records + [('SHA256SUMS', manifest, 0o644)]:
                member = tarfile.TarInfo('PlexPort-' + version + '/' + name)
                member.size, member.mode, member.mtime = len(data), mode, 0
                member.uid = member.gid = 0
                member.uname = member.gname = ''
                bundle.addfile(member, io.BytesIO(data))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + '.sha256').write_text(digest + '  ' + archive.name + '\n')
    print(str(archive))
    print(digest)
    print('Source revision: ' + commit + '; files: ' + str(len(records)))
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--output-dir', default='dist')
    args = parser.parse_args()
    build(args.ref, args.output_dir)
