# PlexPort technical guide

[Back to the simple start page](../README.md) · [Daily use](GEBRUIKEN.md)

PlexPort is a local app that searches your sources, sends torrents to Transmission or qBittorrent, and imports completed media into your Plex folders. The current interface uses Dutch labels; repository documentation is in English.

At the top, **Weergave (Appearance)** offers **Systeem (System)**, **Licht (Light)** and **Donker (Dark)**. Your choice is saved per browser. A signed [Android APK](../android/dist/PlexPort-1.2.0.apk) is available through **Instellingen → Android-app downloaden (Settings → Download Android app)** too. It uses the same NAS, sources and downloads. See the [Android guide](../android/README.md) and [download roadmap](../ROADMAP.md).

**TrueNAS 25.10 Goldeye:** follow [INSTALLATIE-TRUENAS.md](../INSTALLATIE-TRUENAS.md). `compose.yaml` and `compose.truenas.yaml` are examples for the Apps web interface. Adjust the NAS address, dataset paths and UID/GID, then set your own PlexPort password. PlexPort and qBittorrent must see the same physical download folder as `/downloads`.

**Other NAS or local Docker installation:** follow [INSTALLATIE-NAS.md](../INSTALLATIE-NAS.md) with `compose.build.yaml` for an existing qBittorrent. Use `compose.transmission.yaml` to include a new torrent downloader. Only those two variants use `.env`.

## Start on a Mac

Double-click **Start PlexPort.command**, or run from the project folder:

```sh
python3 -m plexport --open
```

Python 3.11 or newer is enough; no additional Python packages are required. The app opens at **http://127.0.0.1:8765**. Keep the terminal window open to process downloads. Closing it or pressing Ctrl+C stops PlexPort; the torrent client continues independently. Downloads and settings resume after restarting.

This launch method uses a **separately installed Transmission or qBittorrent**. The torrent engine does not run in the Python process.

## Include a torrent downloader with Docker

The alternative Docker Compose setup starts PlexPort and Transmission together. Docker must be installed and running. For a local Docker build using an existing qBittorrent, use `compose.build.yaml` and start with `docker compose -f compose.build.yaml up -d --build`.

1. Copy `.env.example` to `.env`.
2. Choose your own app and Transmission passwords in `.env`.
3. Set `MEDIA_PATH` to your existing Plex media folder and `DOWNLOADS_PATH` to a download folder. Both must exist and be writable. On Linux or a NAS, set `PUID` and `PGID` to the folder owner's IDs.
4. Start:

```sh
docker compose -f compose.transmission.yaml up -d --build
```

Open **http://YOUR-NAS-ADDRESS:8765**, with username **admin** and `PLEXPORT_PASSWORD`. Transmission is available at **http://YOUR-NAS-ADDRESS:9091** using the Transmission credentials in `.env`. Stop with `docker compose -f compose.transmission.yaml down`. Settings, torrents and media remain in mounted folders.

This setup makes the controls reachable on your NAS with password authentication. For internet access, use a reverse proxy with HTTPS; the app does not include a TLS server.

## Configure connections

Open **Instellingen (Settings)**, then save and test each connection.

### Downloader

- **Transmission:** use the full RPC address, such as `http://127.0.0.1:9091/transmission/rpc`. The supplied Docker setup uses `http://transmission:9091/transmission/rpc`.
- **qBittorrent:** enable its Web UI and use the base address, such as `http://192.168.1.20:8080`, with a username and password. The integration targets qBittorrent 4.6+ and 5.x, including pause and resume.
- Enter the download folder as the **downloader** sees it, and the same folder as **PlexPort** sees it. The downloader must actually write files to that shared folder. Each task gets its own subfolder.

Example: qBittorrent runs on a NAS and writes to `/volume1/downloads`. That folder is mounted on your Mac as `/Volumes/downloads`. Set the downloader path to `/volume1/downloads` and the PlexPort path to `/Volumes/downloads`.

In Docker, both use `/downloads` by default. For qBittorrent on the Docker host, use `http://host.docker.internal:8080` where supported; `localhost` inside a container refers to that container itself.

