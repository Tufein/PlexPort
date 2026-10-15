# Add your first movie or TV show

[Back to the main page](../README.md)

The app currently uses Dutch labels. This guide includes the labels you will see and their English meaning.

## First: is everything ready?

Open **Instellingen → Opslaan & controleren (Settings → Save & check)**. PlexPort saves your settings, then checks your downloader and the folders where files should go. If you configured automatic Plex scanning, it also tests that connection. Individual test buttons remain available. Changes to sources or unchanged settings preserve unrelated successful checks.

The checklist on **Overzicht (Overview)** shows what still needs setting up. Adding a source lets you search it; it does not guarantee that its website will always be reachable.

## Search and choose a version

1. Open **Ontdekken (Discover)**, choose **Films (Movies)** or **Series (TV shows)** and search for a title.
2. Choose a quality if needed: **Full HD** is 1080p, **4K** is 2160p and **HD** is 720p. The app reads this from the release name; it does not inspect video quality.
3. Set a maximum size to save space. Results without a known size are excluded when a size limit is set.
4. Use the minimum sharing count to find versions with people currently sharing them. More seeders may help, but do not guarantee speed.
5. Expand the title's download versions and click **Kiezen (Choose)** beside the version you want. Matching titles with reliable year and episode information share a card; remakes, different episodes and uncertain identities remain separate.

## Search with part of a title

Use `*` for zero or more characters, or `?` for one character. Examples: `Star*`, `*Nosferatu*`, or `Star?Wars`. Matching ignores capitalization and common release separators such as dots and underscores. Use at least two letters or digits in one literal part of a source query; `*` alone is too broad. The same patterns work under **Zoek in je downloads (Search your downloads)**.

PlexPort sends a useful text part to your sources, then checks their returned titles against your pattern. It searches the results those sources return, rather than their entire catalogs. A broad query can miss titles because sources limit results; add more of the title if needed. Ordinary title searches keep their existing behavior. WatchSoMuch searches free words from a word beginning and can interpret some names as actor filters. A fragment from the middle of a word may therefore return nothing. Start with a recognizable word or the beginning of a title when a broad pattern finds no matches.

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

Under **Downloads**, use the tabs for **Onderweg (Active)**, **Gestopt (Stopped)**, **Aandacht nodig (Needs attention)** or **Geïmporteerd (Imported)**, or select all tasks. The same name search applies to each view. Imported files remain visible if sharing is stopped or a Plex scan needs attention.

## Stop or remove a download

Choose **Stoppen (Stop)** beside a task to stop downloading or sharing and pause its automatic import. The task stays in your list; **Hervatten (Resume)** continues it later. An import already in progress finishes before Stop can take effect.

Choose **Verwijderen (Remove)** to open the cleanup dialog. By default, PlexPort removes the task and its torrent from your downloader and keeps downloaded files. Select **Ook downloadbestanden wissen (Also delete download files)** to erase the downloader's files too. Confirm with **Verwijderen**, or choose **Behouden (Keep)** to cancel. This file deletion cannot be undone. Files already published into your Plex media folder stay in place; the removed task disappears from the PlexPort library view.

If the downloader is unavailable, choose **Alleen uit PlexPort (Only from PlexPort)**. This stops PlexPort tracking and importing that task; the torrent and files remain in the downloader, where downloading or sharing can continue. A task still being created by the downloader may need a moment before normal Stop or Remove is available.

## Watch in Plex

Movies and shows appear in Plex once it has scanned the media folders and identified the title. With a configured Plex connection, PlexPort requests that scan. Under **Downloads → Geïmporteerd (Imported)**, you can also choose **Plex laten scannen (Ask Plex to scan)**, or refresh the library directly in Plex. Existing links to the former Library screen open the imported view.

Original downloads stay in place for sharing. PlexPort does not automatically delete them.

## Recognize titles by their posters

The overview, downloads, library and search results show posters when WatchSoMuch has an unambiguous title match. Enter the film's release year to distinguish remakes with the same name. A small **Bron (Source)** link identifies each poster's source. If no matching poster is available, a film or TV icon appears instead; downloading and importing continue normally.

Images need Internet access from the PlexPort server. The server sends the title and movie/TV category to WatchSoMuch and caches the returned image, including for downloads from another source. It does not send passwords or torrent links. You do not need a separate account or API key. The Android app displays the same posters after updating the server. Cover images illustrate the title; they do not verify the contents of a torrent.

## Searching by actor

In **Ontdekken (Discover)**, choose **Op acteur (By actor)** and enter a name, for example `Tom Hanks`. PlexPort shows films whose cast list includes that name, with the first cast members next to each version. This needs a WatchSoMuch source under **Instellingen (Settings)**. It shows at most the first eight matching titles that WatchSoMuch returns, so a very long filmography can be incomplete; add a year or search by title for a specific film.

## Check before starting

The add-download window compares the chosen title with current PlexPort tasks. It does not inspect your full Plex library. Open a matching task or tick **Toch met deze versie doorgaan (Continue with this version)** to intentionally add another version. An identical torrent remains blocked. Different known movie years and episodes remain separate; incomplete information produces a cautious warning.

The same window tests whether the configured folders can reuse the downloaded file or need a second copy. For a known size it estimates extra media space, including both copies when storage is shared. An unknown method or unknown file size is shown explicitly. Space is not reserved, and other downloads can change what is available.

## Choose episodes and subtitles

For a new TV task, enable **Zelf afleveringen en bestanden kiezen (Choose episodes and files)** before starting. Your downloader fetches file information; it may already contact peers and receive data. Once metadata is ready the torrent waits for your choice, and PlexPort does not import anything yet.

In Downloads, choose **Afleveringen kiezen (Choose episodes)**. Select at least one supported video and explicitly select any matching subtitles. Check original filenames and episode numbers. A video containing several episodes stays one file and is never split. **Keuze opslaan en downloaden (Save selection and download)** applies the selection to this task's torrent. Only selected files that have completed can be imported. **Later kiezen (Choose later)** keeps the import waiting.

If metadata changes, reload the file list and confirm again. Stopping, restarting or retrying a task retains the saved selection. Downloads created before this opt-in keep their existing behavior.
