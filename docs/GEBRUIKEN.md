# Add your first movie or TV show

[Back to the main page](../README.md)

The app currently uses Dutch labels. This guide includes the labels you will see and their English meaning.

## First: is everything ready?

Open **Instellingen → Alles controleren (Settings → Check everything)**. PlexPort checks your downloader and the folders where files should go. If you configured automatic Plex scanning, it also tests that connection.

The checklist on **Overzicht (Overview)** shows what still needs setting up. Adding a source lets you search it; it does not guarantee that its website will always be reachable.

## Search and choose a version

1. Open **Ontdekken (Discover)**, choose **Films (Movies)** or **Series (TV shows)** and search for a title.
2. Choose a quality if needed: **Full HD** is 1080p, **4K** is 2160p and **HD** is 720p. The app reads this from the release name; it does not inspect video quality.
3. Set a maximum size to save space. Results without a known size are excluded when a size limit is set.
4. Use the minimum sharing count to find versions with people currently sharing them. More seeders may help, but do not guarantee speed.
5. Click **Kiezen (Choose)** beside the version you want.

## Check before starting

Check the title and year. For a single TV episode, you can enter the season and episode. A season pack needs episode codes such as `S01E01` in its filenames.

Under **Voor je start (Before you start)**, you can see whether the download folder and destination are accessible and how much space is free. When the file size is known, PlexPort blocks a download that would not fit in the download folder. The check does not reserve space; other downloads can use it in the meantime.

Click **Download starten (Start download)**. The task appears under **Downloads**.

## Use your own link or file

Click **Download toevoegen (Add download)**. Paste a magnet or torrent link, or choose a `.torrent` file. Choose **Film (Movie)** or **Serie (TV show)** and enter the title. The size of these manual downloads is not known in advance.

## Follow what happens

| Label in the app | Meaning |
|---|---|
| **Download voorbereiden** | Preparing: the downloader is fetching file information. |
| **Wacht op een vrije plek** | Waiting for a slot: other tasks are running first. |
| **Wacht op delers** | Waiting for seeders: no data is arriving. This may be temporary. |
| **Bestanden controleren** | Checking files: PlexPort waits for the downloader to finish checking. |
| **Bestanden verplaatsen** | Moving files: PlexPort waits for the downloader to finish moving them. |
| **Importeren** | Importing: completed videos are being placed in your media folder. |
| **Geïmporteerd** | Imported: files are in your configured media folder. |
| **Aandacht nodig** | Needs attention: read the message, fix the problem and choose **Opnieuw proberen (Retry)**. |

Under **Downloads**, you can search by name or filter for active tasks, problems or imported media.

## Watch in Plex

Movies and shows appear in Plex once it has scanned the media folders and identified the title. With a configured Plex connection, PlexPort requests that scan. Under **Bibliotheek (Library)**, you can also choose **Plex laten scannen (Ask Plex to scan)**, or refresh the library directly in Plex.

Original downloads stay in place for sharing. PlexPort does not automatically delete them.
