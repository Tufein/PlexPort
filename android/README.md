# PlexPort for Android

This Android app opens your existing PlexPort server on a NAS. Sources, qBittorrent, download statuses and Plex settings come from the same server as the website. Your phone does not run a torrent downloader.

For a simple walkthrough, see [Install on Android](../docs/START-ANDROID.md). The current native and website interfaces use Dutch labels. Version 1.2 adds a refreshed sign-in card with clear labels, a password visibility toggle and matching light and dark colors.

## Install and use

You can download the APK on your phone through **PlexPort → Instellingen → Android-app downloaden (Settings → Download Android app)**.

1. Put `dist/PlexPort-1.2.0.apk` on your Android phone and open it. If Android asks, allow installation from that browser or file app.
2. Connect to the same home network as your NAS, or a VPN that can reach it.
3. Open **PlexPort** and enter your own server address. The public build suggests `http://truenas.local:8765/`; use your NAS IP if your network does not resolve that name. Change it later through **Menu → NAS-adres wijzigen (Change NAS address)**.
4. Sign in as `admin` with your existing **PlexPort password**, not your qBittorrent or TrueNAS password.

The app saves only the NAS address. Your password stays in memory for the app session and is needed again after closing the app. **Menu → Afmelden (Sign out)** ends the session. A new session checks your credentials on the server before loading the website. Android's back button navigates within the website; the app closes when there is no previous page. Rotation preserves the current page and form.

The app follows the system light or dark theme. PlexPort also lets you choose a website theme, saved per device. `.torrent` files can be selected with Android's normal file picker; no broad storage permission is required.

Install this APK over the previous version to keep the saved server address. It has the same signing certificate and a higher version code.

## Scope and protections

- Supports Android 8.0 and newer: minimum API 26, compile and target API 36. The only manifest permission is `INTERNET`.
- Local HTTP is allowed for NAS installations. HTTP does not encrypt login details; use it within your trusted home network or VPN. HTTPS with a valid certificate is also supported.
- Only the configured HTTP(S) address, with the same protocol, hostname and port, can load inside the app. External websites, other ports, `file:`, `content:` and intent links are blocked.
- Local WebView file and content access, JavaScript-to-native bridges, third-party cookies, geolocation, extra windows and unsolicited device permissions are disabled. JavaScript is required for PlexPort controls.
- HTTPS certificate errors are rejected. The app does not provide a bypass.
- The native login check sends a read request to `/`, uses connection and read timeouts, and does not follow redirects. The PlexPort server restricts scripts, images and network requests through its Content Security Policy. Android's resource check sees only the initial resource URL during redirects; use this client for your own PlexPort server.
- Downloads stay on your NAS or Mac according to existing PlexPort settings. Android does not run a download process or background service. The NAS must remain reachable.

## Build again

Use JDK 17 or newer, Android SDK platform 36, and build-tools 35.0.0 or 36.0.0. Set `JAVA_HOME` and `ANDROID_HOME` for your installation. Gradle 8.13 and Android Gradle Plugin 8.13.2 are pinned; the Gradle download has a SHA256 check.

From this folder:

```sh
./build-apk.sh
```

This runs URL security unit checks and release lint, then builds a signed release APK in `dist/PlexPort-1.2.0.apk`. The filename follows the version in `app/build.gradle`. Its `.apk.sha256` file is refreshed on each build. Copy the new APK to `plexport/static/plexport.apk` in your NAS code folder to update the website download. For a development build, use `./gradlew assembleDebug`.

Your first release build creates a signing key in **`android/.signing/plexport-release.jks`**, with private settings in **`android/.signing/signing.properties`**. Later builds reuse it; they do not replace or regenerate it. Back up the entire `.signing` folder securely: Android accepts updates only with the same signing key. The folder has restricted permissions and is excluded by `.gitignore`. Never share or publish it. If only one of the two files exists, the build stops to avoid creating a different key accidentally.

The supplied APK is a release build with Android debugging disabled. It is signed for this project and is not published on Google Play. Future updates need the same signing key and a higher `versionCode`. The project's private key is not included: your own builds get their own signature and cannot replace the project's published APK directly.

## Official Android sources

The WebView follows Android guidance for [file access](https://developer.android.com/privacy-and-security/risks/webview-unsafe-file-inclusion), [HTTP authentication](https://developer.android.com/reference/android/webkit/HttpAuthHandler), [TLS errors](https://developer.android.com/reference/android/webkit/WebViewClient#onReceivedSslError(android.webkit.WebView,%20android.webkit.SslErrorHandler,%20android.net.http.SslError)) and [website dark mode](https://developer.android.com/develop/ui/views/layout/webapps/dark-theme). Build versions follow the [AGP 8.13 compatibility table](https://developer.android.com/build/releases/agp-8-13-0-release-notes) and [Android 16 SDK setup](https://developer.android.com/about/versions/16/setup-sdk). Also see [cleartext traffic](https://developer.android.com/privacy-and-security/security-config#CleartextTrafficPermitted) and [APK signing](https://developer.android.com/tools/apksigner).
