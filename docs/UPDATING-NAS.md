# Update an existing NAS installation

The release includes `tools/update_nas.py` for installations that bind-mount a
PlexPort code folder into `/app`, as in the TrueNAS example. It replaces only
that folder's `plexport` runtime, including the APK served by PlexPort. It leaves
Compose YAML, environment files, saved settings, tasks, download folders and
media in place. It does not stop qBittorrent, Transmission or Plex.

This is a host-side tool, not a service manager. Discover the actual PlexPort
service and mount paths before running it. Do not substitute the example NAS
address, app name, storage pool or UID from the installation guide for your
actual configuration. Run only one PlexPort instance against a data folder.
Python 3.9 or newer is required on the host.

## Prepare a verified release

Download the release archive and `SHA256SUMS` from the published GitHub release.
Use the archive's SHA-256 from that release as `RELEASE_SHA256` below. The
archive contains a second `SHA256SUMS` manifest covering every runtime file.
The helper requires the external archive checksum and verifies the internal
manifest before changing the installation. Do not take a checksum solely from
an unverified archive. An already extracted release is also accepted, provided
its manifest exists and its originating archive was verified first.

Identify:

- `APP_DIR`: the existing host code folder mounted at `/app`; it must contain
  `plexport/__main__.py`.
- `DATA_DIR`: the existing host folder mounted at `/data`; it must contain
  `plexport.sqlite`.
- `BACKUP_DIR`: a private folder outside both code and data. Backups contain
  credentials, so restrict access to its owner (`chmod 700`) and keep them off
  GitHub. Do not use a media or downloader folder for backups.
- `RELEASE_ARCHIVE`: the downloaded local release archive, outside `APP_DIR`.

Check available disk space: the update makes a full copy of the existing code
folder, a SQLite snapshot and a staged runtime. Run as the app folder owner or
an administrator able to retain its ownership and permissions. The helper
rejects symlinks and special files, including in path parents; use actual
dataset paths. Use an application code folder, never a storage-pool root.

## Stop only PlexPort, update and check

For a TrueNAS custom app, inspect the app name and configuration in Apps, or
use the host shell's supported `midclt` app methods. For Docker Compose, inspect
the active project's service and bind mounts. Preserve the current Compose
configuration, passwords, dataset ACLs and downloader mounts.

Stop **only the discovered PlexPort service** through its current service
manager. For example, after verifying its actual name is `plexport`, a TrueNAS
host can use `midclt call --job app.stop plexport`; a Compose installation can
use `docker compose -f /actual/compose.yaml stop plexport`. Do not run `down`
against a stack containing other apps. Confirm PlexPort has stopped.

Run the helper from the verified extracted release, using the actual paths and
published checksum:

```sh
python3 /path/to/verified-release/tools/update_nas.py \
  --app-dir "$APP_DIR" \
  --data-dir "$DATA_DIR" \
  --backup-dir "$BACKUP_DIR" \
  --source "$RELEASE_ARCHIVE" \
  --sha256 "$RELEASE_SHA256" \
  --service-stopped
```

The helper prints the private backup location. It snapshots SQLite through the
SQLite backup API, including committed changes still in a WAL file, and checks
the snapshot's integrity. Existing runtime paths retain ownership and file
modes; new files are readable by the existing app user. A failed runtime swap
restores the previous code automatically. The database is never replaced.

Start only the same PlexPort service using its existing configuration. For the
verified TrueNAS example name this is `midclt call --job app.start plexport`;
for Compose it is `docker compose -f /actual/compose.yaml start plexport`.
Keep the service's code mount read-only if it was read-only before the update.

Before declaring the update complete:

1. Check that the service is running and its logs show no startup errors.
2. Open the actual PlexPort URL and sign in with the existing account.
3. Check the displayed version, existing tasks and settings. Confirm that the
   downloader still reports the existing torrents and progress.
4. In Settings, use **Opslaan & controleren** to check the saved connections and
   mapped folders. Verify that the existing Plex movie and TV folders remain
   the selected folders.
5. Download the APK through Settings if needed, and compare it with the
   published release APK. Install it over the previous Android app using the
   same signing key; do not uninstall the old app to bypass a signature error.

For an installation built into a Docker image instead of bind-mounted code,
use the existing image/Compose update workflow with the same persistent data
and media mounts. Do not use this file replacement helper inside a running
container or assume it replaces an image.

## Roll back runtime code

If startup or functional checks fail, stop only PlexPort again and restore its
previous runtime from the printed backup:

```sh
python3 /path/to/verified-release/tools/update_nas.py \
  --app-dir "$APP_DIR" \
  --rollback /actual/private/backups/plexport-update-BACKUP_ID \
  --service-stopped
```

Start the same service and repeat the checks. Rollback restores code and the
previous served APK. It preserves the current database, including tasks saved
after the update. The SQLite snapshot is a separate disaster-recovery backup;
restoring it could erase newer task progress or settings and must be a separate,
intentional recovery operation while PlexPort is stopped.
