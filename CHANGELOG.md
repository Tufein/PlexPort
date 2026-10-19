# What's new?

## Website/server 1.9.0 — October 19, 2026

- Downloads that are already in your downloader get a **Snelheid (Speed)** menu to cap that one torrent's download speed (unlimited, 1, 2, 5 or 10 MB/s). It works with qBittorrent and Transmission, changes only the chosen torrent and leaves the downloader's global limits and other torrents alone. The limit is stored with the task. This is covered by local fixture tests; it has not been tried against a real downloader or on a physical phone.

## Website/server 1.8.0 — October 15, 2026

- **YTS** adds a direct movie source and **EZTV** adds a direct TV source, both without an API key. EZTV looks up matching shows through TVmaze and requests their IMDb-specific torrents. Settings offers explicit add buttons; existing sources and credentials remain in place.
- Source requests are bounded, cached briefly and use fixed HTTPS providers. Unavailable sources report errors without discarding successful results from the others. Movie and TV searches skip sources that do not support the chosen category; actor search continues to use WatchSoMuch.
- Each result card now shows one recommended torrent and a **Downloaden (Download)** button. The recommendation chooses among the versions that pass your filters, prioritizing seeders, then quality, known smaller size and stable input order. It remains a recommendation, not a guarantee of speed or content.
- Other qualities and versions are collapsed by default under **Andere kwaliteit of versie kiezen (Choose another quality or version)**. Opening the list retains every eligible release and its original link. Both the recommended button and manual choices keep the normal confirmation, space and title-history checks.
- These changes load through the updated server in the website and existing Android APK 1.2.0. No new native APK is required.

## Website/server 1.7.0 — October 15, 2026

- Before adding another version, PlexPort warns about matching titles in its current task history and distinguishes earlier imports from active or stopped downloads. Known different years and episodes remain separate. Missing identity information is described as uncertain. Continuing requires an explicit confirmation; identical torrents remain blocked, including simultaneous requests.
- Download preflight tries an actual hardlink between the configured download and media folders. It explains whether the video can reuse existing data, a copy needs extra storage, or the method is unknown. Known-size copy estimates account for shared storage without adding independent free-space readings. Checks reserve no space and the import still checks actual capacity.
- TV downloads can opt in to **Zelf afleveringen en bestanden kiezen (Choose episodes and files)**. After metadata arrives, choose supported videos and matching subtitles. Multiple episodes in one video remain one file. The selection is checked against the downloader's current file identities and saved across restart, stop/resume and retry. PlexPort imports only selected completed files.
- Metadata acquisition may contact peers and receive data before selection. Once metadata is ready the managed torrent waits for the user's choice. Existing tasks keep their current download behavior.
- The server update supplies these controls to the website and the existing signed Android APK 1.2.0. No new native APK is included and no real NAS or physical phone deployment is implied.

## Website/server 1.6.0 — October 13, 2026

- **Downloads** now brings active, stopped, problem and imported tasks together, with status tabs and a shared search. The imported view retains file paths and **Plex laten scannen (Ask Plex to scan)**. Existing `#library` links open that view.
- **Opslaan & controleren (Save & check)** is the main settings action. Individual connection tests share the same reporting. Saving a search source or unchanged settings retains unrelated successful checks; changing a connection or folder invalidates only its affected checks.
- Discover groups trustworthy matching titles into one card with separate download versions. Different years and TV episodes stay separate, and incomplete identity information is not guessed. Filters retain the original version selection.
- Download task creation, duplicate protection and folder checks share one entry point. Updated downloader credentials apply only to the original downloader; submitted tasks retain their original server and download paths.
- Status updates refresh progress and artwork once. Shared filter mappings retain saved preferences and the temporary **Alles tonen (Show everything)** behavior.
- Signing in from the main server URL now reloads the app when the destination URL is unchanged, retaining the selected view.
- These website changes also appear in the existing Android WebView after updating its server. Publishing server source does not confirm that a NAS or phone has been updated.

## Use PlexPort away from home — Included in 1.6.0

- A new [Tailscale guide](docs/START-REMOTE.md) explains how to reach PlexPort from your phone or another computer without opening router ports. No server or Android update is needed.
- The guide has not yet been tested on a real NAS or phone.

## Search by actor — Included in 1.6.0

