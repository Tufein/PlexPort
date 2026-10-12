# Use PlexPort away from home with Tailscale

[Back to the main page](../README.md)

Tailscale creates a private, encrypted network between your own devices. Your phone can then open PlexPort on your NAS from anywhere, **without opening a port on your router** and without putting PlexPort on the public internet. Tailscale has a free personal plan; check its current terms on tailscale.com.

PlexPort needs no code changes for this. It already requires a password for access from other devices, and it works with both plain `http://` over the private network and `https://` through Tailscale.

## What you need

- PlexPort already working at home, with `PLEXPORT_PASSWORD` set (the TrueNAS guide does this).
- A Tailscale account (sign in with Google, Microsoft, Apple or GitHub).
- Tailscale on **the NAS** and on **each phone or computer** you want to use. They must use the same account.

qBittorrent and Plex stay where they are. PlexPort talks to them from your NAS exactly as before, so you do not expose either of them.

## 1. Put the NAS on your Tailscale network

Choose the option that fits your NAS:

- **TrueNAS:** open **Apps**, search for **Tailscale** and install it. Follow the app's own instructions for the authentication key and for sharing the host network. Tailscale's own guide for TrueNAS is the authority here, because the app settings change between TrueNAS versions.
- **Another NAS or a computer with Linux:** install Tailscale from tailscale.com/download and run `sudo tailscale up`. Open the login link it prints.
- **Synology, QNAP and other NAS systems:** use Tailscale's package for your model and follow its instructions.

When the NAS appears in the **Machines** list at login.tailscale.com, note its name (for example `nas`) and its Tailscale address starting with `100.`.

## 2. Turn on friendly names

In the Tailscale admin console, open **DNS** and make sure **MagicDNS** is on. Your NAS then has a stable name such as `nas.your-tailnet.ts.net` (the exact name is shown in the Machines list).

## 3. Install Tailscale on your phone

1. Install the **Tailscale** app from Google Play and sign in with the same account.
2. Keep the switch on. Android shows a key icon while the private network is active.
3. Open the PlexPort app. Under the app menu, change the **PlexPort address** to:

   `http://nas.your-tailnet.ts.net:8765/`

   Use your own NAS name and port. Do not leave out `:8765` unless you use the HTTPS option below.

If Tailscale is on while you are at home, this same address also works there, so you do not need to switch between two addresses. Traffic between your phone and NAS is encrypted by Tailscale, even though the address starts with `http://`.

Sign in as **admin** with your PlexPort password.

## Optional: HTTPS with a normal address

If you prefer `https://` without a port number, Tailscale can add it for devices on your own network:

1. In the Tailscale admin console under **DNS**, turn on **HTTPS Certificates**.
2. On the NAS, run:

   `tailscale serve --bg 8765`

3. Use `https://nas.your-tailnet.ts.net/` as the PlexPort address.

`tailscale serve` only shares PlexPort with your own Tailscale devices. **Do not use `tailscale funnel`**: it publishes the app on the public internet.

On a TrueNAS app installation, the command must run where Tailscale and PlexPort share a network. If you are not sure, use the simple `http://…:8765` address above.

## Safety checklist

- Do **not** forward port 8765 on your router.
- Use a long, unique PlexPort password. Everyone on your Tailscale network can reach the login page, so the password still matters.
- Do not share your Tailscale account. To give someone else access, use Tailscale's device sharing instead of your login.
- Remove devices you no longer use in the Tailscale Machines list.
- Keep qBittorrent, Plex and the TrueNAS web interface off the public internet.

## Troubleshooting

- **The app cannot connect:** check that Tailscale shows as connected on the phone and that the NAS shows as online in the Machines list.
- **The name does not work:** use the `100.` address of the NAS instead, for example `http://100.101.102.103:8765/`, and check that MagicDNS is on.
- **It works over Wi-Fi but not mobile data:** battery saving may stop the Tailscale app. Allow it to run in the background.
- **Login says access is refused:** PlexPort is running without `PLEXPORT_PASSWORD`. Set it and restart the app, as described in the [TrueNAS guide](START-TRUENAS.md).
- **Very slow transfers while away:** the PlexPort screens are light. Downloads and Plex streaming happen at home and are not affected.

This guide was written from Tailscale's documented behavior and PlexPort's code. It has not been tested on a real NAS or phone yet.

[Connection help](HULP.md) · [Android app](START-ANDROID.md)
