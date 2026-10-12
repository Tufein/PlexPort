# PlexPort on your Android phone

[Back to the main page](../README.md)

Your phone controls **the same PlexPort server** running on your NAS or computer. Downloads go to that server, not your phone's storage.

1. Make sure PlexPort is already working on your NAS or computer. Connect your phone to the same home network.
2. [Download the Android app](https://github.com/Tufein/PlexPort/raw/refs/heads/main/android/dist/PlexPort-1.2.0.apk), or open **Instellingen → Android-app downloaden (Settings → Download Android app)** in PlexPort.
3. Open the downloaded file. Android may ask whether your browser or file app may install apps. PlexPort is not yet available on Google Play.
4. Open PlexPort and enter your **PlexPort address**, for example `http://192.168.1.100:8765/`. Use your own NAS address. You can change it later through the app menu.
5. Sign in as **admin** with your **PlexPort password**, not your TrueNAS or qBittorrent password.

Android **8 or newer** is required. To use PlexPort outside your home network, follow [Use PlexPort away from home with Tailscale](START-REMOTE.md). The app does not set this up automatically.

Search filters and download controls come directly from your server, so server updates also appear on your phone. The current interface uses Dutch labels; the [usage guide](GEBRUIKEN.md) explains them in English.

Install version 1.2.0 over the previous APK to keep your saved NAS address. You do not need to uninstall first.

[Connection help](HULP.md) · [Technical Android information](../android/README.md)
