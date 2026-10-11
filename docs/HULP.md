# Hulp bij PlexPort

[Terug naar de startpagina](../README.md)

## Waar begin ik als iets niet werkt?

Open **Instellingen** en klik **Alles controleren**. Lees de melding bij de downloader of de betreffende map. Herstel dat onderdeel en controleer opnieuw.

## TrueNAS zegt EFAULT of de app start niet

`EFAULT` is een algemene melding. Vaak wijst een mapinstelling naar een map die niet bestaat, met bijvoorbeeld een verkeerde hoofdletter. Controleer de volledige paden in je installatiebestand en vergelijk ze met je echte opslagmappen.

Maak geen lege vervangende filmmap: de app moet je bestaande media kunnen zien. Blijft het probleem? De beheerder kan in de TrueNAS-Shell het bestand `/var/log/app_lifecycle.log` lezen. De nieuwste melding voor `plexport` vertelt meestal wat er precies misgaat. [Meer TrueNAS-uitleg](../INSTALLATIE-TRUENAS.md#hulpmiddelen-en-fouten).

## De download is klaar, maar PlexPort ziet de bestanden niet

De downloader en PlexPort moeten naar **dezelfde downloadbestanden** kijken. Hetzelfde maplabel op het scherm bewijst nog niet dat ze dezelfde opslag gebruiken. Controleer de mapkoppelingen van beide apps. Bij de TrueNAS-voorbeeldinstallatie zien beide de gedeelde downloadmap als `/downloads`.

Klik daarna bij de taak op **Opnieuw proberen**. Verander niet zomaar van downloader als die de taak al heeft ontvangen.

## Wacht op delers: is mijn download kapot?

Niet per se. Er komt nu geen data binnen. Wacht even en kijk in je downloader of de verbinding werkt. Blijft de taak lang wachten, dan kun je een andere versie met meer delers kiezen. PlexPort versnelt een torrent niet zelf.

## Er staat te weinig vrije ruimte

Kies een kleiner bestand of maak ruimte vrij op de betreffende opslag. Verwijder alleen bestanden waarvan je weet dat je ze niet meer nodig hebt. Als de downloadmap en mediamap op verschillende opslag staan, kan een extra kopie nodig zijn.

Een geslaagde ruimtecontrole is een momentopname. Handmatige links hebben nog geen vooraf bekende grootte; andere taken kunnen ondertussen ruimte gebruiken.

## Ik zie niets in Plex

Controleer eerst **Bibliotheek** in PlexPort. Staat de taak daar als geplaatst? Laat Plex dan de bibliotheek scannen. Controleer ook of Plex dezelfde fysieke film- en seriemappen leest en of de titel klopt.

Een scanverzoek betekent dat Plex de aanvraag heeft ontvangen. Het betekent niet dat Plex de titel al heeft herkend.

## Een seriepakket geeft een fout over afleveringsnummers

De bestandsnamen moeten aangeven welke aflevering het is, bijvoorbeeld `S01E01`. Voor één aflevering kun je het nummer zelf invullen. Een pakket met onbekende nummers wordt niet blind hernoemd.

## De Android-app maakt geen verbinding

Gebruik het adres van **PlexPort**, inclusief `:8765` als je de standaardpoort gebruikt. Meld aan met je PlexPort-wachtwoord. Controleer of je telefoon op hetzelfde netwerk zit en de server blijft draaien. Het voorgestelde `truenas.local` werkt alleen als je netwerk die naam herkent; anders gebruik je het IP-adres.

## Ik wil een probleem melden

[Vul het probleemformulier in](https://github.com/Tufein/PlexPort/issues/new?template=probleem.yml). Vermeld je apparaat, wat je deed en de melding die je ziet. **GitHub is openbaar:** deel geen wachtwoorden, tokens, volledige instellingenbestanden of ongefilterde logbestanden.
