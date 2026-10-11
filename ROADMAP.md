# PlexPort-roadmap

## Beschikbaar

- Nederlandstalige website met Systeem-, Licht- en Donkermodus.
- qBittorrent 4.6+/5.x en een Docker-variant met Transmission.
- Downloadvoortgang, pauzeren, hervatten en gecontroleerd opnieuw proberen.
- Gedeelde downloadmap en import van voltooide video's en ondertitels naar Plex-mediamappen.
- Rechtstreekse WatchSoMuch-bron en Torznab-koppelingen via Prowlarr of Jackett.
- Android-app die dezelfde PlexPort-server, instellingen en taken gebruikt.
- TrueNAS-installatievoorbeelden, geselecteerde diagnose en backup-hulpmiddelen.
- Een omkeerbaar icoonhulpmiddel voor TrueNAS 25.10.7.

## Betere downloads

1. Duidelijker onderscheid tussen downloaden, controleren, wachten op peers, seeding en importeren.
2. Opslag- en bestandscontroles vóór het starten, met begrijpelijke herstelstappen bij fouten.
3. Een expliciete migratieflow voor bestaande torrents naar een andere downloader: stoppen, aanwezige bestanden controleren en pas daarna koppelen/hervatten.
4. Een importkeuze voor rechtstreeks in qBittorrent toegevoegde downloads.
5. Efficiëntere opslag: hardlinks waar mount- en datasetgrenzen dit toelaten, met zichtbare melding bij kopiëren en beleid voor opruimen na seeding.
6. Betere herkenning van seriepakketten en een gecontroleerde keuze tussen downloadvarianten.

De app importeert alleen volledige geselecteerde bestanden. RAR/ZIP-archieven worden niet uitgepakt; samples en overige bestanden worden overgeslagen. Automatisch scannen via de Plex-API vereist een geldig token en bibliotheek-ID's. Zonder die koppeling kan Plex zelf automatisch of handmatig scannen.
