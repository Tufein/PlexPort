"""Repair only the existing TrueNAS qBittorrent config after a UID change."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import urllib.request


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError('Opdracht mislukt: ' + ' '.join(args[:4]))
    return result.stdout


def main():
    if os.geteuid() != 0:
        raise SystemExit('Voer dit uit als NAS-beheerder.')
    container = json.loads(run('docker', 'inspect', 'ix-qbittorrent-qbittorrent-1'))[0]
    assert container['Config']['Labels']['com.docker.compose.project'] == 'ix-qbittorrent'
    assert container['Config']['User'] == '3000:3000'
    mounts = {m['Destination']: m for m in container['Mounts']}
    config = Path(mounts['/config']['Source']).resolve()
    allowed = Path('/mnt/.ix-apps/app_mounts/qbittorrent').resolve()
    assert config.is_relative_to(allowed) and config != allowed and config.is_dir()
    assert mounts['/downloads']['Source'] == '/mnt/tank/media/Movies/.plexport-downloads'
    run('midclt', 'call', '--job', 'app.stop', 'qbittorrent')
    backups = Path('/mnt/tank/media/Movies/.plexport-app/backups')
    backups.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backups, 0o700)
    backup = backups / ('qbittorrent-owner-' + time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(mode=0o700)
    manifest = []
    nodes = [config] + list(config.rglob('*'))
    for node in nodes:
        s = node.lstat()
        manifest.append({'path': str(node.relative_to(config)), 'uid': s.st_uid,
                         'gid': s.st_gid, 'mode': stat.S_IMODE(s.st_mode)})
    (backup / 'ownership.json').write_text(json.dumps(manifest))
    shutil.copytree(config, backup / 'config', symlinks=True)
    for node in nodes:
        os.chown(node, 3000, 3000, follow_symlinks=False)
    run('midclt', 'call', '--job', 'app.start', 'qbittorrent')
    report = {'backup': str(backup), 'config': str(config), 'nodes_repaired': len(nodes)}
    for _ in range(45):
        try:
            with urllib.request.urlopen('http://127.0.0.1:30024/api/v2/app/version', timeout=2) as r:
                report['version'] = r.read().decode()
            break
        except Exception:
            time.sleep(1)
    else:
        report['error'] = 'qBittorrent antwoordt nog niet; lees de containerlogs.'
    target = Path('/mnt/tank/media/Movies/.plexport-app/code/qbittorrent-repair-result.json')
    target.write_text(json.dumps(report, indent=2))
    os.chmod(target, 0o644)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
