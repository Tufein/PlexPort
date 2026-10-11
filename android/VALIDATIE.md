# Controle van de openbare Android-APK 1.1.0

De openbare build gebruikt een algemeen NAS-adres (`http://truenas.local:8765/`). Bij het openen kies je het adres van jouw PlexPort. Een bestaand opgeslagen adres blijft behouden bij een update.

- Release-bouw, URL-unitchecks en release-lint slagen.
- `apksigner verify` bevestigt een geldige handtekening, met hetzelfde certificaat als de openbare APK 1.0.0.
- Pakket `nl.plexport.app`, versie `1.1.0` / code `2`, Android 8 / API 26 of nieuwer, target API 36. Alleen `INTERNET`; debugging uit.
- `../plexport/static/plexport.apk` is identiek aan `dist/PlexPort-1.1.0.apk`.
- De native client is functioneel gelijk aan versie 1.0. Deze build verhoogt het installatieversienummer; de nieuwe zoekfilters, downloadstatussen en opslagcontroles komen van de bijgewerkte PlexPort-server.

SHA256:

```text
7094b389db19c07cfabada9e69a5a8e98c936cdbe2d69e10eb231ca51188322a
```

Deze build is niet opnieuw in een emulator of op een fysieke telefoon gestart. De controles bewijzen geen volledige download vanaf Android via een NAS naar Plex. De ondertekeningssleutel staat niet in deze repository.