- Choose **Op acteur (By actor)** in **Ontdekken (Discover)** and type a name such as `Tom Hanks`. PlexPort asks your WatchSoMuch source and keeps films that credit that person in their cast list, so title matches with other people are left out.
- Results show the first names of the cast. Actor search uses WatchSoMuch only, returns at most the first eight matching titles, and does not use `*` or `?`. Other sources are skipped.
- This arrives through a server update; the Android APK remains 1.2.0.

## Website 1.5 — October 12, 2026

- Search with `*` for any number of characters and `?` for one character, for example `Star*`, `Harry*Potter` or `Example 202?`. Ordinary title searches remain supported.
- Wildcards also work when searching your own downloads. Discover applies them to the limited results returned by your connected sources; broad patterns can miss titles and do not browse the full catalog.
- Remember quality, maximum size, minimum seeders and sorting with **Voorkeuren onthouden (Remember preferences)**. Choices are saved on your PlexPort server and available on the website and Android.
- **Mijn voorkeuren toepassen (Apply my preferences)** reloads saved choices. **Alles tonen (Show everything)** temporarily removes filters without changing saved preferences. Source selection remains temporary.
- Existing databases receive default preferences when read, without replacing connections, credentials, folders or task history. Saving preferences alone keeps existing connection-check results.
- These controls arrive through a server update; the signed Android APK remains 1.2.0. This entry describes source changes, not confirmation that an existing NAS has been updated.

## Movie and TV posters — October 11, 2026

- Posters make titles easier to recognize in the overview, downloads, library and search results. The same images appear in the Android app after the server update.
- Posters are matched by title and year through WatchSoMuch, with a link to their source. No extra account or API key is needed.
- Missing, ambiguous or temporarily unavailable images fall back to a film or TV icon. Posters never delay adding a download or importing media.
- Images are loaded through your PlexPort server and cached with bounded storage. Existing download settings and media folders remain in use.

## Download controls — October 11, 2026

- **Stoppen (Stop)** stops the torrent and puts the PlexPort task on hold, including automatic importing. **Hervatten (Resume)** continues it later.
- **Verwijderen (Remove)** opens a confirmation with a choice to retain or delete download files. Imported Plex media stays in place.
- The default removes the task from PlexPort and the torrent from the downloader, while retaining downloaded files. A separate list-only option is available when the downloader cannot be reached; it does not stop the torrent.
- Stopped downloads have their own filter and are excluded from active counts. Controls also appear in the existing Android app after the server update.
- Cleanup is limited to the task's torrent. File deletion is refused if its download folder has changed. A failed downloader request leaves the task available for retry.

## Website and Android 1.2 — October 11, 2026

- A dedicated website sign-in page with theme selection, password visibility, clear errors and a sign-out button.
- Modern blue and slate styling, larger text, clearer cards and mobile navigation.
- A matching Android sign-in card with labeled fields, password visibility and clearer server details.
- Android APK 1.2.0 retains the existing signing certificate and saved server address.
- Browser sessions expire after 12 hours and are invalidated on sign-out. Existing Android and Basic Auth API clients remain supported.

## English documentation — October 11, 2026

- The GitHub home page, setup guides, troubleshooting, roadmap and contribution instructions are now in English.
- Problem and feature request forms now accept English reports with English prompts.
- Guides explain the Dutch labels used by the current app interface.

## Android 1.1.0 — October 11, 2026

- A new signed APK that installs over the previous version. Your saved NAS address is preserved.
- The app loads the updated PlexPort interface from your NAS, including search filters, download statuses and storage checks.
- The build script now uses the current version number automatically for the APK filename.

## Website 1.1 — October 11, 2026

- A simpler GitHub home page with separate guides for TrueNAS, Mac and Android.
- A checklist to help set up your downloader, folders and search sources.
- **Alles controleren (Check everything)** tests saved connections and folder write access.
- Search filters for HD, Full HD, 4K, maximum size, source and seeders.
- Sort versions by name, size or seeders.
- Search your downloads and filter for active tasks, problems or imported media.
- Clearer messages for preparing, checking, waiting and moving files.
- Progress bars show the correct percentage and expose accessible progress information.
- Download folder, destination and free-space checks before starting. Known downloads that are too large are blocked.
- An extra space check before a required copy to the media folder.

The server supplies these controls, so they also appear in the existing Android app. Update the app files while keeping the settings folder to preserve settings and tasks.
