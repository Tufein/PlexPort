# PlexPort op jouw NAS met qBittorrent

Deze installatie gebruikt je bestaande qBittorrent en Plex. PlexPort draait als aparte Docker-container op de NAS.

Gebruik op **TrueNAS 25.10 Goldeye** de specifieke [TrueNAS-handleiding](INSTALLATIE-TRUENAS.md) met het hoofdinstallatiebestand `compose.yaml`. `compose.truenas.yaml` is een gelijkwaardige alias. Deze versie gebruikt vaste NAS-paden en kan via **Install via YAML** worden geplaatst; `.env` wordt daarbij niet gebruikt.

De stappen hieronder zijn voor andere NAS-systemen of een lokale Docker-build met **compose.build.yaml**.

## 1. Plaats de app op je NAS

Kopieer de hele map **PlexPort** naar een map op de NAS waar Docker/Container Manager toegang toe heeft.

## 2. Vul de instellingen voor Docker in

Kopieer `.env.example` naar `.env`. Vul in:

| Instelling | Wat je invult |
|---|---|
| `PLEXPORT_PASSWORD` | Een eigen wachtwoord waarmee je in PlexPort aanmeldt |
| `QBITTORRENT_URL` | Je bestaande qBittorrent Web UI, bijvoorbeeld `http://192.168.1.20:8080` |
| `QBITTORRENT_DOWNLOAD_ROOT` | De downloadmap zoals qBittorrent die ziet |
| `DOWNLOADS_PATH` | Het volledige pad van diezelfde downloadmap op de NAS |
| `MEDIA_PATH` | Het volledige pad van de Plex-mediamap op de NAS |

De voorbeeldadressen hierboven zijn geen ingestelde serveradressen. Gebruik je eigen adres en mappen.

Voorbeeld voor een NAS met opslag onder `/volume1`: qBittorrent draait in een container en ziet `/downloads`, gekoppeld aan `/volume1/downloads`. Stel dan `QBITTORRENT_DOWNLOAD_ROOT=/downloads` en `DOWNLOADS_PATH=/volume1/downloads` in. PlexPort ziet deze bestanden automatisch onder `/downloads`.

Met `MEDIA_PATH=/volume1/media` gebruikt PlexPort `/media/Movies` en `/media/TV Shows`. Plex moet dezelfde mappen op de NAS als bibliotheken lezen. Heeft jouw bestaande filmmap een andere naam, pas de mapnaam aan in **Instellingen** in de app.

Zorg dat de mappen bestaan en dat de container er mag schrijven. Bij een NAS-containerbeheerder kun je een gebruiker of groep met toegang toewijzen; pas in dat geval zo nodig `user: "UID:GID"` in `compose.build.yaml` toe. De app moet ook in haar `data`-map kunnen schrijven.

## 3. Start het Docker-project

Maak in je NAS-containerbeheerder een project aan met de meegeleverde **compose.build.yaml** en deze map als projectmap. Of voer vanuit die map uit:

```sh
docker compose -f compose.build.yaml up -d --build
```

Open in je browser **http://JE-NAS-ADRES:8765**. Meld aan met gebruikersnaam **admin** en het wachtwoord uit `.env`.

## 4. Koppel qBittorrent en Plex

Ga naar **Instellingen**:

1. Kies qBittorrent en vul de gebruikersnaam en het wachtwoord van de bestaande Web UI in.
2. Controleer de downloader-downloadmap en de PlexPort-downloadmap. Het tweede pad is in deze opstelling `/downloads`.
3. Klik **Opslaan & verbinding testen** en **Opslaan & mappen controleren**.
4. Vul het Plex-adres en Plex-token in. Klik **Opslaan & Plex testen** en neem de juiste filmbibliotheek- en seriebibliotheek-ID over. Sla opnieuw op.
5. Voeg WatchSoMuch rechtstreeks toe met **WatchSoMuch toevoegen**, of koppel Torznab-bronnen via Prowlarr of Jackett. Sla de instellingen op. Zonder bron kun je al magnetlinks en torrentbestanden gebruiken.

Gebruik geen `localhost` voor qBittorrent of Plex die in een andere container draaien. Gebruik het NAS-IP en de gepubliceerde poort, of de containernaam als beide containers hetzelfde Docker-netwerk gebruiken.

## 5. Je eerste download

Klik **Download toevoegen**, geef een titel, selecteer Film of Serie en plak een magnetlink of kies een torrentbestand. Volg de voortgang in Downloads. Zodra de video klaar is, importeert PlexPort hem in de film- of seriemap en vraagt de ingestelde Plex-bibliotheekscan aan.

Bij series met meerdere afleveringen moeten bestandsnamen episodecodes zoals `S01E01` hebben. Controleer bij een zoekresultaat de titel voor Plex: een releasenaam is niet altijd de juiste titel.

## Onderhoud

- Laat de container draaien om nieuwe downloads automatisch te verwerken.
- Maak een backup van `data/plexport.sqlite` en je `.env`; daarin staan lokale instellingen en toegangsgegevens.
- Stoppen: `docker compose -f compose.build.yaml down`. Downloadbestanden en geïmporteerde media blijven behouden.
- Bij een fout: herstel de verbinding of mappen en klik **Opnieuw proberen**.

De Docker-opstelling is voorbereid, maar de echte verbinding met jouw NAS, qBittorrent en Plex moet nog met bovenstaande tests worden gecontroleerd.
