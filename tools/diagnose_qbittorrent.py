"""Read-only qBittorrent startup diagnostics for the TrueNAS host.

Prints selected configuration, container state, directory ownership and redacted
logs. Does not change configuration, permissions, containers or download files.
"""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess


SENSITIVE = re.compile(r'pass(?:word|wd|phrase)?|token|credential|api[_ -]?key|private[_ -]?key|secret|auth(?:entication|orization)?|cookie|session|username|login|bearer|https?://[^\s/@]+:[^\s/@]+@', re.I)
MEDIA_PATH = re.compile(r'(?:/downloads|/media|/Volumes)/[^\s\"\']+')
QUOTED_MEDIA = re.compile(r'([\"\'])[^\"\']*\.(?:mkv|mp4|avi|mov|m4v|srt|ass|torrent)\1', re.I)
MEDIA_FILE = re.compile(r'\S+\.(?:mkv|mp4|avi|mov|m4v|srt|ass|torrent)\b', re.I)
OPAQUE_VALUE = re.compile(r'(?<![\w/])[A-Za-z0-9_+/-]{32,}={0,2}(?![\w/])')
SAFE_STORAGE_KEYS = {'type', 'host_path', 'path', 'mount_path', 'mountPath', 'dataset_name',
                     'ix_volume_config', 'create_host_path', 'read_only', 'enable_acl',
                     'config', 'downloads', 'additional_storage', 'permissions', 'mode',
                     'uid', 'gid', 'user', 'group'}


def redact_log(raw, limit=45):
    lines = []
    skip = 0
    for line in str(raw).replace('\\n', '\n').splitlines():
        if SENSITIVE.search(line):
            lines.append('[regel met aanmeldgegevens verwijderd]')
            # Also cover credentials printed on a following line.
            skip = 2
            continue
        if skip:
            skip -= 1
            continue
        if re.search(r'\btorrent\b', line, re.I):
            lines.append('[regel met torrentgegevens verwijderd]')
            continue
        if re.search(r'\.(?:mkv|mp4|avi|mov|m4v|srt|ass|torrent)\b', line, re.I):
            lines.append('[regel met bestandsgegevens verwijderd]')
            continue
        line = MEDIA_PATH.sub('[bestandspad verwijderd]', line)
        line = QUOTED_MEDIA.sub('[bestandsnaam verwijderd]', line)
        line = MEDIA_FILE.sub('[bestandsnaam verwijderd]', line)
        line = OPAQUE_VALUE.sub('[lange waarde verwijderd]', line)
        lines.append(line[:500])
    return '\n'.join(lines[-limit:])


def capture(command, timeout=25):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, {'error': type(error).__name__}
    if result.returncode:
        return None, {'exit_code': result.returncode, 'error': redact_log(result.stderr, 5)}
    return result.stdout, None


def query_json(command):
    raw, error = capture(command)
    if error:
        return None, error
    try:
        return json.loads(raw), None
    except (TypeError, ValueError):
        return None, {'error': 'Ongeldig JSON-antwoord; inhoud niet weergegeven.'}


def safe_storage(value):
    if isinstance(value, dict):
        return {key: safe_storage(item) for key, item in value.items()
                if key in SAFE_STORAGE_KEYS and not SENSITIVE.search(key)}
    if isinstance(value, list):
        return [safe_storage(item) for item in value[:12]]
    if isinstance(value, (bool, int)) or value is None:
        return value
    if isinstance(value, str) and not SENSITIVE.search(value):
        return value[:300]
    return '[niet weergegeven]'


def selected_config(config):
    result = {}
    if not isinstance(config, dict):
        return result
    for key in ('run_as', 'storage'):
        if key in config:
            result[key] = safe_storage(config[key])
    if not result:
        for key in ('values', 'config'):
            if isinstance(config.get(key), dict):
                result = selected_config(config[key])
                if result:
                    break
    return result


def directory_info(path):
    result = {'path': path}
    try:
        info = os.stat(path)
        result.update(uid=info.st_uid, gid=info.st_gid, mode=oct(stat.S_IMODE(info.st_mode)),
                      directory=stat.S_ISDIR(info.st_mode))
    except OSError as error:
        result.update(error=type(error).__name__, errno=error.errno)
    return result


def lifecycle_tail():
    path = Path('/var/log/app_lifecycle.log')
    try:
        # Read only the trailing 2 MiB rather than an unbounded historical log.
        with path.open('rb') as stream:
            stream.seek(0, os.SEEK_END)
            length = stream.tell()
            stream.seek(max(0, length - 2 * 1024 * 1024))
            raw = stream.read().decode(errors='replace')
    except OSError as error:
        return {'error': type(error).__name__}
    entries = [line for line in raw.splitlines() if re.search(r"action for ['\"]qbittorrent['\"]", line)]
    return redact_log('\n'.join(entries[-3:]), 55)


def diagnose():
    report = {'read_only': True}
    config, error = query_json(['midclt', 'call', 'app.config', 'qbittorrent'])
    report['configuration'] = error or selected_config(config)
    apps, error = query_json(['midclt', 'call', 'app.query', '[["id","=","qbittorrent"]]'])
    report['app'] = error or [{'id': app.get('id'), 'state': app.get('state')}
                             for app in apps or []]
    raw, error = capture(['docker', 'ps', '-a', '--filter', 'name=ix-qbittorrent-', '--format', '{{.ID}}\t{{.Names}}'])
    containers = []
    paths = set()
    if error:
        report['containers_error'] = error
    else:
        for line in raw.splitlines()[:8]:
            parts = line.split('\t', 1)
            if len(parts) != 2 or not parts[1].startswith('ix-qbittorrent-'):
                continue
            container_id, name = parts
            info, error = query_json(['docker', 'inspect', container_id])
            if error or not info:
                containers.append({'name': name, 'error': error or 'Geen inspectiegegevens'})
                continue
            info = info[0]
            state = info.get('State', {})
            entry = {'name': name, 'state': {key: state.get(key) for key in
                     ('Status', 'ExitCode', 'OOMKilled', 'StartedAt', 'FinishedAt')}}
            entry['state']['Error'] = redact_log(state.get('Error', ''), 3)
            entry['mounts'] = []
            for mount in info.get('Mounts', []):
                if mount.get('Destination', '').rstrip('/') not in ('/config', '/downloads'):
                    continue
                source = mount.get('Source', '')
                entry['mounts'].append({'type': mount.get('Type'), 'source': source,
                                        'destination': mount.get('Destination'), 'writable': mount.get('RW')})
                if source.startswith('/mnt/'):
                    paths.update(str(path) for path in (Path(source), Path(source).parent, Path(source).parent.parent))
            try:
                logs = subprocess.run(['docker', 'logs', '--tail', '65', container_id], capture_output=True,
                                      text=True, timeout=15, check=False)
                entry['logs'] = redact_log(logs.stdout + logs.stderr, 40)
            except (OSError, subprocess.TimeoutExpired) as error:
                entry['logs'] = {'error': type(error).__name__}
            containers.append(entry)
    report['containers'] = containers
    report['directories'] = [directory_info(path) for path in sorted(paths)]
    report['recent_start_errors'] = lifecycle_tail()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'text'), default='json')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Voer deze alleen-lezen controle uit in de TrueNAS-hostshell met sudo.')
    report = diagnose()
    if args.format == 'json':
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for key, value in report.items():
            print(key + ':')
            print(json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value)


if __name__ == '__main__':
    main()
