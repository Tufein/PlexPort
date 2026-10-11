"""Connect this existing TrueNAS installation without replacing its credentials."""
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid

BASE = Path('/mnt/tank/media/Movies/.plexport-app')
DOWNLOADS = '/mnt/tank/media/Movies/.plexport-downloads'
URL = 'http://192.168.1.100:30024'


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise RuntimeError('Opdracht mislukt: ' + ' '.join(args[:4]))
    return r.stdout


def mounts(name):
    c = json.loads(run('docker', 'inspect', name))[0]
    assert c['Config']['User'] == '3000:3000', 'Onverwachte app-gebruiker'
    return {m['Destination']: m['Source'] for m in c['Mounts']}


def main():
    if os.geteuid() != 0:
        raise SystemExit('Voer dit uit als NAS-beheerder.')
    assert mounts('ix-qbittorrent-qbittorrent-1')['/downloads'] == DOWNLOADS
    assert mounts('ix-plexport-plexport-1')['/downloads'] == DOWNLOADS
    with urllib.request.urlopen(URL + '/api/v2/app/version', timeout=10) as r:
        version = r.read().decode()
    compose = json.loads(run('midclt', 'call', 'app.config', 'plexport'))
    updated = copy.deepcopy(compose)
    env = updated['services']['plexport']['environment']
    env.update({'DOWNLOADER_TYPE': 'qbittorrent', 'QBITTORRENT_URL': URL,
                'QBITTORRENT_USER': '', 'DOWNLOADER_ROOT': '/downloads'})
    backups = BASE / 'backups'
    backups.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backups, 0o700)
    backup = backups / ('connect-nas-qbit-' + time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(mode=0o700)
    compose_file = backup / 'compose-before.json'
    compose_file.write_text(json.dumps(compose))
    os.chmod(compose_file, 0o600)
    dbpath = BASE / 'data/plexport.sqlite'
    backup_ready = False
    try:
        run('midclt', 'call', '--job', 'app.stop', 'plexport')
        with sqlite3.connect(dbpath) as source, sqlite3.connect(backup / 'plexport.sqlite') as target:
            source.backup(target)
        backup_ready = True
        os.chmod(backup / 'plexport.sqlite', 0o600)
        sys.path.insert(0, str(BASE / 'code'))
        from plexport.core import Store
        store = Store(BASE / 'data')
        store.save_settings({'downloader': {'type': 'qbittorrent', 'url': URL,
                             'username': '', 'password': '', 'remote_root': '/downloads',
                             'local_root': '/downloads'}})
        run('midclt', 'call', '--job', 'app.update', 'plexport',
            json.dumps({'custom_compose_config': updated}))
        state = json.loads(run('midclt', 'call', 'app.get_instance', 'plexport'))['state']
        if state != 'RUNNING':
            run('midclt', 'call', '--job', 'app.start', 'plexport')
    except Exception:
        # Restore the known configuration and database before reporting failure.
        run('midclt', 'call', '--job', 'app.stop', 'plexport')
        if backup_ready:
            with sqlite3.connect(backup / 'plexport.sqlite') as source, sqlite3.connect(dbpath) as target:
                source.backup(target)
        run('midclt', 'call', '--job', 'app.update', 'plexport',
            json.dumps({'custom_compose_config': compose}))
        run('midclt', 'call', '--job', 'app.start', 'plexport')
        raise
    assert mounts('ix-plexport-plexport-1')['/downloads'] == DOWNLOADS
    # Check from the actual application process environment, as its own UID.
    check = '''import json, os, tempfile
from pathlib import Path
from plexport.core import Store
from plexport.integrations import client
c=Store('/data').settings()
paths=[c['downloader']['local_root'],c['library']['movies'],c['library']['tv']]
for p in paths:
    with tempfile.NamedTemporaryFile(prefix='.plexport-write-check-',dir=p): pass
print(json.dumps({'connection':client(c['downloader']).test(),'paths':paths,'uid':os.getuid(),'remote_root':c['downloader']['remote_root']}))
'''
    checked = json.loads(run('docker', 'exec', 'ix-plexport-plexport-1', 'python', '-c', check))
    marker = '.plexport-map-test-' + uuid.uuid4().hex
    try:
        run('docker', 'exec', 'ix-qbittorrent-qbittorrent-1', 'sh', '-c',
            'umask 077; printf shared-download-map > /downloads/' + marker)
        seen = run('docker', 'exec', 'ix-plexport-plexport-1', 'python', '-c',
                   "from pathlib import Path; print(Path('/downloads/" + marker + "').read_text())").strip()
        assert seen == 'shared-download-map'
    finally:
        (Path(DOWNLOADS) / marker).unlink(missing_ok=True)
    report = {'version': version, 'backup': str(backup), 'checks': checked,
              'same_download_folder': True, 'host_downloads': DOWNLOADS,
              'saved_url': store.settings()['downloader']['url']}
    p = BASE / 'code/nas-qbit-connection-result.json'
    p.write_text(json.dumps(report, indent=2))
    os.chmod(p, 0o644)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
