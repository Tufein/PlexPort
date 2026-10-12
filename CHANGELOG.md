# What's new?

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
