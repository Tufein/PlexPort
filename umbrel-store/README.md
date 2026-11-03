# JellyPort for Umbrel (community app store)

Copy the contents of this folder to the root of a separate public Git repository
(for example `Tufein/umbrel-apps`), then in Umbrel: **App Store → ⋯ → Community App Stores →
add the repository URL**.

Before installing:

1. Publish the image: run the **Publish container image** workflow once (Actions tab) and make
   the `jellyport` package public (GitHub → Packages → Package settings).
2. Check the volume paths in `tufein-jellyport/docker-compose.yml`. They are an assumption:
   `/downloads` must be the folder your downloader (for example Umbrel's Transmission) writes to,
   and `/media/Movies` and `/media/TV Shows` must be folders your Jellyfin library reads.
3. In JellyPort Settings, use the downloader address reachable from this container and the
   same paths as above.

Not tested on a real Umbrel.
