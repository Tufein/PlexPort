# PlexPort help

[Back to the main page](../README.md)

## Where do I start when something isn't working?

Open **Instellingen (Settings)** and click **Alles controleren (Check everything)**. Read the message beside the downloader or affected folder. Fix that part and check again.

## TrueNAS shows EFAULT or the app won't start

`EFAULT` is a general error. Often a folder setting points to a folder that does not exist, perhaps because of a different capital letter. Check the full paths in your installation file against your actual storage folders.

Do not create an empty replacement movie folder: the app needs to see your existing media. If the problem continues, an administrator can read `/var/log/app_lifecycle.log` in the TrueNAS Shell. The latest entry for `plexport` usually explains the cause. [More TrueNAS details](../INSTALLATIE-TRUENAS.md#tools-and-troubleshooting).

## The download is complete, but PlexPort cannot see the files

Your downloader and PlexPort must see **the same download files**. Matching folder labels on screen do not prove they use the same storage. Check both apps' folder mounts. In the TrueNAS example, both see the shared download folder as `/downloads`.

Then choose **Opnieuw proberen (Retry)** on the task. Do not switch downloaders after a task has already been submitted.

## Waiting for seeders: is my download broken?

Not necessarily. No data is arriving right now. Wait a little and check the connection in your downloader. If a task keeps waiting, you can choose another version with more seeders. PlexPort does not speed up torrents itself.

## There is not enough free space

Choose a smaller file or free space on the affected storage. Only remove files you know you no longer need. If downloads and media are on different storage, importing may require an extra copy.

A successful space check is a snapshot. Manual links have no known size in advance, and other tasks can use space in the meantime.

## I cannot see the media in Plex

First check **Bibliotheek (Library)** in PlexPort. If the task is marked as imported, ask Plex to scan its library. Also check that Plex reads the same physical movie and TV folders and that the title is correct.

A scan request means Plex accepted the request, not that it has already identified the title.

## A season pack reports missing episode numbers

Filenames must identify each episode, for example `S01E01`. You can enter the numbers yourself for a single episode. A pack with unknown episode numbers is not renamed blindly.

## The Android app cannot connect

Use the **PlexPort address**, including `:8765` if you use the default port. Sign in with your PlexPort password. Check that your phone is on the same network and that the server is running. The suggested `truenas.local` only works if your network recognizes that name; otherwise use the IP address.

## I want to report a problem

[Open the problem form](https://github.com/Tufein/PlexPort/issues/new?template=probleem.yml). Include your device, what you did and the message you see. **GitHub is public:** do not share passwords, tokens, complete settings files or unfiltered logs.
