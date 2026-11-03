"""Optional completion and problem messages sent to one user-configured webhook."""
import json
import urllib.parse

from .integrations import http_url, request


def payload(url, title, message):
    host = urllib.parse.urlsplit(url).hostname or ''
    text = title + ': ' + message
    headers = {'User-Agent': 'JellyPort'}
    if host in ('discord.com', 'discordapp.com') or host.endswith(('.discord.com', '.discordapp.com')):
        return json.dumps({'content': text}).encode(), {**headers, 'Content-Type': 'application/json'}
    if host == 'hooks.slack.com':
        return json.dumps({'text': text}).encode(), {**headers, 'Content-Type': 'application/json'}
    # ntfy and similar services accept the message as a plain body.
    return text.encode(), {**headers, 'Content-Type': 'text/plain; charset=utf-8'}


def send(url, title, message):
    """Send one message. The URL is a credential; never log it or echo it back."""
    url = http_url(url)
    body, headers = payload(url, str(title)[:200], str(message)[:800])
    request(url, body, headers, timeout=10)
