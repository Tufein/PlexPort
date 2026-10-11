"""Reversible custom-app icon workaround, verified against TrueNAS 25.10.7.

TrueNAS has no public custom-app icon API in this release. This changes only
metadata.icon; it does not touch Compose, volumes, credentials or downloads.
Run on the TrueNAS HOST, as root. --restore restores only the original icon.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

import yaml

FILE = Path('/mnt/.ix-apps/app_configs/plexport/metadata.yaml')
BACKUP = FILE.with_name('metadata.yaml.plexport-before-icon')
ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="17" fill="#f5b536"/><path d="M22 15h15l13 17-13 17H22l13-17z" fill="#252821"/></svg>'


def atomic_write(raw, original):
    fd, name = tempfile.mkstemp(prefix='.plexport-icon-', dir=FILE.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), stat.S_IMODE(original.st_mode))
            os.fchown(stream.fileno(), original.st_uid, original.st_gid)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, FILE)
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Voer dit op de TrueNAS-host uit als beheerder (sudo).')
    version = subprocess.check_output(['midclt', 'call', 'system.version'], text=True)
    if '25.10.7' not in version:
        raise SystemExit('Deze aanpassing is alleen gecontroleerd voor TrueNAS 25.10.7.')
    original = FILE.stat()
    raw = FILE.read_bytes()
    body = yaml.safe_load(raw)
    if not isinstance(body, dict) or not body.get('custom_app') or not isinstance(body.get('metadata'), dict):
        raise SystemExit('Geen verwachte PlexPort custom-appmetadata; niets gewijzigd.')
    if args.restore:
        old = yaml.safe_load(BACKUP.read_bytes())['metadata']
        if 'icon' in old:
            body['metadata']['icon'] = old['icon']
        else:
            body['metadata'].pop('icon', None)
    else:
        if not BACKUP.exists():
            with BACKUP.open('xb') as stream:
                os.fchmod(stream.fileno(), stat.S_IMODE(original.st_mode))
                os.fchown(stream.fileno(), original.st_uid, original.st_gid)
                stream.write(raw)
        body['metadata']['icon'] = 'data:image/svg+xml;base64,' + base64.b64encode(ICON.encode()).decode()
    atomic_write(yaml.safe_dump(body, sort_keys=False).encode(), original)
    try:
        subprocess.run(['midclt', 'call', '--job', 'app.metadata.generate'], check=True, stdout=subprocess.DEVNULL)
        apps = json.loads(subprocess.check_output(['midclt', 'call', 'app.query', '[["id","=","plexport"]]'], text=True))
        if len(apps) != 1 or apps[0]['metadata'].get('icon') != body['metadata'].get('icon'):
            raise RuntimeError('De NAS heeft het icoon niet bevestigd.')
    except BaseException:
        atomic_write(raw, original)
        subprocess.run(['midclt', 'call', '--job', 'app.metadata.generate'], stdout=subprocess.DEVNULL, check=False)
        raise
    print('PlexPort-icoon hersteld.' if args.restore else 'PlexPort-icoon ingesteld; vernieuw de Apps-pagina.')
    print('Backup:', BACKUP)


if __name__ == '__main__':
    main()
