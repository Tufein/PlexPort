# Controle van de openbare Android-APK

Op 11 oktober 2026 is de openbare release opnieuw gebouwd. Het voorgestelde serveradres is `http://truenas.local:8765/`; stel bij de eerste start het adres van je eigen PlexPort-server in.

## Uitgevoerde controles

- `testDebugUnitTest`, `lintRelease` en `assembleRelease` slagen.
- `apksigner verify --verbose` bevestigt een geldige APK Signature Scheme v2-handtekening.
- De download in `../plexport/static/plexport.apk` is identiek aan `dist/PlexPort-1.0.0.apk`.
- De Python-tests van de server slagen: 31 tests.

SHA256 van de APK:

```text
7922e39f8e17f1534f760de052bb6e77e29fe6cb32686bbc41de5d743a3d9799
```

Deze opnieuw gebouwde openbare APK is niet opnieuw in een emulator of op een fysieke telefoon getest. De bouw- en codecontroles bevestigen geen volledige download van Android via een NAS naar Plex.

De ondertekeningssleutel staat niet in deze repository. Bewaar bij eigen builds je sleutel privé om toekomstige APK-updates met dezelfde handtekening te kunnen uitbrengen.
