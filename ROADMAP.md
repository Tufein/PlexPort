# What's next?

[Back to the main page](README.md) · [What's already available?](CHANGELOG.md)

## Available now

Website/server **1.7.0** adds warnings about titles already in PlexPort history, an observed hardlink/copy space estimate and opt-in TV file selection for qBittorrent and Transmission. Download metadata can contact peers before selection; importing waits for a confirmed choice. These checks do not inspect the full Plex library or reserve disk space.

Version 1.6.0 consolidates downloads and imports into one overview with status tabs. Settings use **Opslaan & controleren (Save & check)**, preserving checks unaffected by changes. Discover groups versions only when title, year and episode identity are reliable. These features also appear in the existing Android WebView after updating the server.

The current source includes simple setup guides, connection and folder checks, download version filters, stop/resume/remove controls, and clearer explanations when a task is waiting. Dark mode, Android, movie and TV posters, qBittorrent, Transmission and media-folder imports are also available.

Website 1.5 adds **saved search preferences** for quality, maximum size, seeders and sorting, shared through your PlexPort server. Save them explicitly with **Voorkeuren onthouden (Remember preferences)**. **Alles tonen (Show everything)** temporarily clears the filters without deleting your saved choices.

**Wildcard search** accepts `*` for any number of characters and `?` for one character. You can use these in Discover and in your own download list. Discover filters the limited results returned by your sources; it does not search a source's entire catalog. Use a useful fragment such as `Star*` rather than only wildcard characters.

These describe the repository version. An existing NAS needs a server update before its website and Android WebView show the new controls. The Android APK remains 1.2.0.

The GitHub documentation is now in English. The app interface still uses Dutch labels.

## Next improvements researched

The first three researched priorities shipped in 1.7.0; their behavior and limits are described in [feature notes](docs/NEXT-FEATURES.md). The remaining ideas below are proposals without promised delivery dates.

| Idea | How it helps | What needs to work first |
|---|---|---|
| **Available · Warn about an existing title** | Avoid downloading a second version of a film or episode by accident. | Distinguish remakes and episodes; show a warning with an intentional override. Existing identical-download protection stays in place. |
| **Available · Explain extra storage before importing** | Understand whether an import can reuse the video or requires a copy. | Test actual hardlink support; the same disk or folder name is not proof. Explain that estimates do not reserve space. |
| **Available · Choose episodes from a season** | Download only the episodes you want. | Wait for trustworthy file information, persist selected files and import only complete selected media. |
| **Import an existing qBittorrent download** | Organize files downloaded outside PlexPort in Plex too. | Verify the existing location, avoid duplicate imports and let you confirm the title. Do not relocate or delete unrelated files. |
| **Completion and problem notifications** | Know when media is imported or a task needs attention. | Ask users which channel they want; avoid repeated alerts and protect channel credentials. A scan request alone does not prove Plex recognized the title. |
| **Guided TrueNAS setup** | Fewer folder settings and fewer incorrect mounts. | Preserve existing datasets, permissions and media without creating empty replacement folders. |
| **English app interface** | Use PlexPort without learning Dutch button labels. | Translate controls, status messages and errors consistently, while preserving settings and download behavior. |
| **Limits for an individual download** | Control how much bandwidth a PlexPort task uses. | Apply supported limits only to the chosen torrent; preserve the downloader's global settings and other torrents. |

## Research sources

The [official qBittorrent API documentation](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29) documents torrent metadata, file priorities and individual speed limits. This informs the file-selection, existing-download and bandwidth proposals.

The [Radarr settings guide](https://wiki.servarr.com/radarr/settings) and [Sonarr quick-start guide](https://wiki.servarr.com/sonarr/quick-start-guide) are references for quality choices and imports. Their workflows inspire proposals; PlexPort does not provide all of their automation.

[Plex's TV naming guide](https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/) informs episode naming. [Tautulli's notification guide](https://docs.tautulli.com/using-tautulli/notification-agents-guide) is a reference for notification channels and conditions; no Tautulli integration is included.

[Suggest an improvement](https://github.com/Tufein/PlexPort/issues/new?template=idee.yml).
