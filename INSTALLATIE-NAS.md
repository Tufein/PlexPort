# JellyPort on your NAS with qBittorrent

> **Transmission (default):** JellyPort defaults to Transmission via its RPC address, for example `http://192.168.1.75:9091/transmission/rpc`. Choose **Transmission** under Downloader, enter your Transmission username and password if RPC authentication is on, and set the download folder as Transmission sees it plus the same folder as JellyPort sees it (for example `/Home/Downloads`). Transmission may require JellyPort's host in its RPC whitelist. qBittorrent is still supported and the steps below that mention it still apply to it; existing qBittorrent tasks keep working.

This setup uses your existing qBittorrent and Jellyfin. JellyPort runs in its own Docker container on the NAS.

For **TrueNAS 25.10 Goldeye**, use the dedicated [TrueNAS guide](INSTALLATIE-TRUENAS.md) with `compose.yaml`. `compose.truenas.yaml` is an equivalent alias. That setup uses explicit NAS paths and can be installed through **Install via YAML**; it does not use `.env`.

The following steps are for other NAS systems or a local Docker build using **compose.build.yaml**.

## 1. Put the app on your NAS

Copy the entire **JellyPort** folder to a location your NAS Docker or Container Manager can access.

## 2. Fill in the Docker settings

Copy `.env.example` to `.env` and set:

| Setting | What to enter |
|---|---|
| `JELLYPORT_PASSWORD` | Your chosen JellyPort login password |
| `QBITTORRENT_URL` | Your existing qBittorrent Web UI, such as `http://192.168.1.20:8080` |
| `QBITTORRENT_DOWNLOAD_ROOT` | The download folder as qBittorrent sees it |
| `DOWNLOADS_PATH` | The full NAS path to that same download folder |
| `MEDIA_PATH` | The full NAS path to the Jellyfin media folder |

These addresses are examples, not configured servers. Use your own addresses and folders.

Example for a NAS with storage under `/volume1`: qBittorrent runs in a container and sees `/downloads`, mounted from `/volume1/downloads`. Set `QBITTORRENT_DOWNLOAD_ROOT=/downloads` and `DOWNLOADS_PATH=/volume1/downloads`. JellyPort sees those files under `/downloads`.

With `MEDIA_PATH=/volume1/media`, JellyPort uses `/media/Movies` and `/media/TV Shows`. Jellyfin must read the same NAS folders as libraries. If your existing movie folder has another name, adjust it in **Instellingen (Settings)** in the app.

Make sure the folders exist and the container has write access. A NAS container manager can assign a user or group with access; if necessary, add `user: "UID:GID"` to `compose.build.yaml`. The app also needs write access to its `data` folder.

## 3. Start the Docker project

Create a project in your NAS container manager using **compose.build.yaml**, with this folder as the project folder. Alternatively, run this from that folder:

```sh
docker compose -f compose.build.yaml up -d --build
```

Open **http://YOUR-NAS-ADDRESS:8765** in your browser. Sign in as **admin** with the password from `.env`.

## 4. Connect qBittorrent and Jellyfin

Open **Instellingen (Settings)**:

1. Choose qBittorrent and enter your existing Web UI username and password.
2. Check the downloader's download folder and JellyPort's download folder. The second path is `/downloads` in this setup.
3. Click **Opslaan & verbinding testen (Save & test connection)** and **Opslaan & mappen controleren (Save & check folders)**.
4. Enter the Jellyfin address and API key (Dashboard → API Keys). Click **Opslaan & Jellyfin testen (Save & test Jellyfin)** and enter the correct movie and TV library IDs. Save again.
5. Add WatchSoMuch directly with **WatchSoMuch toevoegen (Add WatchSoMuch)**, or connect Torznab sources through Prowlarr or Jackett. Save settings. You can already use magnet links and torrent files without a search source.

Do not use `localhost` for qBittorrent or Jellyfin running in a different container. Use the NAS IP and published port, or a container name when both containers share a Docker network.

## 5. Your first download

Click **Download toevoegen (Add download)**, enter a title, choose **Film (Movie)** or **Serie (TV show)**, and paste a magnet link or select a torrent file. Follow progress under **Downloads**. Once the video is complete, JellyPort imports it to the movie or TV folder and requests a Jellyfin library scan if configured.

Multi-episode TV downloads need episode codes such as `S01E01` in filenames. Check the title for Jellyfin when choosing a search result: a release name is not always the correct title.

## Maintenance

- Keep the container running to process new downloads automatically.
- Back up `data/jellyport.sqlite` and `.env`; they contain local settings and credentials.
- Stop with `docker compose -f compose.build.yaml down`. Downloads and imported media are preserved.
- On an error, fix the connection or folders and click **Opnieuw proberen (Retry)**.

The Docker setup is provided as an example. Verify the actual connections to your NAS, qBittorrent and Jellyfin with the checks above.
