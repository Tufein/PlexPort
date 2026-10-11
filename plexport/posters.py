"""Optional, exact-match poster lookup with bounded, server-local image caching."""
from collections import OrderedDict
import hashlib
from html.parser import HTMLParser
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


BASE = 'https://watchsomuch.to'
FEED_LIMIT = 512 * 1024
IMAGE_LIMIT = 512 * 1024
IMAGE_CACHE_LIMIT = 10 * 1024 * 1024
METADATA_LIMIT = 256
IMAGE_COUNT_LIMIT = 128


def normalized_title(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def catalog_id(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != 'watchsomuch.to'
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment):
            return None
        match = re.fullmatch(r'/Movie/(\d{1,12})[^/]*/[^/]+/?', parsed.path)
        return match[1] if match else None
    except ValueError:
        return None


class DescriptionPoster(HTMLParser):
    def __init__(self, movie_id):
        super().__init__()
        self.movie_id = movie_id
        self.url = ''

    def handle_starttag(self, tag, attributes):
        if tag != 'img' or self.url:
            return
        value = urllib.parse.urljoin(BASE + '/', dict(attributes).get('src', ''))
        try:
            parsed = urllib.parse.urlsplit(value)
            match = re.fullmatch(r'/Media/PosterS/(\d{1,12})_Small\.jpg', parsed.path)
            if (parsed.scheme == 'https' and parsed.hostname == 'watchsomuch.to'
                    and not parsed.username and not parsed.password and parsed.port in (None, 443)
                    and not parsed.query and not parsed.fragment and match
                    and int(match[1]) == int(self.movie_id)):
                self.url = value
        except ValueError:
            return


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Even same-site redirects are optional metadata failures, not proxy targets.
        return None


def read_public(url, limit, image=False):
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers={'User-Agent': 'PlexPort/1.2'})
    try:
        response = opener.open(request, timeout=6)
    except urllib.error.HTTPError as error:
        error.close()
        raise
    with response:
        if response.geturl() != url:
            raise ValueError('Posteradres gewijzigd.')
        length = response.headers.get('Content-Length')
        if length is not None and (not length.isdigit() or int(length) > limit):
            raise ValueError('Posterantwoord te groot.')
        if image and response.headers.get_content_type() != 'image/jpeg':
            raise ValueError('Geen JPEG-poster.')
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError('Posterantwoord te groot.')
        if image and not body.startswith(b'\xff\xd8\xff'):
            raise ValueError('Geen JPEG-poster.')
        return body


class PosterCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.outbound = threading.BoundedSemaphore(2)
        self.metadata = OrderedDict()
        self.images = OrderedDict()
        self.image_bytes = 0
        self.pending = {}

    def cached(self, key):
        item = self.metadata.get(key)
        if item is None:
            return None
        expires, result = item
        image_key = result.get('image_url', '').removeprefix('/posters/').removesuffix('.jpg')
        if expires <= time.monotonic() or (image_key and image_key not in self.images):
            del self.metadata[key]
            return None
        self.metadata.move_to_end(key)
        return dict(result)

    def lookup(self, title, year='', kind='movie'):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError('Vul een titel van maximaal 200 tekens in.')
        if kind not in ('movie', 'tv'):
            raise ValueError('Kies film of serie.')
        if not isinstance(year, str) or (year and (not re.fullmatch(r'\d{4}', year) or not 1888 <= int(year) <= 2199)):
            raise ValueError('Vul een geldig jaartal in.')
        title = title.strip()
        key = (normalized_title(title), year, kind)
        with self.lock:
            result = self.cached(key)
            if result is not None:
                return result
            event = self.pending.get(key)
            owner = event is None
            if owner:
                if len(self.pending) >= 64:
                    return {'image_url': ''}
                event = self.pending[key] = threading.Event()
        if not owner:
            event.wait(25)
            with self.lock:
                return self.cached(key) or {'image_url': ''}
        result = {'image_url': ''}
        try:
            # Do not allow an arbitrary number of authenticated HTTP threads to
            # keep external connections open when several pages request artwork.
            if self.outbound.acquire(timeout=6):
                try:
                    result = self.resolve(title, year, kind)
                finally:
                    self.outbound.release()
        except Exception:
            # Artwork is optional and never prevents downloading or importing.
            result = {'image_url': ''}
        finally:
            with self.lock:
                ttl = 3600 if result['image_url'] else 300
                self.metadata[key] = (time.monotonic() + ttl, dict(result))
                self.metadata.move_to_end(key)
                while len(self.metadata) > METADATA_LIMIT:
                    self.metadata.popitem(last=False)
                self.pending.pop(key, None)
                event.set()
        return result

    def resolve(self, title, year, kind):
        keyword = ('Movies ' if kind == 'movie' else 'TV ') + title
        feed = read_public(BASE + '/RSS/?' + urllib.parse.urlencode({'Search': keyword}), FEED_LIMIT)
        root = ET.fromstring(feed)
        if root.tag != 'rss':
            return {'image_url': ''}
        matches = {}
        for item in root.findall('./channel/item'):
            name = item.findtext('title', '')
            year_match = re.search(r'\((\d{4})\)\s*$', name)
            item_year = year_match[1] if year_match else ''
            if year_match:
                name = name[:year_match.start()].strip()
            if normalized_title(name) != normalized_title(title) or (year and item_year != year):
                continue
            source_url = item.findtext('link', '')
            movie_id = catalog_id(source_url)
            if not movie_id:
                continue
            parser = DescriptionPoster(movie_id)
            parser.feed(item.findtext('description', ''))
            # Keep all matching catalog IDs, including a match without a poster,
            # so a different remake is not chosen just because it has an image.
            matches[movie_id] = (parser.url, source_url)
        if len(matches) != 1:
            return {'image_url': ''}
        url, source_url = next(iter(matches.values()))
        if not url:
            return {'image_url': ''}
        body = read_public(url, IMAGE_LIMIT, image=True)
        image_key = hashlib.sha256(url.encode()).hexdigest()
        with self.lock:
            if image_key not in self.images:
                self.images[image_key] = body
                self.image_bytes += len(body)
            self.images.move_to_end(image_key)
            while self.image_bytes > IMAGE_CACHE_LIMIT or len(self.images) > IMAGE_COUNT_LIMIT:
                _, removed = self.images.popitem(last=False)
                self.image_bytes -= len(removed)
        return {'image_url': '/posters/' + image_key + '.jpg', 'source_name': 'WatchSoMuch', 'source_url': source_url}

    def image(self, key):
        if not re.fullmatch(r'[a-f0-9]{64}', key):
            return None
        with self.lock:
            body = self.images.get(key)
            if body is not None:
                self.images.move_to_end(key)
            return body
