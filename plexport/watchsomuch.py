"""WatchSoMuch's public RSS search and download pages; no account is needed."""
from html.parser import HTMLParser
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

from .integrations import request

BASE = 'https://watchsomuch.to'
_cache = {}
_lock = threading.Lock()


def download_ids(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in ('watchsomuch.to', 'www.watchsomuch.to')
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment):
        return None
    match = re.fullmatch(r'/Movie/(\d+)[^/]*/Download-(\d+)/[^/]+/?', parsed.path)
    return match.groups() if match else None


class Torrents(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.current = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'torrent' in attrs.get('class', '').split() and attrs.get('data-torrent', '').isdigit():
            url = urllib.parse.urljoin(BASE + '/', attrs.get('href', ''))
            ids = download_ids(url)
            if ids and ids[1] == attrs['data-torrent']:
                self.current = {'title': attrs.get('data-title', ''), 'link': url, 'size': '', 'seeders': ''}
                self.stack = []
        if self.current is not None and tag == 'div':
            classes = attrs.get('class', '').split()
            field = 'size' if 'size' in classes else 'seeders' if 'seed' in classes else None
            # The second seed column is peers, not seeders.
            if field == 'seeders' and self.current['seeders']:
                field = None
            self.stack.append(field)

    def handle_data(self, text):
        if self.current is not None and self.stack and self.stack[-1]:
            self.current[self.stack[-1]] += text

    def handle_endtag(self, tag):
        if self.current is not None:
            if tag == 'div' and self.stack:
                self.stack.pop()
            elif tag == 'a':
                if self.current['title']:
                    self.items.append(self.current)
                self.current = None
                self.stack = []


class Magnet(HTMLParser):
    def __init__(self):
        super().__init__()
        self.link = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('id') == 'txtMagnetLink':
            self.link = attrs.get('value', '')
        elif tag == 'a' and attrs.get('id') == 'btnDownloadMagnet' and not self.link:
            self.link = attrs.get('href', '')


def fetch(path):
    return request(BASE + path, headers={'User-Agent': 'PlexPort/1.0'}, timeout=8).decode('utf-8-sig')


def size_bytes(text):
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(B|KB|MB|GB|TB)\b', text, re.I)
    return int(float(match[1].replace(',', '.')) * 1024 ** ('B', 'KB', 'MB', 'GB', 'TB').index(match[2].upper())) if match else 0


def search(source, query, kind):
    # Bound requests to five title lists; resolve only the selected download later.
    key = (query.casefold(), kind)
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 300:
            return [dict(item, source=source['name']) for item in cached[1]]
    keyword = ('Movies ' if kind == 'movie' else 'TV ') + query
    try:
        root = ET.fromstring(fetch('/RSS/?' + urllib.parse.urlencode({'Search': keyword})))
    except ET.ParseError:
        raise ValueError('WatchSoMuch geeft geen geldige zoekfeed terug. De site is mogelijk tijdelijk niet bereikbaar.') from None
    if root.tag != 'rss':
        raise ValueError('WatchSoMuch geeft geen geldige zoekfeed terug.')
    results, seen, failures = [], set(), []
    titles = root.findall('./channel/item')[:5]
    for item in titles:
        parsed = urllib.parse.urlsplit(item.findtext('link', ''))
        if parsed.scheme != 'https' or parsed.hostname not in ('watchsomuch.to', 'www.watchsomuch.to'):
            continue
        match = re.match(r'^/Movie/(\d+)[^/]*/', parsed.path)
        if not match:
            continue
        mid = match[1]
        endpoint = 'ajMovieTorrents' if kind == 'movie' else 'ajTVTorrents'
        parser = Torrents()
        try:
            parser.feed(fetch('/Movies/' + endpoint + '.aspx?mid=' + mid))
        except Exception as error:
            failures.append(error)
            continue
        library_title = item.findtext('title', '')
        year_match = re.search(r'\((\d{4})\)\s*$', library_title)
        year = year_match[1] if year_match else ''
        if year_match:
            library_title = library_title[:year_match.start()].strip()
        for torrent in parser.items:
            if download_ids(torrent['link'])[0] != mid or torrent['link'] in seen:
                continue
            seen.add(torrent['link'])
            seeds = torrent['seeders'].strip().replace(',', '')
            episode = re.search(r'\bS(\d{1,3})E(\d{1,3})\b', torrent['title'], re.I) if kind == 'tv' else None
            results.append({**torrent, 'size': size_bytes(torrent['size']), 'seeders': int(seeds) if seeds.isdigit() else 0,
                            'source': source['name'], 'published': item.findtext('pubDate', ''),
                            'library_title': library_title, 'year': year,
                            'season': episode[1] if episode else '', 'episode': episode[2] if episode else ''})
    if failures and not results:
        raise ValueError('De downloadlijst van WatchSoMuch is tijdelijk niet bereikbaar. Probeer opnieuw.')
    results.sort(key=lambda item: item['seeders'], reverse=True)
    results = results[:250]
    with _lock:
        # Keep a small, short-lived in-memory cache, without search history on disk.
        if len(_cache) >= 32:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (time.monotonic(), results)
    return results


def resolve(url):
    ids = download_ids(url)
    if not ids:
        return url
    parser = Magnet()
    parser.feed(fetch('/Movies/ajTorrentDetails.aspx?' + urllib.parse.urlencode({'movie': ids[0], 'key': ids[1]})))
    link = parser.link.strip()
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)
    if (not link.startswith('magnet:?') or len(link) > 8192
            or not any(re.fullmatch(r'urn:btih:(?:[a-fA-F0-9]{40}|[A-Z2-7a-z]{32})', value) for value in params.get('xt', []))):
        raise ValueError('WatchSoMuch geeft voor deze download geen geldige magnetlink terug. Kies een andere variant of probeer later opnieuw.')
    return link
