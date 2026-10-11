# Wat komt er hierna?

[Terug naar de startpagina](README.md) · [Wat is al toegevoegd?](CHANGELOG.md)

## Nu beschikbaar

Een eenvoudige startgids, controle van je verbindingen en mappen, filters voor downloadversies, zoeken in je downloads en duidelijke uitleg wanneer een taak wacht. Ook zijn donkerstand, Android, qBittorrent, Transmission en de import naar je mediamappen beschikbaar.

## Onderzochte volgende verbeteringen

Deze ideeën zijn onderzocht, maar nog niet ingebouwd en hebben geen beloofde opleverdatum.

| Idee | Wat heb je eraan? | Wat moet eerst goed geregeld zijn? |
|---|---|---|
| **Een bestaande qBittorrent-download toevoegen** | Ook bestanden die je buiten PlexPort downloadde netjes in Plex plaatsen. | Het juiste bestandspad controleren, voorkomen dat dezelfde video dubbel wordt geplaatst en jou de titel laten bevestigen. |
| **Een vaste voorkeurskwaliteit** | Je hoeft niet telkens Full HD, 4K of een maximumgrootte te kiezen. | Begrijpelijk laten zien waarom een versie wel of niet past, met een keuze wanneer de kwaliteit onbekend is. |
| **Afleveringen kiezen uit een seizoen** | Alleen downloaden wat je nog nodig hebt. | Bestandsinformatie afwachten, geselecteerde bestanden bijhouden en de juiste afleveringsnummers controleren. |
| **Zien of extra opslag nodig is** | Vooraf duidelijk weten wanneer een video ruimte bespaart of als kopie wordt opgeslagen. | Werkelijke ondersteuning van hardlinks testen; dezelfde schijf of mapnaam alleen is geen bewijs. |
| **Een begeleide TrueNAS-installatie** | Minder mapinstellingen en minder kans op een verkeerde koppeling. | Bestaande datasets, rechten en media behouden; geen lege vervangende mappen aanmaken. |

## Waar het onderzoek op is gebaseerd

De [officiële qBittorrent-uitleg](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29) beschrijft afzonderlijke downloadtoestanden, bestandskeuzes en de bediening van bestaande torrents. Dat maakt duidelijkere voortgang en gecontroleerde bestandskeuzes mogelijk.

De [Sonarr-startgids](https://wiki.servarr.com/sonarr/quick-start-guide) werkt met voorkeurskwaliteit en gebruikt hardlinks waar de opslag dat ondersteunt. Dit geeft bruikbare ideeën voor PlexPort, met extra aandacht voor begrijpelijke keuzes en jouw bestaande mediamappen.

[Stel zelf een verbetering voor](https://github.com/Tufein/PlexPort/issues/new?template=idee.yml).
