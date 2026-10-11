# PlexPort op TrueNAS

Installeer PlexPort als custom app via **Apps → Discover Apps → Install via YAML**. qBittorrent en Plex draaien als aparte apps op dezelfde NAS. `compose.yaml` en `compose.truenas.yaml` zijn identieke voorbeelden; vervang de adressen, datasetpaden en gebruiker door die van jouw NAS.

## Mappen en gebruiker

Het voorbeeld gebruikt `192.168.1.100`, pool `tank` en UID/GID `3000:3000`. Deze waarden zijn voorbeelden. Maak de app-, data- en downloadmappen vooraf aan en gebruik de werkelijke schrijfwijze van je film- en seriemappen.

| Gebruik | Voorbeeld op TrueNAS | PlexPort-container | qBittorrent-container |
|---|---|---|---|
| Appcode | `/mnt/tank/media/Movies/.plexport-app/code` | `/app` | — |
| Instellingen en taken | `/mnt/tank/media/Movies/.plexport-app/data` | `/data` | — |
| Downloads | `/mnt/tank/media/Movies/.plexport-downloads` | `/downloads` | `/downloads` |
| Films | `/mnt/tank/media/Movies` | `/media/Movies` | — |
| Series | `/mnt/tank/media/Series` | `/media/TV Shows` | — |

Beide downloadkoppelingen moeten naar **dezelfde fysieke map** verwijzen. Gebruik in de qBittorrent-app een hostpad voor de downloads. De gebruikers van beide apps moeten daar kunnen lezen en schrijven. Plex moet de film- en seriemappen kunnen lezen. Behoud bestaande dataset-ACL's; pas toegangsrechten aan voor de gekozen appgebruikers.

Plaats de inhoud van deze repository in de codemap, met de submap `plexport` rechtstreeks onder `code`. Als de downloads en appbestanden binnen je filmmap staan, voeg dan aan `.plexignore` in die filmmap toe:

```text
.plexport-downloads/*
.plexport-app/*
```

## PlexPort installeren

1. Pas alle voorbeeldpaden en het NAS-adres in `compose.yaml` aan. Controleer ook `user: "3000:3000"` tegen de gebruiker die toegang tot je datasets heeft.
2. Vul een eigen `PLEXPORT_PASSWORD` in. Een netwerkserver zonder appwachtwoord start niet. Bewaar een bestaand wachtwoord bij een update.
3. Installeer via de Apps-webinterface met naam `plexport`, sla de YAML op en wacht op **Running**.
4. Open `http://JE-NAS-ADRES:8765` en meld aan als `admin` met je PlexPort-wachtwoord.

De YAML gebruikt de officiële Python-container en vereist geen lokale Docker-build. `create_host_path: false` laat een verkeerde mapkoppeling mislukken, zodat er geen onverwachte lege map wordt gemaakt. Bewaar de `data`-map bij updates; deze bevat instellingen en taken. Laat één PlexPort-instantie dezelfde taken verwerken.

## qBittorrent verbinden

Schakel de Web UI van de qBittorrent-app in en stel de standaarddownloadmap in op `/downloads`. Gebruik diezelfde containerlocatie in PlexPort. Automatisch torrentmapbeheer staat voor PlexPort-taken uit; gebruik bij voorkeur geen aparte tijdelijke downloadmap.

Open **PlexPort → Instellingen**:

| Instelling | Waarde |
|---|---|
| Downloader | qBittorrent |
| Serveradres | `http://JE-NAS-ADRES:30024` of jouw Web UI-poort |
| Gebruikersnaam en wachtwoord | Je qBittorrent-Web UI-aanmelding |
| Downloadmap gezien door de downloader | `/downloads` |
| Dezelfde downloadmap gezien door PlexPort | `/downloads` |
| Filmmap | `/media/Movies` |
| Seriemap | `/media/TV Shows` |

