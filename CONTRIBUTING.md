# Help PlexPort beter te maken

Een technische achtergrond is niet nodig om te helpen. [Meld een probleem](https://github.com/Tufein/PlexPort/issues/new?template=probleem.yml), [stel een functie voor](https://github.com/Tufein/PlexPort/issues/new?template=idee.yml) of vertel welke uitleg je niet begrijpt.

Gebruik voorbeelden zonder persoonlijke toegangsgegevens. Alle meldingen in deze repository zijn openbaar.

## Voor wie de code aanpast

Houd de bediening Nederlandstalig en gebruik gewone woorden. Bescherm bestaande instellingen, downloads en media. Downloadtaken mogen niet stilzwijgend naar een andere downloader worden verplaatst. Voeg bij wijzigingen aan de verwerking een test toe die het echte risico controleert.

Voer vanuit de projectmap uit:

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_discovery.cjs
node --check plexport/static/app.js
```

Controleer nieuwe bediening in een brede en smalle browserweergave en in licht en donker. [Technische uitleg](docs/TECHNISCH.md).
