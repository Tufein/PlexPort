# Install PlexPort on TrueNAS

[Back to the main page](../README.md)

This guide is for **TrueNAS 25.10**. qBittorrent and Plex should already be working. Initial setup needs some folder settings; after that you control PlexPort in your browser or on Android. The app's buttons currently have Dutch labels, shown alongside their English meaning below.

## 1. Gather three things

| What you need | Where to find it | Example |
|---|---|---|
| Your NAS address | The address you use to open TrueNAS in your browser | `192.168.1.100` |
| The download folder | Your qBittorrent app's storage settings | `/mnt/tank/downloads` |
| The movie and TV folders | The folders used by your Plex libraries | `/mnt/tank/media/Movies` and `/mnt/tank/media/Series` |

These are examples, not values to copy without checking. **Capital letters matter:** `Movies` and `movies` can be different folders. Do not create an empty replacement folder if your media is already stored elsewhere.

## 2. Download and place PlexPort

[Download the app files](https://github.com/Tufein/PlexPort/archive/refs/heads/main.zip) and extract them. Place them in a separate app folder on your NAS. Keep settings in a separate folder so you can retain them during updates.

This is the one-time technical step: [follow the folder layout and installation example](../INSTALLATIE-TRUENAS.md#folders-and-app-user). It explains which folders to connect and which user needs access.

## 3. Install in TrueNAS

1. Open **Apps** in TrueNAS and choose the option to install a custom app using YAML. Here, YAML is the text file containing the app's settings.
2. Use `compose.yaml` from the extracted folder. Adjust the example addresses, folders and app user using the [installation guide](../INSTALLATIE-TRUENAS.md#install-plexport).
3. Enter your own PlexPort password under `PLEXPORT_PASSWORD` and save.
4. Wait until the app shows **Running**.

## 4. Open PlexPort

Open `http://YOUR-NAS-ADDRESS:8765` in your browser, replacing `YOUR-NAS-ADDRESS` with your own address. Sign in as **admin** with the PlexPort password you just chose.

Open **Instellingen (Settings)**:

1. Choose qBittorrent and enter its Web UI address and login details.
2. Enter the download, movie and TV folders as described in the installation guide.
3. Click **Alles controleren (Check everything)**. Fix any reported problems before starting a download.
4. Add a search source and save. You can also add your own link without a search source.

[Continue with your first download](GEBRUIKEN.md).

## Updating

Stop PlexPort, keep the existing settings folder and replace only the app files in the code folder. Start PlexPort again and click **Alles controleren (Check everything)**. You do not need to remove settings, tasks or media. Android loads the interface from the server, so these website improvements do not require a new APK.

Seeing `EFAULT`? [Read the troubleshooting guide](HULP.md#truenas-shows-efault-or-the-app-wont-start).
