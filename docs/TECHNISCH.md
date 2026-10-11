# Technische uitleg voor PlexPort

[Terug naar de eenvoudige startpagina](../README.md) · [Dagelijks gebruik](GEBRUIKEN.md)

Een lokale, Nederlandstalige app die je bronnen doorzoekt, torrents naar Transmission of qBittorrent stuurt en voltooide media automatisch in je Plex-mediamappen importeert.

Bovenaan kies je bij **Weergave** tussen Systeem, Licht en Donker. Je keuze blijft per browser bewaard. Voor Android staat een ondertekende APK klaar in [android/dist/PlexPort-1.0.0.apk](../android/dist/PlexPort-1.0.0.apk); je kunt hem ook downloaden via **Instellingen → Android-app downloaden**. De Android-app gebruikt dezelfde NAS, bronnen en downloads. Zie [Android installeren](../android/README.md) en de [roadmap voor betere downloads](../ROADMAP.md).

**TrueNAS 25.10 Goldeye:** volg [INSTALLATIE-TRUENAS.md](../INSTALLATIE-TRUENAS.md). `compose.yaml` en `compose.truenas.yaml` zijn voorbeelden voor de Apps-webinterface. Pas het NAS-adres, de datasetpaden en UID/GID aan en vul een eigen PlexPort-wachtwoord in. PlexPort en de qBittorrent-app moeten dezelfde fysieke downloadmap als `/downloads` zien.

**Andere NAS of lokale Docker-installatie:** volg [INSTALLATIE-NAS.md](../INSTALLATIE-NAS.md) met `compose.build.yaml` voor een bestaande qBittorrent. Gebruik `compose.transmission.yaml` als je liever een nieuwe torrent-downloader meelevert. Alleen deze twee varianten gebruiken `.env`.

## Starten op deze Mac

Dubbelklik op **Start PlexPort.command**, of start vanuit deze map:

```sh
python3 -m plexport --open
```

Python 3.11 of nieuwer is voldoende; de app heeft geen aanvullende Python-pakketten nodig. De app opent op **http://127.0.0.1:8765**. Houd het terminalvenster open om downloads te verwerken. Sluiten of Ctrl+C stopt PlexPort; de torrentclient blijft zelfstandig werken. Downloads en instellingen worden na opnieuw starten hervat.

Bij deze startmethode gebruik je een **apart geïnstalleerde Transmission of qBittorrent**. De torrent-engine draait niet in het Python-proces.

## Inclusief torrent-downloader met Docker

De alternatieve Docker Compose-opstelling start PlexPort en Transmission samen. Docker moet daarvoor geïnstalleerd en gestart zijn. Gebruik bij een lokale Docker-build `compose.build.yaml` voor een bestaande qBittorrent; starten gebeurt dan met `docker compose -f compose.build.yaml up -d --build`.

1. Kopieer `.env.example` naar `.env`.
2. Kies je eigen app- en Transmission-wachtwoorden in `.env`.
3. Stel `MEDIA_PATH` in op je bestaande Plex-mediamap en `DOWNLOADS_PATH` op een downloadmap. Beide moeten bestaan en schrijfbaar zijn. Op Linux/NAS stel je ook `PUID` en `PGID` in op de eigenaar van de mappen.
4. Start:

```sh
docker compose -f compose.transmission.yaml up -d --build
```

Open **http://JE-NAS-ADRES:8765**, gebruikersnaam **admin**, met `PLEXPORT_PASSWORD` als wachtwoord. Transmission is bereikbaar op **http://JE-NAS-ADRES:9091** met de Transmission-gegevens uit `.env`. Stoppen: `docker compose -f compose.transmission.yaml down`. Instellingen, torrents en media blijven in de gekoppelde mappen bewaard.

Deze opstelling maakt de bedieningsschermen bereikbaar op je NAS met wachtwoordbeveiliging. Gebruik bij toegang via het internet een reverse proxy met HTTPS; de app bevat zelf geen TLS-server.

## Instellen

Open **Instellingen** en sla daarna iedere verbinding op en test hem.

### Downloader

- **Transmission:** volledig RPC-adres, bijvoorbeeld `http://127.0.0.1:9091/transmission/rpc`. In de meegeleverde Docker-opstelling is het `http://transmission:9091/transmission/rpc`.
- **qBittorrent:** schakel de Web UI in en gebruik het basisadres, bijvoorbeeld `http://192.168.1.20:8080`, met gebruikersnaam en wachtwoord. De koppeling is bedoeld voor qBittorrent 4.6+ en 5.x, inclusief pauzeren/hervatten.
- Vul de downloadmap in zoals de **downloader** die ziet, en dezelfde map zoals **PlexPort** die ziet. De downloader moet zijn bestanden daadwerkelijk in die gedeelde map schrijven. Iedere taak krijgt een eigen submap.

