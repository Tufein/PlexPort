"""Observe import storage without changing configured folders or user media."""

import errno
import os
from pathlib import Path
import shutil
import tempfile
import uuid


_COPY_ERRORS = {errno.EXDEV, errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOTSUP}
_NOTE = ('Deze controle is een momentopname, geen garantie of ruimtereservering. '
         'Maprechten, bestandssystemen, quota en andere downloads kunnen veranderen. '
         'De downloader moet dezelfde downloadmap gebruiken als PlexPort.')


def _problem(error):
    if isinstance(error, PermissionError) or getattr(error, 'errno', None) in (errno.EACCES, errno.EPERM):
        return 'De maprechten laten de importcontrole niet toe.'
    if isinstance(error, FileNotFoundError):
        return 'De download- of mediamap is tijdens de controle verdwenen.'
    if getattr(error, 'errno', None) == errno.ENOSPC:
        return 'Er is geen vrije ruimte voor het tijdelijke controlebestand.'
    if isinstance(error, ValueError):
        return str(error)
    return 'De importcontrole van de download- en mediamap is mislukt.'


def _remove_probe(path):
    """Retry a transient failure, while always allowing the other file to clean up."""
    for attempt in range(2):
        try:
            os.unlink(path)
            return None
        except FileNotFoundError:
            return None
        except OSError as error:
            if attempt:
                return error


def _space(result, size):
    result.update(required_download_bytes=size or None, required_library_bytes=None,
                  required_shared_bytes=None, space_ok=None)
    if not size:
        result['space_message'] = 'De bestandsgrootte is onbekend; de benodigde ruimte kan nog niet worden geschat.'
        return
    if result['method'] == 'unknown':
        result['space_message'] = 'De importmethode is onbekend; de benodigde extra ruimte is nog onbekend.'
        return
    copying = result['method'] == 'copy'
    result['additional_bytes'] = size if copying else 0
    result['required_library_bytes'] = size if copying else 0
    downloads, library = result['download_free_bytes'], result['library_free_bytes']
    if downloads is None or library is None:
        result['space_message'] = 'De vrije ruimte kon niet volledig worden gecontroleerd.'
        return
    if result['shared_filesystem']:
        required = size * (2 if copying else 1)
        result['required_shared_bytes'] = required
        # Never add readings of the same storage. The smaller reading is cautious
        # when directory quotas expose different limits; quota semantics can vary.
        available = min(downloads, library) if copying else downloads
        result['space_ok'] = available >= required
        if copying:
            result['space_message'] = ('Download en tweede kopie gebruiken gedeelde opslag; er is ruimte voor beide nodig. '
                                       'De vrije ruimte is daarvoor ' + ('nu voldoende.' if result['space_ok'] else 'nu te klein.') +
                                       ' Aparte mapquota kunnen extra beperkingen geven.')
        else:
            result['space_message'] = ('De gemeten vrije downloadruimte is ' +
                                       ('nu voldoende.' if result['space_ok'] else 'nu te klein.'))
    else:
        result['space_ok'] = downloads >= size and (not copying or library >= size)
        result['space_message'] = ('Download en media hebben aparte ruimtemetingen; de vrije ruimte is ' +
                                   ('nu voldoende.' if result['space_ok'] else 'nu te klein voor de download of tweede kopie.'))


def import_capability(config, kind, expected_bytes=0):
    """Probe actual linking, then report a before-download space estimate.

    ``supported`` means that a real hardlink was observed, not that the client
    connection succeeded. ``space_ok`` budgets the download AND its future copy;
    after downloading, use ``additional_bytes`` instead of budgeting twice again.
    Missing or zero sizes mean unknown. Config and existing media remain intact.
    """
    if kind not in ('movie', 'tv'):
        raise ValueError('Kies een film of serie voor de importcontrole.')
    if type(expected_bytes) is not int or not 0 <= expected_bytes <= 1024 ** 5:
        raise ValueError('Ongeldige bestandsgrootte. Kies de download opnieuw.')
    result = {'method': 'unknown', 'supported': None, 'additional_bytes': None,
              'message': 'Importmethode onbekend.', 'note': _NOTE, 'error': None,
              'cleanup_errors': [], 'download_free_bytes': None,
              'library_free_bytes': None, 'shared_filesystem': None,
              'expected_bytes': expected_bytes}
    owned = []
    try:
        downloads = Path(config['downloader']['local_root'])
        library = Path(config['library']['movies' if kind == 'movie' else 'tv'])
        for path, label in ((downloads, 'downloadmap'), (library, 'mediamap')):
            if not path.is_absolute() or not path.is_dir():
                raise ValueError('De ' + label + ' is niet bereikbaar. Controleer de mapkoppeling bij Instellingen.')
        result['shared_filesystem'] = downloads.stat().st_dev == library.stat().st_dev
        marker = ('PlexPort import check ' + uuid.uuid4().hex).encode('ascii')
        descriptor, name = tempfile.mkstemp(prefix='.plexport-import-', dir=downloads)
        source = Path(name)
        owned.append(source)
        with os.fdopen(descriptor, 'wb') as probe:
            probe.write(marker)
            probe.flush()
        destination = library / ('.plexport-import-' + uuid.uuid4().hex)
        try:
            os.link(source, destination)
            owned.append(destination)
            method = 'hardlink'
        except OSError as error:
            if error.errno not in _COPY_ERRORS:
                raise
            # A failed link alone does not establish that a protected copy works.
            with destination.open('xb') as probe:
                owned.append(destination)
                probe.write(marker)
                probe.flush()
            method = 'copy'
        if destination.read_bytes() != marker:
            raise ValueError('Het tijdelijke importbestand kon niet betrouwbaar worden teruggelezen.')
        if method == 'hardlink':
            original, linked = source.stat(), destination.stat()
            if (original.st_dev, original.st_ino) != (linked.st_dev, linked.st_ino):
                raise ValueError('De controle kon het hergebruik van het downloadbestand niet bevestigen.')
        result.update(method=method, supported=method == 'hardlink')
    except Exception as error:
        result['error'] = _problem(error)
    finally:
        for path in reversed(owned):
            error = _remove_probe(path)
            if error is not None:
                result['cleanup_errors'].append(str(path))
    if result['cleanup_errors']:
        result['error'] = ('Een tijdelijk controlebestand kon niet worden verwijderd. '
                           'Controleer de maprechten en ruim de vermelde controlebestanden op.')
    if result['error'] is None:
        try:
            result['download_free_bytes'] = shutil.disk_usage(downloads).free
            result['library_free_bytes'] = shutil.disk_usage(library).free
        except Exception as error:
            result['error'] = _problem(error)
    if result['error'] is not None:
        result.update(method='unknown', supported=None, message='Importmethode onbekend. ' + result['error'])
    elif result['method'] == 'hardlink':
        result['message'] = 'Je media kan de gedownloade video hergebruiken zonder een tweede kopie.'
    else:
        result['message'] = 'Importeren maakt waarschijnlijk een tweede kopie; de download blijft beschikbaar om te delen.'
    _space(result, expected_bytes)
    return result
