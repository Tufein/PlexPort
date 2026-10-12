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

## Search with part of a title

Use `*` for zero or more characters, or `?` for one character. Examples: `Star*`, `Harry*Potter`, or `Star?Wars`. Matching ignores capitalization and common release separators such as dots and underscores. Use at least two letters or digits in one literal part of a source query; `*` alone is too broad. The same patterns work under **Zoek in je downloads (Search your downloads)**.

PlexPort sends a useful text part to your sources, then checks their returned titles against your pattern. It searches the results those sources return, rather than their entire catalogs. A broad query can miss titles because sources limit results; add more of the title if needed. Ordinary title searches keep their existing behavior.

## Remember your download choices

After a search, choose your **Beeldkwaliteit (Quality)**, **Maximale grootte (Maximum size)**, **Mensen die delen (Seeders)** and **Volgorde (Order)**, then click **Voorkeuren onthouden (Remember preferences)**. These choices are saved on your PlexPort server. Opening the website or Android app again loads the same preferences; **Mijn voorkeuren toepassen (Apply my preferences)** also retrieves the latest saved choices.

**Alles tonen (Show everything)** temporarily removes the filters without erasing your preferences. You still choose the download yourself. The source filter and search text are not saved. Changes to the other connection settings, running downloads and media folders are not required.

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
| **Gestopt** | Stopped: downloading and automatic processing are on hold until you choose Resume. |
| **Importeren** | Importing: completed videos are being placed in your media folder. |
| **Geïmporteerd** | Imported: files are in your configured media folder. |
| **Aandacht nodig** | Needs attention: read the message, fix the problem and choose **Opnieuw proberen (Retry)**. |

Under **Downloads**, you can search by name or filter for active tasks, problems or imported media.

## Stop or remove a download

Choose **Stoppen (Stop)** beside a task to stop downloading or sharing and pause its automatic import. The task stays in your list; **Hervatten (Resume)** continues it later. An import already in progress finishes before Stop can take effect.

Choose **Verwijderen (Remove)** to open the cleanup dialog. By default, PlexPort removes the task and its torrent from your downloader and keeps downloaded files. Select **Ook downloadbestanden wissen (Also delete download files)** to erase the downloader's files too. Confirm with **Verwijderen**, or choose **Behouden (Keep)** to cancel. This file deletion cannot be undone. Files already published into your Plex media folder stay in place; the removed task disappears from the PlexPort library view.

If the downloader is unavailable, choose **Alleen uit PlexPort (Only from PlexPort)**. This stops PlexPort tracking and importing that task; the torrent and files remain in the downloader, where downloading or sharing can continue. A task still being created by the downloader may need a moment before normal Stop or Remove is available.

## Watch in Plex

Movies and shows appear in Plex once it has scanned the media folders and identified the title. With a configured Plex connection, PlexPort requests that scan. Under **Bibliotheek (Library)**, you can also choose **Plex laten scannen (Ask Plex to scan)**, or refresh the library directly in Plex.

Original downloads stay in place for sharing. PlexPort does not automatically delete them.

## Recognize titles by their posters

The overview, downloads, library and search results show posters when WatchSoMuch has an unambiguous title match. Enter the film's release year to distinguish remakes with the same name. A small **Bron (Source)** link identifies each poster's source. If no matching poster is available, a film or TV icon appears instead; downloading and importing continue normally.

Images need Internet access from the PlexPort server. The server sends the title and movie/TV category to WatchSoMuch and caches the returned image, including for downloads from another source. It does not send passwords or torrent links. You do not need a separate account or API key. The Android app displays the same posters after updating the server. Cover images illustrate the title; they do not verify the contents of a torrent.
