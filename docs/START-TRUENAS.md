# PlexPort installeren op TrueNAS

[Terug naar de startpagina](../README.md)

Deze handleiding is voor **TrueNAS 25.10**. qBittorrent en Plex moeten al werken. De eerste installatie vraagt wat mapinstellingen; daarna bedien je PlexPort in je browser of op Android.

## 1. Verzamel drie dingen

| Dit heb je nodig | Waar vind je het? | Voorbeeld |
|---|---|---|
| Het adres van je NAS | Het adres waarmee je TrueNAS in je browser opent | `192.168.1.100` |
| De downloadmap | De opslaginstellingen van je qBittorrent-app | `/mnt/tank/downloads` |
| De film- en seriemap | De mappen die je Plex-bibliotheken gebruiken | `/mnt/tank/media/Movies` en `/mnt/tank/media/Series` |

De voorbeelden zijn geen waarden die je zomaar moet overnemen. **Hoofdletters tellen mee:** `Movies` en `movies` kunnen verschillende mappen zijn. Maak geen lege vervangende map als je films al ergens staan.

## 2. Download en plaats PlexPort

[Download de appbestanden](https://github.com/Tufein/PlexPort/archive/refs/heads/main.zip) en pak ze uit. Plaats ze op je NAS in een aparte appmap. Bewaar de instellingen in een afzonderlijke map zodat je ze later bij een update kunt behouden.

Hier heb je de eenmalige technische stap nodig: [volg de mapindeling en het installatievoorbeeld](../INSTALLATIE-TRUENAS.md#mappen-en-gebruiker). Daar staat welke map je waar koppelt en welke gebruiker toegang nodig heeft.

## 3. Installeer de app in TrueNAS

1. Open **Apps** in TrueNAS en kies de installatieoptie voor een eigen app met YAML. YAML is hier het tekstbestand met de appinstellingen.
2. Gebruik `compose.yaml` uit de uitgepakte map. Pas de voorbeeldadressen, mappen en appgebruiker aan volgens de [installatiehandleiding](../INSTALLATIE-TRUENAS.md#plexport-installeren).
3. Vul bij `PLEXPORT_PASSWORD` een eigen PlexPort-wachtwoord in en sla op.
4. Wacht tot de app **Running** aangeeft.

## 4. Open PlexPort

Open `http://JE-NAS-ADRES:8765` in je browser. Vervang `JE-NAS-ADRES` door je eigen adres. Meld aan met **admin** en het PlexPort-wachtwoord dat je zojuist hebt gekozen.

Open **Instellingen**:

1. Kies qBittorrent en vul het adres van zijn bedieningspagina en de bijbehorende aanmelding in.
2. Vul de downloadmap, filmmap en seriemap in zoals de installatiehandleiding aangeeft.
3. Klik **Alles controleren**. Herstel eventuele meldingen vóór je een download start.
4. Voeg een zoekbron toe en sla op. Je kunt ook zonder zoekbron een eigen link gebruiken.

[Ga verder met je eerste download](GEBRUIKEN.md).

## Bij een update

Stop PlexPort, bewaar de bestaande instellingenmap en vervang alleen de appbestanden in de codemap. Start PlexPort opnieuw en klik **Alles controleren**. Je instellingen, taken en media hoeven niet te worden verwijderd. De Android-app laadt de nieuwe bediening van de server; voor deze websiteverbeteringen is geen nieuwe APK nodig.

Zie je een fout met `EFAULT`? [Open de hulp](HULP.md#truenas-zegt-efault-of-de-app-start-niet).
