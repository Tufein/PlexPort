# PlexPort developer handoff

PlexPort connects a user's search sources and torrent client to their existing Plex media folders. Work from this repository and its current code. Communicate with the owner in plain Dutch; public GitHub documentation is English, while app labels are currently Dutch.

## Current state

- Website/server source: **1.7.0**, adding title-history warnings, observed hardlink/copy estimates and opt-in episode/file selection for qBittorrent and Transmission. The unified task/import view, grouped versions, actor/wildcard search and saved preferences remain available. `/api/status` reports the running server version.
- Published Android APK: **1.2.0**, `versionCode` **3**, package `nl.plexport.app`. Native source for the next upgrade is **1.3.0**, `versionCode` **4**; publish it only after building with the existing private signing key and verifying certificate compatibility. The WebView loads the website from the user's server. A source update does not prove that the user's NAS has been updated.
- The Android release build, signature, URL tests and lint have passed. The personal build was installed in an isolated emulator, but native screen rendering and a physical phone flow have not been validated. Do not describe those as completed checks.
- Consult [CHANGELOG.md](CHANGELOG.md), [ROADMAP.md](ROADMAP.md), [next feature briefs](docs/NEXT-FEATURES.md) and [technical guide](docs/TECHNISCH.md). Future proposals are not implemented merely because they appear there.

## Architecture

The backend uses Python 3.11+ and only the standard library; no Python dependencies need installing. The frontend is plain HTML, CSS and JavaScript. Android is a small Java WebView client.

| File or folder | Responsibility |
|---|---|
| `plexport/server.py` | HTTP routes, authentication, sessions, API and static files |
| `plexport/core.py` | SQLite settings/jobs, persistent worker, validation and safe media imports |
| `plexport/integrations.py` | qBittorrent, Transmission, Torznab and Plex APIs |
| `plexport/watchsomuch.py` | Direct source search and magnet resolution |
| `plexport/posters.py` | Optional exact-match artwork with bounded caching |
| `plexport/search.py` | Validated wildcard queries and local filtering of source results |
| `plexport/static/` | User interface, filters, artwork, login and themes |
| `android/` | WebView shell, native welcome/login, APK build and existing release APK |
| `tests/` | Local API fixtures, temporary filesystem tests and dependency-free JavaScript tests |

## Preserve the user's installation

- Settings, credentials and jobs are stored in the mounted SQLite data folder. Keep the existing database, download folders, media folders, Compose settings and ownership/permissions. Do not replace them with public examples.
- PlexPort and the downloader must refer to the same physical download files. Preserve the mapping between each client's container path and the NAS host path. Folder spelling and case matter.
- Existing jobs retain their original downloader endpoint and paths. Do not bulk rewrite them or switch their client while updating the app.
- Before an authorized deployment, back up the affected code and data safely, update only intended files, and verify running code plus retained settings and tasks. Do not stop, remove or delete real user torrents to exercise tests.
- Download deletion is opt-in, limited to the task's torrent and guarded by its original save location. Imported Plex media must remain intact. Keep list-only removal distinct from stopping or deleting in the downloader.
- Do not publish `.env`, SQLite databases, credentials, signing keys or NAS backups. Have the user enter authentication details directly when needed; do not request passwords in chat.
- The Android signing key is excluded from this public repository. Published APK updates require the existing private key and a higher version code. Do not regenerate a key for an update; request access through the owner's private build setup if a native release is needed.

## Important behavior

**Search:** ordinary queries remain supported. `*` matches any number of characters and `?` one character. Discover sends a useful literal fragment to sources and filters only the bounded results they return; this is not a whole-catalog search. Preserve query/result limits and use bounded-state matching rather than converting user input to a regex that can backtrack excessively. The download-list filter runs locally.

**Preferences:** `preferences` contains `quality`, `max_gb`, `min_seeders` and `sort`. Values are validated against supported choices. Legacy settings get defaults in memory without a database rewrite on read. Partial saves preserve other fields and secrets. Explicit save shares preferences through the server; **Alles tonen** changes only current filters. Source selection is temporary.

**Task views:** downloads and imports share one task list. Imported files remain visible even when sharing is stopped or a Plex scan fails. Preserve `#library` as an alias to the imported view. Group search versions only with reliable title/year/type and TV episode identity; preserve each original result index and release link.

**Imports:** only complete, supported media from PlexPort-managed jobs is imported. Samples are skipped; RAR/ZIP files are not extracted. Try a hardlink, with a protected copy fallback when necessary. Keep originals available for seeding, refuse unsafe paths and never overwrite existing library content with different bytes. A Plex scan request is not confirmation that Plex matched a title.

**Before downloading:** title warnings check current PlexPort tasks only. Known different years and episodes stay separate. Confirm the current matching task IDs explicitly; this never bypasses identical-torrent protection. A filesystem probe tests real linking between the configured folders. Its space estimate is an observation, not a reservation, and cleanup failures report an unknown method.

**Episode selection:** opt-in TV tasks wait for trustworthy file metadata and a committed choice before importing. Metadata acquisition can contact peers and transfer data. Validate file identities and indices against a current metadata token before changing priorities; use only the task's original downloader and paths. Require one supported video, explicitly selected matching subtitles and completion of every selected file. Preserve choices through restart, stop/resume and retry. Existing tasks retain their previous behavior.

## Verification

From the repository root:

```sh
python3 -m unittest discover -s tests -v
node --test tests/*.cjs
node --check plexport/static/app.js
```

Use temporary folders and local fixtures. Check affected website flows on desktop and a narrow mobile viewport, including dark mode, errors and cancellations. These tests do not establish a real NAS-to-Plex download or a physical Android flow; record what was actually exercised. See [Android verification](android/VALIDATIE.md) before claiming native coverage.

For local development, `python3 -m plexport --open` starts the app. Use isolated data and media paths when experimenting; do not connect a test worker to the owner's production data or downloads.

WatchSoMuch's RSS query parser also affects recall: free words search from word beginnings, and some names are interpreted as actor filters. Local wildcard matching cannot recover items the provider did not return. Live read-only checks passed with `Star*` (92 versions) and `Nosferatu*` (87 versions); fragments from the middle of a word can return no items. Do not advertise exhaustive wildcard searching across a provider catalog.
