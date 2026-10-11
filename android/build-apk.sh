#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 prepare_signing.py
./gradlew testDebugUnitTest lintRelease assembleRelease --no-daemon --console=plain
mkdir -p dist
python3 - <<'PY'
from pathlib import Path
import hashlib
import re
import shutil
version = re.search(r"versionName\s+'([0-9]+\.[0-9]+\.[0-9]+)'", Path('app/build.gradle').read_text()).group(1)
apk = Path('dist') / f'PlexPort-{version}.apk'
shutil.copyfile('app/build/outputs/apk/release/app-release.apk', apk)
apk.with_suffix('.apk.sha256').write_text(hashlib.sha256(apk.read_bytes()).hexdigest() + '  ' + apk.name + '\n')
print(f'APK gemaakt: {apk.resolve()}')
PY
