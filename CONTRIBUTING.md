# Help improve PlexPort

You do not need a technical background to help. [Report a problem](https://github.com/Tufein/PlexPort/issues/new?template=probleem.yml), [suggest a feature](https://github.com/Tufein/PlexPort/issues/new?template=idee.yml), or tell us which instructions are confusing.

Use examples without private access details. Reports in this repository are public. English is welcome.

## Changing the code

Use plain language in the interface. It currently uses Dutch labels; English repository documentation should include those labels when explaining which buttons to press. Protect existing settings, downloads and media. Download tasks must not silently move to another downloader. When changing processing behavior, add a test that checks the actual risk.

Run these from the project folder:

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_discovery.cjs
node --check plexport/static/app.js
```

Check new controls in wide and narrow browser layouts and in light and dark mode. See the [technical guide](docs/TECHNISCH.md).