Voorbeeld: qBittorrent draait op een NAS en schrijft naar `/volume1/downloads`. Die map is op je Mac gemount als `/Volumes/downloads`. Stel het downloaderpad in op `/volume1/downloads` en het PlexPort-pad op `/Volumes/downloads`.

In Docker gebruiken beide standaard `/downloads`. Voor qBittorrent op de host van Docker gebruik je waar ondersteund `http://host.docker.internal:8080`; `localhost` in een container verwijst naar die container zelf.

### Plex

Vul afzonderlijke film- en seriemappen in die **PlexPort kan lezen en beschrijven** en die ook door je Plex-server worden gelezen. Een server op een NAS of andere computer vereist dus een gemounte SMB/NFS-map of een Docker-volumekoppeling. Alleen het Plex-serveradres invullen is onvoldoende: de Plex API biedt geen upload van mediabestanden.

Met Docker zijn de app-paden standaard `/media/Movies` en `/media/TV Shows`. Bij `compose.build.yaml` en `compose.transmission.yaml`: als `MEDIA_PATH=/volume1/media` is, configureer je in Plex de bibliotheekmappen `/volume1/media/Movies` en `/volume1/media/TV Shows`, of de equivalente paden in je Plex-container.

Voor een scan na import vul je het Plex-adres en token in. **Plex testen** toont de bibliotheken en hun ID's. Neem de juiste ID over bij films en series. Je vindt uitleg over het token in [Plex Support](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

