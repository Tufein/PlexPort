"""Portable wildcard filtering for bounded results returned by search sources.

Sources receive an ordinary literal search term. The wildcard pattern is applied
locally to the titles they return, so this cannot search their entire catalogue.
"""

import unicodedata


MAX_QUERY_LENGTH = 200
MAX_TITLE_LENGTH = 2048
_SEPARATORS = str.maketrans({'.': ' ', '_': ' ', '-': ' '})


def _literal(value):
    return unicodedata.normalize('NFKC', value).casefold().translate(_SEPARATORS)


def _provider_term(fragment):
    # Punctuation has no portable search meaning across Torznab providers.
    value = unicodedata.normalize('NFKC', fragment)
    return ' '.join(''.join(char if char.isalnum() else ' ' for char in value).split())


def prepare_query(query):
    """Validate a query and choose one useful literal term for remote sources."""
    if not isinstance(query, str):
        raise ValueError('Vul een zoekopdracht in.')
    query = query.strip()
    if len(query) < 2:
        raise ValueError('Vul minimaal twee tekens in.')
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError('Gebruik maximaal 200 tekens in je zoekopdracht.')
    wildcard = '*' in query or '?' in query
    if not wildcard:
        return {'query': query, 'term': query, 'wildcard': False}

    fragments = query.replace('?', '*').split('*')
    terms = [_provider_term(fragment) for fragment in fragments]
    terms = [term for term in terms if sum(char.isalnum() for char in term) >= 2]
    if not terms:
        raise ValueError('Gebruik bij * of ? ook een stuk tekst met minimaal twee letters of cijfers, bijvoorbeeld Star*.')
    return {'query': query, 'term': max(terms, key=len), 'wildcard': True}


def _pattern_tokens(query):
    """Keep wildcard operators separate from normalized literal characters."""
    tokens, literal = [], []

    def flush():
        for char in _literal(''.join(literal)):
            if char.isspace():
                if not tokens or tokens[-1] != ('literal', ' '):
                    tokens.append(('literal', ' '))
            else:
                tokens.append(('literal', char))
        literal.clear()

    for char in query:
        if char in ('*', '?'):
            flush()
            token = ('star', None) if char == '*' else ('any', None)
            if token[0] != 'star' or not tokens or tokens[-1][0] != 'star':
                tokens.append(token)
        else:
            literal.append(char)
    flush()
    while tokens and tokens[0] == ('literal', ' '):
        tokens.pop(0)
    while tokens and tokens[-1] == ('literal', ' '):
        tokens.pop()
    return tokens


def _matches_title(title, tokens):
    if not isinstance(title, str) or len(title) > MAX_TITLE_LENGTH:
        return False
    title = ' '.join(_literal(title).split())
    if len(title) > MAX_TITLE_LENGTH:
        return False
    # A bounded-state glob matcher avoids treating input as regular expressions
    # and avoids regex backtracking when users repeat wildcard operators.
    previous = [True] + [False] * len(tokens)
    for index, (kind, _) in enumerate(tokens, 1):
        if kind == 'star':
            previous[index] = previous[index - 1]
    for char in title:
        current = [True] + [False] * len(tokens)
        for index, (kind, literal) in enumerate(tokens, 1):
            if kind == 'star':
                current[index] = previous[index] or current[index - 1]
            else:
                current[index] = previous[index - 1] and (kind == 'any' or literal == char)
        if current[-1]:
            return True
        previous = current
    return previous[-1]


def filter_results(results, prepared):
    """Retain matching original result objects in their existing order."""
    if not prepared['wildcard']:
        return results
    tokens = _pattern_tokens(prepared['query'])
    return [result for result in results
            if any(_matches_title(result.get(field), tokens) for field in ('library_title', 'title'))]
