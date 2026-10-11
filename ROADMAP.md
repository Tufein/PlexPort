# What's next?

[Back to the main page](README.md) · [What's already available?](CHANGELOG.md)

## Available now

Simple setup guides, connection and folder checks, download version filters, download search, and clearer explanations when a task is waiting. Dark mode, Android, qBittorrent, Transmission and media-folder imports are also available.

The GitHub documentation is now in English. The app interface still uses Dutch labels.

## Next improvements researched

These ideas have been researched but are not built yet. No delivery dates are promised.

| Idea | How it helps | What needs to work first |
|---|---|---|
| **Import an existing qBittorrent download** | Organize files downloaded outside PlexPort in Plex too. | Verify file paths, avoid duplicate imports and let you confirm the title. |
| **Save a preferred quality** | Avoid choosing Full HD, 4K or a maximum size every time. | Explain why a version matches and allow a choice when quality is unknown. |
| **Choose episodes from a season** | Download only what you still need. | Wait for file information, track selected files and verify episode numbers. |
| **Show when extra storage is needed** | Understand whether an import saves space or requires a copy. | Test actual hardlink support; the same disk or folder name is not proof. |
| **Guided TrueNAS setup** | Fewer folder settings and fewer incorrect mounts. | Preserve existing datasets, permissions and media without creating empty replacement folders. |
| **English app interface** | Use PlexPort without learning Dutch button labels. | Translate controls, status messages and errors consistently, while preserving settings and download behavior. |

## Research sources

The [official qBittorrent API documentation](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29) describes separate download states, file selection and control of existing torrents. These support clearer progress and controlled file choices.

The [Sonarr quick-start guide](https://wiki.servarr.com/sonarr/quick-start-guide) describes quality preferences and hardlinks where storage supports them. These offer useful ideas for PlexPort, with attention to clear choices and existing media folders.

[Suggest an improvement](https://github.com/Tufein/PlexPort/issues/new?template=idee.yml).