Zonder Plex-token worden bestanden wel geïmporteerd. Zet dan automatisch of periodiek scannen aan in Plex. Netwerkmappen ondersteunen niet altijd automatische wijzigingsdetectie; een API-scan of periodieke scan is dan nodig. [Plex-bibliotheekinstellingen](https://support.plex.tv/articles/200289526-library/)

Een geslaagde scan-aanvraag betekent dat Plex de aanvraag heeft geaccepteerd; de app controleert niet of Plex de titel vervolgens correct herkent. Het Bibliotheek-scherm toont alleen imports van PlexPort, niet je volledige Plex-catalogus.

### Bronnen / films en series zoeken

Klik bij **Instellingen → Jouw bronnen → WatchSoMuch toevoegen** om [WatchSoMuch](https://watchsomuch.to) rechtstreeks te koppelen. Sla daarna de instellingen op. Er is geen account, API-sleutel, Jackett of Prowlarr nodig voor deze bron. PlexPort gebruikt de openbare RSS-zoekfeed en downloadlijsten, toont varianten met grootte en seeders en haalt de magnetlink pas op wanneer je een download start. Bij series worden herkende seizoen- en afleveringsnummers alvast ingevuld. Controleer die vóór het starten.

Een zoekopdracht leest maximaal vijf gevonden titels en toont maximaal 250 varianten, met een cache van vijf minuten. Zoek zo specifiek mogelijk. Wijzigingen of tijdelijke blokkades op de website kunnen de koppeling onderbreken; PlexPort start dan geen download met een ongeldige link.

Voor andere bronnen voeg je de **Torznab-feed** en API-sleutel toe. [Prowlarr](https://wiki.servarr.com/prowlarr) en [Jackett](https://github.com/Jackett/Jackett) bieden zulke feeds voor hun ingestelde indexers. Kopieer de Torznab-URL uit je bronbeheerder. PlexPort zoekt in de categorieën Movies (2000) of TV (5000); resultaten worden gesorteerd op seeders.

Je activeert zelf welke bronnen je wilt gebruiken; er worden geen accounts meegeleverd. Je kunt zonder zoekbron ook een magnetlink, torrent-URL of `.torrent`-bestand toevoegen.

## Hoe import werkt

1. Voeg een download toe en controleer de **titel voor Plex**. WatchSoMuch vult de titel en het jaar vanuit de zoekfeed in. Bij Torznab staat de releasenaam ingevuld; pas die aan naar de echte film- of serietitel en vul eventueel het jaar in.
2. PlexPort bewaart de taak in SQLite en stuurt hem naar de downloader. De voortgang wordt iedere vier seconden bijgewerkt.
3. Alleen complete, geselecteerde videobestanden en ondertitels worden geïmporteerd. De app controleert de bereikbaarheid en bestandsgrootte. Samples en overige bestanden worden overgeslagen. RAR/ZIP-archieven worden niet uitgepakt.
4. Films komen in `Titel (jaar)/Titel (jaar).mkv`. De grootste video wordt als hoofdvideo benoemd; eventuele andere video's behouden hun bestandsnaam in dezelfde map. Series komen in `Serie/Season 01/Serie - S01E01.mkv`. Seizoenpakketten vereisen afleveringsnummers in de bestandsnamen. Bij één aflevering kun je seizoen en aflevering handmatig opgeven.
5. Op hetzelfde bestandssysteem gebruikt de app hardlinks; op een andere schijf of netwerkshare kopieert hij de bestanden. De download blijft op zijn plaats voor seeding. Kopiëren kan daarom extra schijfruimte kosten.
6. Na import wordt, indien ingesteld, een Plex-scan aangevraagd. Een fout in de scan verwijdert de geïmporteerde media niet. Gebruik **Opnieuw proberen** nadat je de instellingen hebt hersteld.

Alleen downloads die je via PlexPort toevoegt worden op deze manier geïmporteerd. Een torrent die je rechtstreeks in de qBittorrent-Web UI toevoegt, blijft in de downloadmap en krijgt geen automatische PlexPort-import.

De app vervangt geen bestaande media met andere inhoud. Dubbele torrents worden geweigerd. Niet alle releasenamen, extra's en ondertiteltalen zijn automatisch te herkennen; controleer de titel en gebruik episodecodes bij series. PlexPort transcodeert niet en downloadt geen ondertitels.

## Gegevens & toegang

Instellingen, toegangsgegevens en taakgeschiedenis staan lokaal in `data/plexport.sqlite` met bestandsrechten `0600`. Geheimen worden niet teruggestuurd naar het instellingenformulier; lege wachtwoordvelden behouden de opgeslagen waarden. Ze zijn wel nodig in de lokale database om de diensten te benaderen. Bescherm backups van deze map. Om een opgeslagen geheim te verwijderen kun je via de lokale API expliciet een lege waarde opslaan.

De losse app luistert standaard uitsluitend op `127.0.0.1`. Voor een andere luisterinterface moet je `PLEXPORT_PASSWORD` instellen; aanmelden gebeurt met `admin` en dat wachtwoord. API-verzoeken hebben een eigen header en controle op de browser-origin. Er wordt geen telemetry verstuurd en de interface gebruikt geen externe fonts of scripts.

## Ontwikkeling & verificatie

```sh
python3 -m unittest discover -s tests -v
node --check plexport/static/app.js
```

De tests gebruiken tijdelijke mappen en lokale testservers. Ze verifiëren de torrent-API's, import, herstarten, padbeveiliging, secret-redactie, zoekfeeds en browser-API. Een echte torrentclient, Docker-installatie, externe zoekbron en Plex-server zijn nodig om de koppelingen in jouw omgeving te testen.

## Nieuwe bediening

Zoekfilters worden in de browser toegepast op de maximaal 250 resultaten van de bestaande zoekaanvraag. De beeldkwaliteit wordt afgeleid uit de releasenaam; dit is geen verificatie van de video. Bij een bestandsgroottelimiet vallen resultaten met onbekende grootte buiten de selectie.

`POST /api/preflight` controleert de opgeslagen downloadmap en de bestemming van de gekozen categorie. Het verzoek bevat `kind` (`movie` of `tv`) en optioneel `expected_bytes` (niet-negatief geheel getal). De controle schrijft en verwijdert een tijdelijk testbestand en leest de vrije ruimte. Zij maakt geen ontbrekende map aan en bewijst niet dat een externe downloader dezelfde fysieke map gebruikt. Er wordt geen ruimte gereserveerd. Ook andere taken en datasetquota kunnen het resultaat beïnvloeden.

Het toevoegen van een taak controleert de mappen opnieuw. Een nog niet verstuurde taak wordt ook door de worker opnieuw gecontroleerd. Bij reeds verstuurde taken blijft het oorspronkelijke downloaderadres en pad behouden. Ontbrekende film- of seriemappen blokkeren de start; alleen de bestemming van de gekozen categorie is daarvoor nodig.

De bekende grootte uit het gekozen zoekresultaat wordt gebruikt om een download te weigeren die groter is dan de op dat moment beschikbare ruimte. Handmatige links en torrentbestanden hebben in deze versie nog geen vooraf bekende grootte. Als hardlinks niet mogelijk zijn, controleert de kopieerstap aanvullend de vrije ruimte van de mediamap.

De activiteit uit qBittorrent of Transmission wordt los van de importstatus opgeslagen. Controleren, voorbereiden, wachten, verplaatsen en downloaden krijgen verschillende meldingen. qBittorrent-taken die bestanden verplaatsen, controleren of metadata ophalen worden niet geïmporteerd, ook niet wanneer hun voortgang op 100% staat.

Frontend-filters testen:

```sh
node --test tests/test_discovery.cjs
```
