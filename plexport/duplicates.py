"""Conservative title warnings within the current PlexPort task history.

These matches are advisory: they do not inspect Plex or the filesystem, establish
torrent identity, or decide whether a download may be added. Callers must retain
the separate fingerprint check and repeat this check while holding their lock.
"""

from collections.abc import Mapping
import re
import unicodedata


_MAX_TITLE_LENGTH = 512
_YEAR = re.compile(r'(?:18|19|20|21)[0-9]{2}')
_RELEASE_DETAILS = re.compile(
    r'(?<!\w)(?:[0-9]{3,4}p|[248]k|web[ ._-]?(?:dl|rip)|blu[ ._-]?ray|'
    r'b[dr]rip|hdtv|x26[45]|hevc|s[0-9]{1,3}(?:[ ._-]*e[0-9]{1,3})?)(?!\w)')


def _title_keys(value):
    if not isinstance(value, str) or len(value) > _MAX_TITLE_LENGTH:
        return '', ''
    exact = ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
    if len(exact) > _MAX_TITLE_LENGTH or not any(char.isalnum() for char in exact):
        return '', ''
    # Punctuation variants can merit a caution, but never a definite match.
    # Preserve symbols, accents, word order and every word; do not fuzzy-match
    # prefixes or guess the library title from a torrent release name.
    loose = ' '.join(''.join(' ' if unicodedata.category(char).startswith('P') else char
                            for char in exact).split())
    return exact, loose


def _year(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return ''
    text = str(value).strip()
    return text if _YEAR.fullmatch(text) else ''


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return int(text) if re.fullmatch(r'[0-9]{1,3}', text) else None


def _tv_reason(existing, candidate):
    season, episode = _number(candidate.get('season')), _number(candidate.get('episode'))
    old_season, old_episode = _number(existing.get('season')), _number(existing.get('episode'))
    if season is not None and old_season is not None and season != old_season:
        return 'different'
    if episode is not None and old_episode is not None and episode != old_episode:
        return 'different'
    # A season without an episode can contain many episodes. It is not the same
    # identity as a single episode, even when that episode falls in its season.
    if (season is not None and episode is None) or (old_season is not None and old_episode is None):
        return 'season_pack'
    if None in (season, episode, old_season, old_episode):
        return 'missing_episode'
    return ''


def title_conflicts(jobs, candidate):
    """Return public advisory matches for a confirmed library-title candidate.

    Input jobs and candidate use ``title``, ``kind`` (movie/tv), ``year``,
    ``season`` and ``episode`` as stored by PlexPort. Each returned match contains
    only id/title/kind/year/season/episode/state, an ``imported`` boolean based on
    recorded files, ``certainty`` (definite/possible), and a stable ``reason``:
    same_title, missing_year, ambiguous_title, season_pack, or missing_episode.

    Exact normalized titles with known equal years (and full equal TV identity)
    are definite. Missing metadata, punctuation variants and release-like names
    only produce cautions. Different known years, seasons or episodes never match.
    Removed tasks are absent from the supplied current history. Input is not
    mutated, and private settings, links and imported paths are never returned.
    """
    if not isinstance(candidate, Mapping) or candidate.get('kind') not in ('movie', 'tv'):
        return []
    title, loose_title = _title_keys(candidate.get('title'))
    if not title:
        return []
    kind, year = candidate['kind'], _year(candidate.get('year'))
    matches = []
    for existing in jobs:
        if not isinstance(existing, Mapping) or existing.get('kind') != kind:
            continue
        if not isinstance(existing.get('id'), str) or not existing['id']:
            continue
        old_title, old_loose_title = _title_keys(existing.get('title'))
        if not old_title or (old_title != title and old_loose_title != loose_title):
            continue
        old_year = _year(existing.get('year'))
        if year and old_year and year != old_year:
            continue
        tv_reason = _tv_reason(existing, candidate) if kind == 'tv' else ''
        if tv_reason == 'different':
            continue
        if tv_reason:
            reason = tv_reason
        elif old_title != title or _RELEASE_DETAILS.search(title) or _RELEASE_DETAILS.search(old_title):
            reason = 'ambiguous_title'
        elif not year or not old_year:
            reason = 'missing_year'
        else:
            reason = 'same_title'
        matches.append({
            'id': existing['id'], 'title': existing['title'], 'kind': kind, 'year': old_year,
            'season': _number(existing.get('season')), 'episode': _number(existing.get('episode')),
            'state': existing.get('state') if isinstance(existing.get('state'), str) else '',
            'imported': isinstance(existing.get('files_imported'), list) and bool(existing['files_imported']),
            'certainty': 'definite' if reason == 'same_title' else 'possible', 'reason': reason,
        })
    return matches
