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

FILE = Path('/mnt/.ix-apps/app_configs/jellyport/metadata.yaml')
BACKUP = FILE.with_name('metadata.yaml.jellyport-before-icon')
ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#06b6d4"/></linearGradient></defs><rect width="64" height="64" rx="17" fill="url(#g)"/><path d="M25 17.5v21a2 2 0 0 0 3 1.7l17-10.5a2 2 0 0 0 0-3.4L28 15.8a2 2 0 0 0-3 1.7z" fill="#fff"/><path d="M16 48.5c9 5 23 5 32 0" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-dasharray="0.1 6.4" opacity=".9"/></svg>'


def atomic_write(raw, original):
    fd, name = tempfile.mkstemp(prefix='.jellyport-icon-', dir=FILE.parent)
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
        raise SystemExit('Geen verwachte JellyPort custom-appmetadata; niets gewijzigd.')
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
        apps = json.loads(subprocess.check_output(['midclt', 'call', 'app.query', '[["id","=","jellyport"]]'], text=True))
        if len(apps) != 1 or apps[0]['metadata'].get('icon') != body['metadata'].get('icon'):
            raise RuntimeError('De NAS heeft het icoon niet bevestigd.')
    except BaseException:
        atomic_write(raw, original)
        subprocess.run(['midclt', 'call', '--job', 'app.metadata.generate'], stdout=subprocess.DEVNULL, check=False)
        raise
    print('JellyPort-icoon hersteld.' if args.restore else 'JellyPort-icoon ingesteld; vernieuw de Apps-pagina.')
    print('Backup:', BACKUP)


if __name__ == '__main__':
    main()
