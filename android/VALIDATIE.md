# Android APK 1.2.0 verification

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
