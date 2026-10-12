# Next feature proposals

[Roadmap](../ROADMAP.md) · [Developer handoff](../CLAUDE.md) · [Technical guide](TECHNISCH.md)

These are proposed implementation briefs, not available features. Website 1.5 already includes saved search preferences and wildcard search, so those do not need rebuilding. The priorities below come from an audit of the current code and its NAS, downloader and Plex workflow. External tools inform the ideas; the acceptance criteria are proposals for PlexPort.

## 1. Warn before downloading a title again

**User outcome:** choosing a second version of a film shows “This title is already in your downloads” or “This title has already been imported,” with a link to that task and an explicit choice to continue.

**Current behavior:** `server.py` rejects an identical download fingerprint. It does not recognize the same film supplied through another link or release. `publish_file()` protects existing destination files, but that happens after a download and is not a useful early warning.

Acceptance criteria:

- Compare existing PlexPort tasks first. State clearly that this checks PlexPort history, not the full Plex library.
- Match a movie using its confirmed library title and year. Treat different known years as different films. Missing years or ambiguous titles produce a cautious warning, never a claim of certain identity.
- Match TV episodes using title, year where known, season and episode. A match for another episode must not prevent adding this one. Season packs need a separate explanation rather than being equated with one episode.
- Show the matching task's state, and distinguish an active download from a previous import. Removed tasks are outside the current history; do not claim otherwise.
- Require a clear “Continue with this version” choice for a title warning. Keep the existing hard rejection of an identical download; an override must not bypass fingerprint protection.
- Check again when creating the task, inside the worker lock, so a second browser cannot silently bypass the warning. Do not change existing torrent locations or overwrite library files.

Validation: test capitalization and spacing, different years, missing years, separate episodes, season packs, active/stopped/imported tasks, two simultaneous submissions and an identical fingerprint with an override. Test the warning and cancellation on narrow screens and with keyboard navigation. Existing downloads and files must remain unchanged.

[Radarr's settings documentation](https://wiki.servarr.com/radarr/settings) provides a reference for identifying and choosing movie versions. The warning and override described here are a proposed PlexPort flow.

## 2. Explain when importing needs a second copy

**User outcome:** before starting a known-size download, show either “Your media can reuse the downloaded video” or “Importing may need about X GB extra,” with a simple explanation. A missing check displays “Import method unknown.”

**Current behavior:** `storage_report()` tests write access and current free space. `publish_file()` tries a hardlink and falls back to a copy when necessary. The current preflight does not establish whether hardlinks between the actual download and destination folders work.

Acceptance criteria:

- Probe the configured download folder and the selected movie or TV destination using a uniquely named temporary file and a real link attempt. Do not infer support solely from disk names, mount paths or device IDs.
- Remove every probe file even when linking, reading or cleanup fails. Never create missing media roots, change ACLs or alter user media. Return a separate capability result so an optional failed link check does not masquerade as a failed downloader connection.
- Report hardlink support as a current observation, not a permanent guarantee. Filesystem boundaries, dataset quotas, permissions and later configuration changes can affect the final import.
- If copying is required and the download size is known, explain the estimated additional media space while originals stay available for seeding. For manual links or unknown sizes, show an unknown estimate rather than zero.
- Avoid misleadingly adding two independent free-space readings when download and media folders share the same storage. A shared-filesystem copy can require room for both the download and its second copy; quotas may still differ.
- Recheck before importing and keep the existing copy-time space protection. Preflight never reserves space. Keep published Plex media intact if a later check fails.
- Use plain language in the main interface, with hardlink details available in a short explanation.

Validation: use temporary files to test successful links, cross-filesystem errors, unsupported linking, permissions failures, unknown sizes, insufficient space, cleanup after an exception and a folder disappearing between checks. Mock filesystem failures; do not change live NAS datasets for automated tests.

The [Sonarr quick-start guide](https://wiki.servarr.com/sonarr/quick-start-guide) is a reference for hardlinks and completed-download imports. The proposed probe and storage explanation must be verified against PlexPort's actual mounted folders.

## 3. Choose files and episodes from a season download

**User outcome:** after torrent metadata becomes available, show recognizable episodes with checkboxes. The user can select the episodes they need and see which files will be imported.

**Current behavior:** the integrations read torrent file metadata, and `import_media()` recognizes episode codes such as `S01E01`. PlexPort does not expose an episode-selection step. Adding file selection must not make a partially downloaded, unwanted file eligible for import.

Acceptance criteria:

- Start with an explicit opt-in selection workflow. Existing tasks keep their current behavior. Make clear that obtaining magnet metadata may briefly contact peers and cannot promise zero data transfer.
- Wait for metadata before presenting a file list. Keep unavailable, incomplete or changed metadata in a visible waiting/error state; never guess file indices from filenames alone.
- Show episode numbers, original filenames and sizes. Distinguish multi-episode files such as `S01E01E02`, extras and ambiguous names. Do not split a video containing several episodes.
- Persist file identifiers, selected indices and episode mapping with the job. Validate indices against the downloader's current list before applying them. Use the downloader's file-priority API only for this task's torrent.
- Require at least one supported video. Associate subtitles where they can be matched safely; do not turn unrelated files into selected episodes automatically.
- Import only selected supported files that are complete and accessible. Overall torrent progress must not substitute for selected-file completion. Filter both download expectations and the eventual import list consistently.
- Preserve selections through restart, retry and stop/resume. Prevent the worker from importing until the selection has been committed. A failed selection request retains an actionable job instead of starting an unconfirmed import.
- Keep current path-traversal and duplicate-destination checks. Recognized filenames must still meet the existing Plex naming rules.

Validation: test metadata delays, reordered or changed file lists, invalid indices, no selected videos, selected subtitles, multi-episode files, partial unwanted files, completion of selected files, client rejection and restarts during selection. Use local downloader fixtures and temporary media; add a controlled end-to-end check with permitted test media before declaring NAS or Android support complete.

The [qBittorrent API reference](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29) documents torrent contents and file priorities. [Plex's TV naming guide](https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/) documents episode naming. Supporting Transmission requires its own verified equivalent; do not silently offer controls that only one client supports.

## Later work

The [roadmap](../ROADMAP.md) also tracks importing existing downloads, optional completion/problem notifications, English interface text, guided TrueNAS setup and individual bandwidth limits. Each needs a separate implementation and verification brief before claiming it is available.
