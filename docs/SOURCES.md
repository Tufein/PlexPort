# Search sources

[Main page](../README.md) · [Using PlexPort](GEBRUIKEN.md) · [Technical guide](TECHNISCH.md)

PlexPort searches the sources you enable under **Instellingen → Jouw bronnen (Settings → Your sources)**. Add a source and save your settings. Searching reads listings and metadata; a download starts only after you choose a version and confirm it. Source availability, metadata and seed counts can change.

| Source | Search category | Setup |
|---|---|---|
| [WatchSoMuch](https://watchsomuch.to) | Movies and TV; title and actor search | Add the built-in source; no API key |
| [YTS](https://yts.gg) | Movies; title search | Add the built-in source; no API key |
| [EZTV](https://eztvx.to) | TV; title search | Add the built-in source; no API key |
| Torznab | Movies and TV; title search | Enter your own configured feed URL and API key |

PlexPort uses only sources compatible with the selected movie or TV category. **Op acteur (By actor)** uses WatchSoMuch only; choosing that mode does not turn a title-only source into an actor search. Existing title and wildcard searches remain available, but wildcards filter only the bounded results returned by each provider. They cannot search an entire provider catalog.

## YTS movies

The canonical website is **`https://yts.gg`**. Its [official API documentation](https://yts.gg/api) identifies **`https://movies-api.accel.li/api/v2/`** as the current API base. This is an API migration published by YTS; the old `yts.gg/api/v2/` endpoint reports that migration and may be retired. Do not substitute an unverified mirror or an old `yts.mx` address.

PlexPort searches `list_movies.json` with `query_term`. A movie can have several torrent versions; each retains its own quality, size, seed count and hash. Title, year and IMDb identity describe the movie, while a version's seed count describes that particular torrent. API success does not prove that a torrent can finish downloading.

The API permits public read access without a key and requests reasonable request rates and response caching. It documents `limit` values from 1 to 50, `page`, quality filters and sorting. PlexPort requests only page 1 with at most 50 movies, examines at most 20 versions per movie and returns at most 250 versions. It does not enumerate the catalog.

## EZTV television

The current website is **`https://eztvx.to`**, identified on the [provider's homepage](https://eztvx.to/). Its [official API documentation](https://eztvx.to/api/) describes `api/get-torrents`, with `imdb_id`, `limit` from 1 to 100 and `page` from 1 to 100. It requires no API login or key. The documented API looks up an IMDb show identity; it does not document a free-text title-search parameter.

PlexPort first uses the [TVmaze show-search API](https://www.tvmaze.com/api#show-search) to find matching show names and their IMDb identifiers. It examines at most 50 suggestions and checks at most three matching shows, then requests page 1 from EZTV with at most 100 torrents for each. The combined result is limited to 250 versions. Shows without a usable IMDb identifier are skipped. TVmaze uses fuzzy matching, so an unrelated name is not automatically treated as the requested series. Different shows or years can share a name; check the displayed identity and episode before adding a download.

This bounded lookup can miss older episodes, less common series or results beyond the first page. An empty response means no matching results were returned by these checks. A failed or unavailable provider is reported as a source error; it is not evidence that the title does not exist. Seed counts and availability can change between search and download.

Show-name and IMDb metadata are provided by [TVmaze](https://www.tvmaze.com), whose [API terms](https://www.tvmaze.com/api#licensing) license its data under [CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/). TVmaze attribution links accompany that metadata. This attribution concerns TVmaze data and does not change the license of PlexPort's application code. The TVmaze API documents caching, HTTP 429 handling and a rate limit of at least 20 calls per 10 seconds per IP; PlexPort keeps its lookups bounded and cached.

## Your own Torznab feeds

[Prowlarr](https://wiki.servarr.com/prowlarr) and [Jackett](https://github.com/Jackett/Jackett) can expose Torznab feeds for indexers that you configure. Copy the feed URL and your source manager's API key into PlexPort. Movies use category 2000; TV uses category 5000. An API key is required where your configured feed requires it; PlexPort does not provide one.

Adding a Torznab entry does not install Prowlarr, Jackett or an indexer, create an account, or configure those services. Keep existing downloader addresses, media paths and private keys separate from public source URLs.

## Verification and limits

The provider documentation and public metadata endpoints above were checked on **October 15, 2026**. A read-only YTS query for the openly released film *Sintel* returned its 2010 movie identity and a torrent version. An EZTV lookup for IMDb `2395695` returned TV torrent metadata, including episode identity, hash, size, seeders and publication time. An EZTV IMDb lookup for *Sintel* returned a valid empty JSON response, as expected for a TV source. These checks confirm endpoint access and representative fields, not coverage of every series. TVmaze returned fuzzy name matches, reinforcing the need to validate show names before requesting EZTV results.

Successful YTS and EZTV searches, including valid empty results, are cached in memory for five minutes, with at most 32 search keys. Provider errors are not cached as empty results. A YTS search uses one API request; an EZTV search uses at most one TVmaze request and three EZTV requests. Each request has an eight-second timeout and a four-MiB response limit. Only the fixed official HTTPS API hosts and redirects within the same host are allowed. Returned magnets use a validated torrent hash; provider-supplied trackers, web seeds and arbitrary URL controls are not forwarded.

These checks did not download torrent contents, start a downloader task, create provider accounts or accept account terms. They do not establish that a particular NAS or network can reach every source, or that a torrent has working peers. Use **Opslaan & controleren (Save & check)** and an actual search on your own installation to check current access.
