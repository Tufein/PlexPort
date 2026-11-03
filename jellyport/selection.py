"""Validated torrent file identities and explicit episode selections.

Indices always come from the downloader's current metadata, never from filenames.
This module intentionally performs no network or filesystem operations.
"""
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
import re

VIDEO = {'.mkv', '.mp4', '.m4v', '.avi', '.mov', '.ts', '.webm', '.mpg', '.mpeg'}
SUBTITLE = {'.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx'}


def identities(files):
    if not isinstance(files, list) or not files or len(files) > 20000:
        raise ValueError('Bestandsmetadata ontbreekt of is te groot. Wacht even en probeer opnieuw.')
    result, seen = [], set()
    for item in files:
        index, name, size = item.get('index'), item.get('name'), item.get('size')
        if type(index) is not int or index < 0 or index in seen:
            raise ValueError('Ongeldige bestandsindices ontvangen van de downloader.')
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('Ongeldige bestandsnaam ontvangen van de downloader.')
        path = PurePosixPath(name.replace('\\', '/'))
        if path.is_absolute() or '..' in path.parts or PureWindowsPath(name).drive:
            raise ValueError('Onveilig bestandspad in torrent.')
        if type(size) is not int or size < 0:
            raise ValueError('Ongeldige bestandsgrootte ontvangen van de downloader.')
        seen.add(index)
        result.append({'index': index, 'name': name, 'size': size})
    return sorted(result, key=lambda item: item['index'])


def metadata_token(torrent_id, files):
    value = json.dumps([torrent_id.lower(), identities(files)], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(value.encode()).hexdigest()


def episode_info(name):
    stem = PurePosixPath(name.replace('\\', '/')).stem
    match = re.search(r'(?i)S(\d{1,3})[ ._-]*E(\d{1,3})((?:[ ._-]*E\d{1,3})*)', stem)
    if not match:
        return None, []
    return int(match[1]), [int(match[2]), *[int(number) for number in re.findall(r'(?i)E(\d{1,3})', match[3])]]


def describe_files(files, selected=()):
    clean = identities(files)
    actual = {item['index']: item for item in files}
    result = []
    for item in clean:
        path = PurePosixPath(item['name'].replace('\\', '/'))
        kind = 'video' if path.suffix.lower() in VIDEO else 'subtitle' if path.suffix.lower() in SUBTITLE else 'other'
        season, episodes = episode_info(item['name'])
        sample = bool(re.search(r'(?i)(?:^|[ ._\-/])sample(?:[ ._\-/]|$)', item['name']))
        extra = bool(re.search(r'(?i)(?:^|[ ._\-/])(?:extras?|featurettes?|trailers?)(?:[ ._\-/]|$)', item['name']))
        reason = ('sample' if sample else 'extra' if extra else 'multiple_episodes' if len(episodes) > 1
                  else 'episode' if episodes else 'ambiguous' if kind == 'video' else kind)
        progress = actual[item['index']].get('progress', 0)
        if type(progress) not in (int, float) or not 0 <= progress <= 1:
            progress = 0
        result.append({**item, 'kind': kind, 'season': season, 'episodes': episodes,
                       'selectable': kind in ('video', 'subtitle') and not sample,
                       'reason': reason, 'progress': progress, 'selected': item['index'] in selected})
    return result


def validate_selection(files, indices, job):
    if not isinstance(indices, list) or not indices or any(type(index) is not int for index in indices):
        raise ValueError('Kies minimaal één ondersteunde video.')
    if len(set(indices)) != len(indices):
        raise ValueError('Een bestand is meerdere keren geselecteerd.')
    described = {item['index']: item for item in describe_files(files)}
    if any(index not in described or not described[index]['selectable'] for index in indices):
        raise ValueError('Een gekozen bestand ontbreekt of wordt niet ondersteund. Vernieuw de bestandslijst.')
    chosen = [described[index] for index in sorted(indices)]
    videos = [item for item in chosen if item['kind'] == 'video']
    if not videos:
        raise ValueError('Kies minimaal één ondersteunde video; alleen ondertitels is niet voldoende.')
    for item in videos:
        if not item['episodes'] and not (len(videos) == 1 and job.get('season') is not None and job.get('episode') is not None):
            raise ValueError('Afleveringsnummer ontbreekt in ' + item['name'] + '. Kies een herkenbare S01E01-video of vul één seizoen en aflevering in bij het toevoegen.')
    for subtitle in (item for item in chosen if item['kind'] == 'subtitle'):
        sub = PurePosixPath(subtitle['name'].replace('\\', '/'))
        matched = False
        for video in videos:
            vid = PurePosixPath(video['name'].replace('\\', '/'))
            # Exact video stem plus a bounded language/forced suffix in the same folder.
            suffix = sub.stem[len(vid.stem):] if sub.stem.startswith(vid.stem) else None
            if sub.parent == vid.parent and suffix is not None and re.fullmatch(r'(?i)(?:\.[a-z]{2,3})?(?:\.forced|\.sdh)?', suffix):
                matched = True
        if not matched:
            raise ValueError('Ondertitel hoort niet eenduidig bij een gekozen video: ' + subtitle['name'])
    return chosen


def selected_complete(files, indices):
    selected = {item['index']: item for item in files if item.get('index') in indices}
    return len(selected) == len(indices) and all(item.get('progress') == 1 for item in selected.values())
