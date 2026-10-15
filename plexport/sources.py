"""Bounded public YTS/EZTV search; fixed HTTPS APIs and no account credentials.

EZTV identifies shows by IMDb ID. TVmaze resolves a user-entered show name;
its fuzzy suggestions are filtered locally before contacting EZTV. TVmaze data
must be credited in the interface (https://www.tvmaze.com/api, CC BY-SA).
"""
import copy
from datetime import datetime, timezone
import json
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request


SOURCE_PRESETS = {
    'yts': {'name': 'YTS', 'url': 'https://yts.gg', 'kinds': ('movie',)},
    'eztv': {'name': 'EZTV', 'url': 'https://eztvx.to', 'kinds': ('tv',)},
}
YTS_API = 'https://movies-api.accel.li/api/v2/list_movies.json'
EZTV_API = 'https://eztvx.to/api/get-torrents'
TVMAZE_API = 'https://api.tvmaze.com/search/shows'
_HOSTS = frozenset(('movies-api.accel.li', 'eztvx.to', 'api.tvmaze.com'))
MAX_BYTES = 4 * 1024 * 1024
MAX_RESULTS = 250
MAX_SHOWS = 3
MAX_CACHE = 32
CACHE_TTL = 300
_cache = {}
_lock = threading.Lock()


def _allowed_url(url):
    parsed = urllib.parse.urlsplit(url)
    try:
        allowed = (parsed.scheme == 'https' and parsed.hostname in _HOSTS
                   and not parsed.username and not parsed.password
                   and parsed.port in (None, 443) and not parsed.fragment)
    except ValueError:
        allowed = False
    if not allowed:
        raise ValueError('De zoekbron verwijst naar een niet-toegestaan API-adres.')
    return url


class _OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _allowed_url(newurl)
        # An API must not redirect a query to another provider, even if both are known.
        if urllib.parse.urlsplit(newurl).hostname != urllib.parse.urlsplit(req.full_url).hostname:
            raise ValueError('De zoekbron verwijst naar een andere API-server.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_json(url):
    _allowed_url(url)
    request = urllib.request.Request(url, headers={'User-Agent': 'PlexPort/1.8 (public source search)', 'Accept': 'application/json'})
    opener = urllib.request.build_opener(_OfficialRedirects())
    with opener.open(request, timeout=8) as response:
        _allowed_url(response.geturl())
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError('De zoekbron geeft een te groot antwoord terug.')
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError('De zoekbron geeft geen geldig JSON-antwoord terug. Probeer later opnieuw.') from None


def supports(source, kind, mode='title'):
    source_type = source.get('type', 'torznab')
    if mode == 'actor':
        return source_type == 'watchsomuch'
    if mode != 'title' or kind not in ('movie', 'tv'):
        return False
    if source_type in SOURCE_PRESETS:
        return kind in SOURCE_PRESETS[source_type]['kinds']
    return source_type in ('watchsomuch', 'torznab')


def _text(value, maximum=300):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= maximum and not any(ord(char) < 32 for char in value) else ''


def _name(value):
    value = unicodedata.normalize('NFKD', value).casefold()
    return ' '.join(''.join(char if char.isalnum() else ' ' for char in value if not unicodedata.combining(char)).split())


def _compatible(title, query):
    title, query = _name(title), _name(query)
    # TVmaze deliberately returns fuzzy suggestions. Each literal query token must
    # occur in the actual show name; initials and fuzzy scores prove no identity.
    return bool(query) and (query in title or all(token in title for token in query.split()))


def _number(value, maximum=1024 ** 5):
    if type(value) is int:
        return value if 0 <= value <= maximum else 0
    if isinstance(value, str) and re.fullmatch(r'\d{1,16}', value):
        number = int(value)
        return number if number <= maximum else 0
    return 0


def _year(value):
    text = str(value) if type(value) is int else value
    return text if isinstance(text, str) and re.fullmatch(r'(18|19|20|21)\d{2}', text) else ''


def _magnet(info_hash, title, supplied=None):
    if not isinstance(info_hash, str) or not re.fullmatch(r'[a-fA-F0-9]{40}', info_hash):
        return ''
    if supplied is not None:
        if not isinstance(supplied, str) or len(supplied) > 8192:
            return ''
        try:
            parsed = urllib.parse.urlsplit(supplied)
            params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True, max_num_fields=40)
            if (parsed.scheme != 'magnet' or parsed.netloc or parsed.path or parsed.fragment
                    or set(params) - {'xt', 'dn', 'tr'}
                    or params.get('xt') != ['urn:btih:' + info_hash]
                    and [value.lower() for value in params.get('xt', [])] != ['urn:btih:' + info_hash.lower()]):
                return ''
            if any(not _text(value, 2048) for value in params.get('dn', [])):
                return ''
            for tracker in params.get('tr', []):
                target = urllib.parse.urlsplit(tracker)
                if (target.scheme not in ('http', 'https', 'udp') or not target.hostname
                        or target.username or target.password or target.fragment or target.port == 0):
                    return ''
        except ValueError:
            return ''
    # Keep only a checked infohash and our bounded display name. Provider-supplied
    # trackers, webseeds, source URLs and arbitrary magnet controls are not forwarded.
    return 'magnet:?' + urllib.parse.urlencode({'xt': 'urn:btih:' + info_hash.lower(), 'dn': title})


