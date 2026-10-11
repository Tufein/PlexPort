# PlexPort voor Android

Deze Android-app opent jouw bestaande PlexPort op de NAS. Bronnen, qBittorrent, downloadstatus en Plex-instellingen komen van dezelfde server als de website. De telefoon hoeft geen torrent-downloader te draaien.

## Installeren en gebruiken

Je kunt de APK rechtstreeks op je telefoon downloaden via **PlexPort → Instellingen → Android-app downloaden** op `http://192.168.1.100:8765/#settings`.

1. Zet `dist/PlexPort-1.0.0.apk` op je Android-telefoon en open het bestand. Sta, als Android daarom vraagt, installatie vanuit die bestandsapp of browser toe.
2. Verbind met hetzelfde thuisnetwerk als je NAS, of een VPN die toegang geeft tot dat netwerk.
3. Open **PlexPort** en vul je eigen NAS-adres in, bijvoorbeeld `http://192.168.1.100:8765/`. De eerste suggestie is `http://truenas.local:8765/`. Je kunt het adres later veranderen via **Menu → NAS-adres wijzigen**.
4. Meld je aan met `admin` en je bestaande **PlexPort-wachtwoord**. Gebruik hier je PlexPort-aanmelding, niet je qBittorrent- of TrueNAS-wachtwoord.

De app slaat alleen het NAS-adres op. Je wachtwoord blijft uitsluitend in het geheugen tijdens de appsessie en is opnieuw nodig na het sluiten van de app. **Menu → Afmelden** beëindigt de aanmelding. Een nieuwe sessie controleert je aanmelding opnieuw op de server voordat de website wordt geladen. Androids terugknop gaat terug binnen de website; de app sluit wanneer er geen vorige pagina is. Roteren behoudt je huidige pagina en formulier.

De app volgt de lichte of donkere systeemstand. In PlexPort kun je daarnaast via de themakeuze een eigen voorkeur kiezen. Die websitevoorkeur blijft per apparaat bewaard. `.torrent`-bestanden kunnen via de gewone Android-bestandskiezer worden geselecteerd; hiervoor is geen algemene opslagpermissie nodig.

## Bereik en bescherming

- Ondersteunt Android 8.0 en nieuwer: minimum API 26, compile en target API 36. Het enige manifestrecht is `INTERNET`.
- Lokale HTTP is bewust toegestaan voor de huidige NAS-installatie. HTTP versleutelt de aanmelding niet; gebruik dit adres binnen je vertrouwde thuisnetwerk of VPN. HTTPS met een geldig certificaat wordt ook ondersteund.
- Alleen het ingestelde HTTP(S)-adres, met hetzelfde protocol, hostnaam en poort, kan binnen de app worden geladen. Externe websites, andere poorten, `file:`, `content:` en intentlinks worden geblokkeerd.
- Lokale WebView-bestandstoegang, contenttoegang, JavaScript-native bridges, third-party cookies, geolocatie, extra vensters en ongevraagde apparaatpermissies zijn uitgeschakeld. JavaScript is nodig om PlexPort te bedienen.
- HTTPS-certificaatfouten worden geweigerd. De app biedt geen knop om die te omzeilen.
- De native aanmeldcontrole verstuurt alleen een leesverzoek naar `/`, heeft verbindings- en leestime-outs en volgt geen doorverwijzingen. De bestaande PlexPort-server beperkt scripts, afbeeldingen en netwerkverzoeken met zijn Content Security Policy. Androids resourcecontrole ziet bij doorverwijzingen alleen het eerste resourceadres; gebruik deze client daarom voor jouw PlexPort-server.
- Downloads blijven op je NAS/Mac volgens de bestaande PlexPort-instellingen; er draait geen downloadproces of achtergrondservice op Android. De NAS moet bereikbaar zijn.

## Opnieuw bouwen

Gebruik JDK 17 of nieuwer, Android SDK platform 36 en build-tools 35.0.0 of 36.0.0. Stel `JAVA_HOME` en `ANDROID_HOME` in voor je eigen installatie. Gradle 8.13 en Android Gradle Plugin 8.13.2 zijn vastgezet; de Gradle-download heeft een SHA256-controle.

Vanuit deze map:

```sh
./build-apk.sh
```

Dit voert de URL-beveiligingschecks en release-lint uit en bouwt een ondertekende release-APK naar `dist/PlexPort-1.0.0.apk`. Het bijbehorende `.apk.sha256`-bestand wordt bij elke bouw vernieuwd. Kopieer een vernieuwde APK ook naar `plexport/static/plexport.apk` in de NAS-codemap om de website-download bij te werken. Voor een losse ontwikkelbuild kun je `./gradlew assembleDebug` gebruiken.

De eerste release-build maakt een eigen ondertekeningssleutel in **`android/.signing/plexport-release.jks`**, met bijbehorende privé-instellingen in **`android/.signing/signing.properties`**. Latere builds gebruiken dezelfde sleutel; ze vervangen of regenereren hem niet. Bewaar de hele `.signing`-map veilig als back-up: Android accepteert updates alleen met dezelfde ondertekening. De map heeft beperkte bestandsrechten en wordt uitgesloten door `.gitignore`. Deel of publiceer deze map niet. Wanneer één van beide bestanden ontbreekt, stopt de bouw om onbedoeld een andere sleutel te voorkomen.

De meegeleverde APK is een release-build zonder Android-debugging. De handtekening is lokaal voor deze persoonlijke app; de app is niet gepubliceerd in Google Play. Installeer toekomstige versies over de bestaande app met dezelfde sleutel en een hoger `versionCode`.

## Officiële Android-bronnen

De WebView volgt Androids [bestandstoegangsaanbevelingen](https://developer.android.com/privacy-and-security/risks/webview-unsafe-file-inclusion), [HTTP-authenticatie](https://developer.android.com/reference/android/webkit/HttpAuthHandler), [afhandeling van TLS-fouten](https://developer.android.com/reference/android/webkit/WebViewClient#onReceivedSslError(android.webkit.WebView,%20android.webkit.SslErrorHandler,%20android.net.http.SslError)) en [website-donkerstand](https://developer.android.com/develop/ui/views/layout/webapps/dark-theme). De bouwversies zijn gebaseerd op de [AGP 8.13-compatibiliteitstabel](https://developer.android.com/build/releases/agp-8-13-0-release-notes) en de [Android 16 SDK](https://developer.android.com/about/versions/16/setup-sdk). Lees ook Androids uitleg over [cleartext traffic](https://developer.android.com/privacy-and-security/security-config#CleartextTrafficPermitted) en [APK-ondertekening](https://developer.android.com/tools/apksigner).