Klik **Opslaan & verbinding testen** en **Opslaan & mappen controleren**. Bij een bestaande database vervangen gewijzigde YAML-waarden de eerder opgeslagen instellingen niet automatisch; pas ook het instellingenformulier aan. Als je qBittorrent al bewust zonder aanmelding voor het appnetwerk gebruikt, laat de downloader-gebruikersnaam leeg. Het voorbeeld schakelt authenticatie niet uit.

Nieuwe taken die je via PlexPort toevoegt krijgen een eigen submap in `/downloads`. Voltooide video's en ondertitels worden naar je film- of seriemap geïmporteerd. De oorspronkelijke bestanden blijven beschikbaar voor seeding. Hardlinks worden gebruikt als dat kan; anders maakt de import een kopie en gebruikt hij extra schijfruimte. Rechtstreeks aan qBittorrent toegevoegde torrents krijgen geen automatische PlexPort-import.

## Plex en bronnen

Vul je Plex-serveradres en Plex-token in, test Plex en sla de bijbehorende film- en seriebibliotheek-ID's op. Plex moet dezelfde fysieke mediamappen lezen; zijn containerpaden mogen anders heten. Zonder API-token worden bestanden wel geïmporteerd; gebruik dan automatisch scannen in Plex of scan handmatig.

Bij **Jouw bronnen** kun je WatchSoMuch rechtstreeks toevoegen of een Torznab-bron via Prowlarr of Jackett instellen. Controleer de titel, het jaar en afleveringsnummers voordat je een download start.

## Android en uiterlijk

Download de APK via **Instellingen → Android-app downloaden**, of gebruik `android/dist/PlexPort-1.0.0.apk`. Android 8 of nieuwer wordt ondersteund. Vul je eigen PlexPort-serveradres in; bronnen en taken komen van diezelfde server. De website heeft een keuze tussen Systeem, Licht en Donker. Zie [Android-instructies](android/README.md).

## Hulpmiddelen en fouten

- `tools/diagnose_qbittorrent.py` leest geselecteerde appinstellingen, koppelingen, rechten en gefilterde logs zonder instellingen te wijzigen.
- `tools/repair_qbittorrent_owner.py` herstelt na een UID-wijziging uitsluitend de configuratie van de gecontroleerde qBittorrent-app, met een backup. Pas het verwachte downloadpad aan jouw installatie aan voordat je dit gebruikt.
- `tools/connect_nas_qbittorrent.py` koppelt een bestaande PlexPort-installatie, bewaart de Compose-configuratie en database en controleert verbinding en gedeelde schrijftoegang. Pas de constanten `BASE`, `DOWNLOADS` en `URL` aan jouw installatie aan.
- `tools/truenas_icon.py` biedt een omkeerbare, versiegebonden iconenaanpassing voor TrueNAS **25.10.7**. Dit gebruikt appmetadata buiten de ondersteunde iconen-API. Voer het alleen op deze versie uit; de `--restore`-optie herstelt het oorspronkelijke icoon.

Deze NAS-hulpmiddelen draaien in de **TrueNAS-hostshell** als beheerder. Hun backups bevatten lokale instellingen en horen niet in GitHub. De diagnose is alleen-lezen; andere hulpmiddelen wijzigen uitsluitend de beschreven appconfiguratie.

Bij `[EFAULT] Failed up action` geeft `/var/log/app_lifecycle.log` de werkelijke oorzaak. Een ontbrekend bindpad vraagt om het correcte bestaande pad; maak geen lege vervangende mediamap. Een configuratiefout na een UID-wijziging kan door oude bestandsrechten ontstaan. Bestaande torrents worden niet automatisch tussen downloaders verplaatst: controleer de oorspronkelijke client en bestanden voordat je een taak hervat.

Bronnen: [TrueNAS custom apps](https://apps.truenas.com/managing-apps/installing-custom-apps/), [qBittorrent Web UI API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-5.0)), [Plex-mapuitsluitingen](https://support.plex.tv/articles/201381883-special-keyword-file-folder-exclusion/).
