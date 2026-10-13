#!/usr/bin/env python3
"""Verify release signing before copying an APK into the distribution folder."""
from pathlib import Path
import argparse
import hashlib
import os
import re
import shutil
import subprocess


def certificate(apksigner, apk):
    result = subprocess.run([str(apksigner), 'verify', '--print-certs', str(apk)],
                            check=True, capture_output=True, text=True)
    digests = re.findall(r'^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$',
                         result.stdout, re.MULTILINE)
    if not digests:
        raise SystemExit(f'Geen geverifieerd ondertekeningscertificaat: {apk.name}')
    return tuple(sorted(digest.lower() for digest in digests))


def sdk_apksigner():
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk:
        raise SystemExit('Stel ANDROID_HOME in om de APK-ondertekening te controleren.')
    for version in ('36.0.0', '35.0.0'):
        candidate = Path(sdk) / 'build-tools' / version / 'apksigner'
        if candidate.is_file():
            return candidate
    raise SystemExit('Android build-tools 35.0.0 of 36.0.0 met apksigner ontbreekt.')


def publish(root, apksigner, personal_build=False):
    version = re.search(r"versionName\s+'([0-9]+\.[0-9]+\.[0-9]+)'",
                        (root / 'app/build.gradle').read_text()).group(1)
    current_version = tuple(map(int, version.split('.')))
    built = root / 'app/build/outputs/apk/release/app-release.apk'
    signing_certificate = certificate(apksigner, built)
    if not personal_build:
        previous = []
        for apk in (root / 'dist').glob('PlexPort-*.apk'):
            match = re.fullmatch(r'PlexPort-(\d+)\.(\d+)\.(\d+)\.apk', apk.name)
            if match:
                apk_version = tuple(map(int, match.groups()))
                if apk_version <= current_version:
                    previous.append((apk_version, apk))
        if not previous:
            raise SystemExit('De gepubliceerde APK ontbreekt; de updatesleutel kan niet worden geverifieerd.')
        reference = max(previous)[1]
        if signing_certificate != certificate(apksigner, reference):
            raise SystemExit('De releasesleutel wijkt af van de gepubliceerde APK. '
                             'Herstel de oorspronkelijke .signing-back-up; er is geen update gepubliceerd.')
    folder = root / 'dist' / 'personal' if personal_build else root / 'dist'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'PlexPort-{version}.apk'
    temporary = target.with_suffix('.apk.tmp')
    shutil.copyfile(built, temporary)
    temporary.replace(target)
    target.with_suffix('.apk.sha256').write_text(
        hashlib.sha256(target.read_bytes()).hexdigest() + '  ' + target.name + '\n')
    print(f'APK gemaakt: {target.resolve()}')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--personal-build', action='store_true')
    arguments = parser.parse_args()
    publish(Path(__file__).resolve().parent, sdk_apksigner(), arguments.personal_build)