def _published(value):
    seconds = _number(value, maximum=7258118400)
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat() if seconds else ''


def _yts(query):
    data = fetch_json(YTS_API + '?' + urllib.parse.urlencode({'query_term': query, 'limit': 50, 'page': 1}))
    if not isinstance(data, dict) or data.get('status') != 'ok' or not isinstance(data.get('data'), dict):
        raise ValueError('YTS geeft geen geldige filmlijst terug. Probeer later opnieuw.')
    movies = data['data'].get('movies', [])
    count = data['data'].get('movie_count')
    if (not isinstance(movies, list)
            or count is not None and (type(count) is not int or count < 0)
            or 'movies' not in data['data'] and count != 0
            or type(count) is int and count > 0 and not movies):
        raise ValueError('YTS geeft geen geldige filmlijst terug.')
    result, seen = [], set()
    for movie in movies[:50]:
        if not isinstance(movie, dict):
            continue
        title = _text(movie.get('title'))
        torrents = movie.get('torrents', [])
        if not title or not _compatible(title, query) or not isinstance(torrents, list):
            continue
        year = _year(movie.get('year'))
        for torrent in torrents[:20]:
            if not isinstance(torrent, dict):
                continue
            quality = _text(torrent.get('quality'), 20)
            encoding = _text(torrent.get('type'), 30)
            release = title + (f' ({year})' if year else '') + (' ' + quality if quality else '') + (' ' + encoding if encoding else '') + ' [YTS]'
            link = _magnet(torrent.get('hash'), release)
            if not link or link in seen:
                continue
            seen.add(link)
            result.append({'title': release, 'library_title': title, 'year': year, 'kind': 'movie',
                           'link': link, 'size': _number(torrent.get('size_bytes')),
                           'seeders': _number(torrent.get('seeds'), 2 ** 31),
                           'published': _published(torrent.get('date_uploaded_unix')),
                           'season': '', 'episode': ''})
            if len(result) >= MAX_RESULTS:
                return result
    return result


def _episode(release, torrent):
    codes = list(re.finditer(r'(?i)(?:^|[^a-z0-9])S(\d{1,3})[ ._-]*E(\d{1,3})', release))
    if len(codes) == 1:
        match = codes[0]
        tail = release[match.end():]
        if not re.match(r'(?i)^(?:\d|[ ._-]*E\d|\s*[-+&]\s*E?\d|\s+(?:to|and)\s+E?\d)', tail):
            return str(int(match[1])), str(int(match[2]))
        return str(int(match[1])), ''
    if codes:
        seasons = {int(match[1]) for match in codes}
        return str(next(iter(seasons))) if len(seasons) == 1 else '', ''
    season, episode = torrent.get('season'), torrent.get('episode')
    valid = lambda value: type(value) is int and 0 <= value <= 999 or isinstance(value, str) and bool(re.fullmatch(r'\d{1,3}', value))
    season_code = re.search(r'(?i)(?:^|[^a-z0-9])S(\d{1,3})(?!\d)', release)
    if season_code:
        return str(int(season_code[1])), ''
    if re.search(r'(?i)\b(?:complete|pack)\b', release):
        return str(int(season)) if valid(season) else '', ''
    if valid(episode) and int(episode) == 0:
        return str(int(season)) if valid(season) else '', ''
    return (str(int(season)), str(int(episode))) if valid(season) and valid(episode) else ('', '')


