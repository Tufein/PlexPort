# PlexPort on TrueNAS

Install PlexPort as a custom app through **Apps → Discover Apps → Install via YAML**. qBittorrent and Plex run as separate apps on the same NAS. `compose.yaml` and `compose.truenas.yaml` are identical examples; replace the addresses, dataset paths and user with those for your NAS.

## Folders and app user

The example uses `192.168.1.100`, pool `tank` and UID/GID `3000:3000`. These are example values. Create the app, data and download folders beforehand, and use the exact spelling of your existing movie and TV folders.

| Purpose | Example TrueNAS path | PlexPort container | qBittorrent container |
|---|---|---|---|
| App code | `/mnt/tank/media/Movies/.plexport-app/code` | `/app` | — |
| Settings and tasks | `/mnt/tank/media/Movies/.plexport-app/data` | `/data` | — |
| Downloads | `/mnt/tank/media/Movies/.plexport-downloads` | `/downloads` | `/downloads` |
| Movies | `/mnt/tank/media/Movies` | `/media/Movies` | — |
| TV shows | `/mnt/tank/media/Series` | `/media/TV Shows` | — |

Both download mounts must point to **the same physical folder**. Use a host path for downloads in the qBittorrent app. Both app users need read and write access there. Plex needs read access to the movie and TV folders. Preserve existing dataset ACLs and adjust access for the chosen app users.

Place this repository's contents in the code folder, with `plexport` directly inside `code`. If downloads and app files sit inside the movie folder, add these entries to `.plexignore` in that movie folder:

```text
.plexport-downloads/*
.plexport-app/*
```

## Install PlexPort

1. Adjust every example path and NAS address in `compose.yaml`. Check that `user: "3000:3000"` matches a user with access to your datasets.
2. Set your own `PLEXPORT_PASSWORD`. A network server will not start without an app password. Preserve an existing password during updates.
3. Install through the Apps web interface with the name `plexport`, save the YAML and wait for **Running**.
4. Open `http://YOUR-NAS-ADDRESS:8765` and sign in as `admin` with your PlexPort password.

The YAML uses the official Python container and does not require a local Docker build. `create_host_path: false` makes an incorrect folder mount fail instead of creating an unexpected empty folder. Keep the `data` folder during updates: it contains settings and tasks. Run only one PlexPort instance against the same tasks.

## Connect qBittorrent

Enable the qBittorrent app's Web UI and set its default download folder to `/downloads`. Use the same container path in PlexPort. Automatic torrent management is disabled for PlexPort tasks; preferably avoid a separate temporary download folder.

Open **PlexPort → Instellingen (Settings)**:

| Setting | Value |
|---|---|
| Downloader | qBittorrent |
| Server address | `http://YOUR-NAS-ADDRESS:30024` or your Web UI port |
| Username and password | Your qBittorrent Web UI login |
| Download folder as seen by the downloader | `/downloads` |
| Same folder as seen by PlexPort | `/downloads` |
| Movie folder | `/media/Movies` |
| TV folder | `/media/TV Shows` |

Click **Opslaan & verbinding testen (Save & test connection)** and **Opslaan & mappen controleren (Save & check folders)**. With an existing database, changed YAML values do not automatically replace saved settings; update the settings form too. If your qBittorrent already intentionally permits access without login on the app network, leave the downloader username blank. The example does not disable authentication.

New tasks added through PlexPort get their own subfolder in `/downloads`. Completed videos and subtitles are imported to your movie or TV folder. Originals remain available for seeding. Imports use hardlinks where possible; otherwise a copy uses extra disk space. Torrents added directly to qBittorrent do not get automatic PlexPort imports.

## Plex and sources

Enter your Plex server address and token, test Plex, then save the movie and TV library IDs. Plex must read the same physical media folders, although its container paths may have different names. Files are imported even without an API token; use automatic or manual Plex scanning in that case.

Under **Jouw bronnen (Your sources)**, add WatchSoMuch directly or configure a Torznab source through Prowlarr or Jackett. Check the title, year and episode numbers before starting a download.

## Android and appearance

Download the APK through **Instellingen → Android-app downloaden (Settings → Download Android app)**, or use `android/dist/PlexPort-1.1.0.apk`. Android 8 or newer is supported. Enter your own PlexPort server address; sources and tasks come from that server. The website offers System, Light and Dark appearance options, currently labeled **Systeem**, **Licht** and **Donker**. See the [Android instructions](android/README.md).

## Tools and troubleshooting

- `tools/diagnose_qbittorrent.py` reads selected app settings, mounts, permissions and filtered logs without changing settings.
- `tools/repair_qbittorrent_owner.py` repairs only the checked qBittorrent app's configuration after a UID change, with a backup. Adjust the expected download path for your installation before using it.
- `tools/connect_nas_qbittorrent.py` connects an existing PlexPort installation, backs up the Compose configuration and database, and checks the connection and shared write access. Adjust `BASE`, `DOWNLOADS` and `URL` for your setup.
- `tools/truenas_icon.py` provides a reversible icon adjustment specifically for TrueNAS **25.10.7**. It uses app metadata outside the supported icon API. Use it only on this version; `--restore` restores the original icon.

These NAS tools run in the **TrueNAS host shell** as an administrator. Their backups contain local settings and must not be uploaded to GitHub. Diagnostics are read-only; the other tools change only the described app configuration.

For `[EFAULT] Failed up action`, `/var/log/app_lifecycle.log` shows the actual cause. A missing bind path needs the correct existing path, not an empty replacement media folder. Configuration errors after a UID change can come from old file ownership. Existing torrents are not automatically moved between downloaders: check the original client and files before resuming a task.

Sources: [TrueNAS custom apps](https://apps.truenas.com/managing-apps/installing-custom-apps/), [qBittorrent Web UI API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-5.0)), [Plex folder exclusions](https://support.plex.tv/articles/201381883-special-keyword-file-folder-exclusion/).
