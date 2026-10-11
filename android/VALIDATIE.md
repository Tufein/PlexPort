# Public Android APK 1.1.0 verification

The public build uses a generic NAS address (`http://truenas.local:8765/`). Enter your own PlexPort address when opening it. Updates preserve an existing saved address.

- Release build, URL unit checks and release lint pass.
- `apksigner verify` confirms a valid signature with the same certificate as the public APK 1.0.0.
- Package `nl.plexport.app`, version `1.1.0` / code `2`, Android 8 / API 26 or newer, target API 36. Only `INTERNET`; debugging disabled.
- `../plexport/static/plexport.apk` is identical to `dist/PlexPort-1.1.0.apk`.
- The native client is functionally unchanged from version 1.0. This build increases the installation version; new search filters, download statuses and storage checks come from the updated PlexPort server.

SHA256:

```text
7094b389db19c07cfabada9e69a5a8e98c936cdbe2d69e10eb231ca51188322a
```

This build was not run again in an emulator or on a physical phone. These checks do not prove a complete download from Android through a NAS to Plex. The signing key is not in this repository.