def _eztv(query):
    # Users commonly include an episode code; the name lookup concerns the show.
    show_query = re.sub(r'(?i)\s+S\d{1,3}(?:E\d{1,3})?.*$', '', query).strip()
    if len(_name(show_query)) < 2:
        return []
    shows = fetch_json(TVMAZE_API + '?' + urllib.parse.urlencode({'q': show_query}))
    if not isinstance(shows, list):
        raise ValueError('TVmaze geeft geen geldige serienamen terug. Probeer later opnieuw.')
    compatible, seen_shows = [], set()
    for row in shows[:50]:
        show = row.get('show') if isinstance(row, dict) else None
        if not isinstance(show, dict):
            continue
        title = _text(show.get('name'))
        externals = show.get('externals')
        imdb = externals.get('imdb') if isinstance(externals, dict) else None
        if (not title or not _compatible(title, show_query) or not isinstance(imdb, str)
                or not re.fullmatch(r'tt\d{7,10}', imdb) or imdb in seen_shows):
            continue
        seen_shows.add(imdb)
        compatible.append((show, title, imdb[2:]))
        if len(compatible) == MAX_SHOWS:
            break
    result, seen = [], set()
    for show, title, imdb in compatible:
        data = fetch_json(EZTV_API + '?' + urllib.parse.urlencode({'imdb_id': imdb, 'limit': 100, 'page': 1}))
        count = data.get('torrents_count') if isinstance(data, dict) else None
        if (not isinstance(data, dict) or str(data.get('imdb_id')) != imdb
                or type(count) is not int or count < 0
                or not isinstance(data.get('torrents', []), list)
                or count > 0 and not data.get('torrents')
                or count == 0 and data.get('torrents')):
            raise ValueError('EZTV geeft geen geldige afleveringenlijst terug. Probeer later opnieuw.')
        premiered = show.get('premiered')
        year = _year(premiered[:4]) if isinstance(premiered, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', premiered) else ''
        show_id = show.get('id')
        metadata_url = 'https://www.tvmaze.com/shows/' + str(show_id) if type(show_id) is int and show_id > 0 else 'https://www.tvmaze.com'
        for torrent in data.get('torrents', [])[:100]:
            if not isinstance(torrent, dict) or str(torrent.get('imdb_id')) != imdb:
                continue
            release = _text(torrent.get('title'), 1024)
            if not release:
                continue
            link = _magnet(torrent.get('hash'), release, torrent.get('magnet_url'))
            if not link or link in seen:
                continue
            seen.add(link)
            season, episode = _episode(release, torrent)
            result.append({'title': release, 'library_title': title, 'year': year, 'kind': 'tv',
                           'link': link, 'size': _number(torrent.get('size_bytes')),
                           'seeders': _number(torrent.get('seeds'), 2 ** 31),
                           'published': _published(torrent.get('date_released_unix', torrent.get('date_released'))),
                           'season': season, 'episode': episode,
                           'metadata_source': 'TVmaze', 'metadata_url': metadata_url})
            if len(result) >= MAX_RESULTS:
                return result
    return result


def search(source, query, kind, mode='title'):
    if source.get('type') not in SOURCE_PRESETS or not supports(source, kind, mode):
        return []
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200 or len(_name(query)) < 2:
        raise ValueError('Gebruik een zoekopdracht van 2 tot 200 tekens.')
    query = query.strip()
    key = (source['type'], query.casefold(), kind)
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_TTL:
            return [dict(copy.deepcopy(item), source=source['name']) for item in cached[1]]
    results = _yts(query) if source['type'] == 'yts' else _eztv(query)
    results.sort(key=lambda item: item['seeders'], reverse=True)
    with _lock:
        if key not in _cache and len(_cache) >= MAX_CACHE:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (time.monotonic(), copy.deepcopy(results[:MAX_RESULTS]))
    return [dict(item, source=source['name']) for item in results[:MAX_RESULTS]]
