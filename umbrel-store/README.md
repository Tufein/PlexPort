# JellyPort for Umbrel (community app store)

Copy the contents of this folder to the root of a separate public Git repository
(for example `Tufein/umbrel-apps`), then in Umbrel: **App Store → ⋯ → Community App Stores →
add the repository URL**.

Before installing:

1. Publish the image: run the **Publish container image** workflow once (Actions tab) and make
   the `jellyport` package public (GitHub → Packages → Package settings).
2. The compose file assumes Umbrel's Transmission (`http://umbrel.local:9091/transmission/rpc`,
   downloads in `/downloads`), films in `/downloads/movies` (mounted as `/media/Movies`) and
   series in `/downloads/tv` (create it yourself). The Jellyfin library must read those folders.
3. In JellyPort Settings, enter your Transmission login and set the movie folder to
   `/media/Movies`. Check that Transmission downloads to a folder other than `movies`, so
   Jellyfin does not see the same file twice.

Not tested on a real Umbrel.