### Plex

Set separate movie and TV folders that **PlexPort can read and write** and that your Plex server also reads. A server on a NAS or another computer therefore needs a mounted SMB/NFS folder or Docker volume mount. Entering only the Plex address is not enough: the Plex API does not upload media files.

With Docker, the app paths default to `/media/Movies` and `/media/TV Shows`. For `compose.build.yaml` and `compose.transmission.yaml`, if `MEDIA_PATH=/volume1/media`, configure Plex to read `/volume1/media/Movies` and `/volume1/media/TV Shows`, or their equivalent paths inside the Plex container.

For scanning after import, enter the Plex address and token. **Opslaan & Plex testen (Save & test Plex)** lists libraries and their IDs. Enter the appropriate movie and TV IDs. See [Plex Support for token instructions](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

Files are imported even without a Plex token. Enable automatic or periodic scanning in Plex in that case. Network folders do not always support automatic change detection, so an API scan or periodic scan may be needed. See [Plex library settings](https://support.plex.tv/articles/200289526-library/).

A successful scan request means Plex accepted it; the app does not verify that Plex subsequently identifies the title correctly. **Downloads → Geïmporteerd (Imported)** shows only PlexPort imports, not your full Plex catalog. Existing `#library` links open that view.

### Sources and search

Under **Instellingen → Jouw bronnen → WatchSoMuch toevoegen (Settings → Your sources → Add WatchSoMuch)**, connect [WatchSoMuch](https://watchsomuch.to) directly and save settings. This source needs no account, API key, Jackett or Prowlarr. PlexPort uses public RSS search feeds and download lists, shows versions with size and seeders, and retrieves the magnet link only when starting a download. Recognized TV season and episode numbers are filled in ahead of time; check them before starting.

A search reads up to five matching titles and shows up to 250 versions, cached for five minutes. Search as specifically as possible. Website changes or temporary blocks may interrupt the integration; PlexPort will not start a download using an invalid link.

For other sources, add a **Torznab feed** and API key. [Prowlarr](https://wiki.servarr.com/prowlarr) and [Jackett](https://github.com/Jackett/Jackett) provide these feeds for their configured indexers. Copy the Torznab URL from your source manager. PlexPort searches Movies (2000) or TV (5000) categories; results are sorted by seeders.

You choose which sources to enable; no accounts are supplied. Without a search source, you can still add a magnet link, torrent URL or `.torrent` file.

## How importing works

1. Add a download and check **Titel voor Plex (Title for Plex)**. WatchSoMuch fills the title and year from the search feed. Torznab fills the release name; change it to the actual movie or show title and optionally enter the year.
2. PlexPort saves the task in SQLite and sends it to the downloader. Progress updates every four seconds.
3. Only complete, selected video files and subtitles are imported. The app checks accessibility and file sizes. Samples and other files are skipped. RAR/ZIP archives are not extracted.
4. Movies are placed in `Title (year)/Title (year).mkv`. The largest video is named as the main video; other videos keep their filenames in that folder. TV shows use `Show/Season 01/Show - S01E01.mkv`. Season packs require episode codes in filenames. For a single episode, you can enter season and episode manually.
5. The app uses hardlinks on the same filesystem where supported; it copies files across disks or network shares. The original download stays in place for seeding. Copying can use extra space.
6. After import, a Plex scan is requested if configured. A failed scan does not remove imported media. Use **Opnieuw proberen (Retry)** after fixing settings.

Only downloads added through PlexPort are imported this way. Torrents added directly through qBittorrent's Web UI stay in the download folder without an automatic PlexPort import.

The app does not replace existing media with different content. Duplicate torrents are rejected. Not all release names, extras or subtitle languages can be recognized automatically; check titles and use episode codes for TV shows. PlexPort does not transcode or download subtitles.

## Data and access

Settings, credentials and task history are stored locally in `data/plexport.sqlite` with file permissions `0600`. Secrets are not returned to the settings form; blank password fields retain saved values. Credentials are needed in the local database to connect to services. Protect backups of this folder. To remove a saved secret, the local API can explicitly save an empty value.

The standalone app listens only on `127.0.0.1` by default. For another listening interface, set `PLEXPORT_PASSWORD`; sign in as `admin` with that password. The website uses a dedicated sign-in page and an HttpOnly, SameSite=Strict session cookie. Sessions last up to 12 hours, stay in server memory and expire on server restart. Signing out invalidates the session, including browsers with cached Basic Auth credentials. Password login is limited to eight failed attempts per IP in a minute. Cookies are marked Secure on HTTPS sockets or an HTTPS browser login origin. Existing Android WebViews and Basic Auth API clients remain supported. API and authentication requests require a dedicated header and browser-origin validation. No telemetry is sent, and the interface uses no external fonts or scripts.

## Development and verification

```sh
python3 -m unittest discover -s tests -v
node --check plexport/static/app.js
node --test tests/test_discovery.cjs
```

Tests use temporary folders and local test servers. They cover torrent APIs, imports, restarts, path protection, secret redaction, search feeds and the browser API. A real torrent client, Docker installation, external source and Plex server are needed to test integrations in your own environment.

Server status at `GET /api/status` includes the running `version`. Download creation uses one task-layer entry point for locking, duplicate checks, folder checks and persistence; the worker repeats folder checks before submission. Downloader credentials can refresh only for the task's original endpoint, without rewriting its saved paths. Saving unchanged settings or search sources preserves unrelated connection checks. See [NAS updates](UPDATING-NAS.md) for verified releases, backups and code-only rollback.

## Updated controls

Search filters run in the browser on the existing search request's maximum 250 results. Quality is inferred from the release name; it is not video verification. A maximum size excludes results whose size is unknown.

`POST /api/preflight` checks the saved download folder and destination for the selected category. The request includes `kind` (`movie` or `tv`) and optional `expected_bytes` (a nonnegative integer). It writes and removes a temporary test file and reads free space. It does not create missing folders or prove that an external downloader uses the same physical folder. No space is reserved. Other tasks and dataset quotas can affect the result.

Adding a task checks the folders again. The worker also rechecks a task that has not yet been submitted. Already submitted tasks retain their original downloader address and path. Missing movie or TV folders block starting the relevant category; only that category's destination is required.

The known size from a selected search result is used to reject a download larger than the space currently available. Manual links and torrent files do not have a known size in advance in this version. If hardlinks are unavailable, the copy step also checks free space in the media folder.

Activity from qBittorrent or Transmission is saved separately from import status. Checking, preparing, waiting, moving and downloading have distinct messages. qBittorrent tasks that are moving files, checking or fetching metadata are not imported, even if progress shows 100%.

## Title warnings, import estimates and file selection (1.7.0)

`POST /api/preflight` accepts title, kind, year, season, episode, expected bytes
and the optional `selection_requested` TV flag. It keeps folder results separate
from `import_capability` and `title_conflicts`. Choosing a season's files leaves
the size unknown until metadata and the selection are available.

Task creation checks current history again while holding the worker lock.
A `409 title_conflict` response lists public matching tasks; callers must supply
those exact IDs in `confirmed_conflicts` to continue. A new concurrent match
requires another explicit confirmation. Identical fingerprints remain rejected.
The warning is limited to current PlexPort history, not the complete Plex catalog.

For opt-in TV tasks, `POST /api/files` with a task ID returns metadata, original
file indices and a metadata token. `POST /api/select` submits that token and chosen
indices. Both downloader adapters verify the original server, save location,
file identity and resulting priorities. TV episode identity and selected indices
are persisted; completion is checked per selected file immediately before import.
An unavailable or changed metadata snapshot blocks import. Once import has begun,
including a partial import followed by an error, its selection cannot be changed.
Metadata acquisition can contact peers and transfer data before confirmation.

Use the downgrade precautions in [Updating a NAS](UPDATING-NAS.md) before running
an older runtime with unfinished selection tasks. The database needs no schema
migration; job records remain JSON and existing jobs keep their previous behavior.
