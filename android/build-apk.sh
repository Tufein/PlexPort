#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 prepare_signing.py
./gradlew testDebugUnitTest lintRelease assembleRelease --no-daemon --console=plain
mkdir -p dist
cp app/build/outputs/apk/release/app-release.apk dist/PlexPort-1.0.0.apk
python3 - <<'PY'
from pathlib import Path
import hashlib
apk = Path('dist/PlexPort-1.0.0.apk')
apk.with_suffix('.apk.sha256').write_text(hashlib.sha256(apk.read_bytes()).hexdigest() + '  ' + apk.name + '\n')
PY
printf 'APK gemaakt: %s/dist/PlexPort-1.0.0.apk\n' "$PWD"
