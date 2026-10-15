# Prepare a source release

Work from a clean public checkout. Keep private databases, NAS configuration,
credentials and Android signing material outside the public repository. Website
releases can use the existing signed Android APK because it loads the server UI.
Do not describe an unpublished native source version as an available APK update.

1. Update the server version in `plexport/__init__.py`, changelog, usage guide and
   feature status. Keep old release notes as history.
2. Run the Python suite, JavaScript tests and syntax checks. Exercise the affected
   browser-to-API-to-task flows with isolated temporary data and local downloader
   fixtures. Record actual checks and any physical NAS/Android coverage limits.
3. Review the code, stage only intended public files and commit the source.
4. Build the exact committed revision:

   ```sh
   python3 tools/build_release.py --ref HEAD --output-dir dist
   ```

   The deterministic archive excludes earlier `dist` archives and rejects
   private/generated tracked paths. It contains the committed source plus an
   internal `SHA256SUMS`. The adjacent checksum covers the entire archive.
5. Verify every manifest entry, runtime completeness and archive checksum. Run a
   temporary NAS update/rollback rehearsal that preserves task data, configuration
   and media. Commit the archive and sidecar separately.
6. Push the reviewed source and distribution commits, publish a version tag at
   that final commit, and create the GitHub release with the archive/checksum and
   the existing signed APK/checksum. Verify the published tag, source revision and
   downloaded checksums. Publishing a release does not deploy an existing NAS.

For a downgrade across the episode-selection feature, follow the stopped-task
precautions in [Update an existing NAS](UPDATING-NAS.md).
