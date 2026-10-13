# Android verification

## Source version 1.3.0 / code 4

The website interface loads from the NAS, so its consolidation is also available in the published 1.2 app after updating the server.

- Gradle 8.13 with the pinned distribution checksum and Android Gradle Plugin 8.13.2 completed `testDebugUnitTest lintRelease assembleRelease` using JDK 21 and SDK platform 36. The build produced an unsigned APK only in the ignored build output folder.
- Three URL security unit tests pass against Java 17 language settings. Release lint reports no errors and 13 warnings in the unchanged native code (WebView JavaScript, backup configuration and untranslated literals).
- The unsigned APK reports package `nl.plexport.app`, version `1.3.0` / code `4`, minimum API 26, target API 36 and only the `INTERNET` permission.
- Eight release guard tests pass: missing and incomplete keys stop the build, existing keys remain untouched, unsigned or differently signed APKs cannot replace a public release, and personal APKs stay in a separate folder.
- The release script requires the original signing backup and checks the certificate against the published APK before writing a distribution APK.
- The original signing key is unavailable in this cloud environment. No new signing key was created and no signed 1.3 APK has been published. The website download and `dist/PlexPort-1.2.0.apk` retain the existing release.
- No physical phone or emulator verification was performed for version 1.3.

## Published APK 1.2.0

The public build uses a generic NAS address (`http://truenas.local:8765/`). Enter your own PlexPort address when opening it. Updates preserve an existing saved address.

- Release build, URL unit checks and release lint pass.
- The release signature matches the previous APK, so this version can install as an update.
- Package `nl.plexport.app`, version `1.2.0` / code `3`, Android 8 / API 26 or newer, target API 36. Only `INTERNET`; debugging disabled.
- `../plexport/static/plexport.apk` is identical to `dist/PlexPort-1.2.0.apk`.
- The native sign-in dialog now has labeled fields, rounded controls, password visibility and matching light and dark colors. The rest of the interface loads from your PlexPort server.
- The personal build installed successfully in an isolated API 35 emulator. Native screen rendering could not be verified there; no physical phone check was performed.

SHA256:

```text
1f3f47036a91eb9e9645e0288e3d6661c1bcd8e81ab7fd4b39df58cac18d1f01
```

Build, signature and installation checks do not prove a complete download from Android through a NAS to Plex. The signing key is not in this repository.
