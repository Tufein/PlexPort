#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
personal_build=false
init_new_key=false
for argument in "$@"; do
    case "$argument" in
        --personal-build) personal_build=true ;;
        --init-new-key) init_new_key=true ;;
        --help)
            printf '%s\n' 'Gebruik: ./build-apk.sh [--personal-build [--init-new-key]]' \
                'Standaard: bouw een update met dezelfde sleutel als de gepubliceerde APK.' \
                'Persoonlijke builds komen in dist/personal/ en kunnen de gepubliceerde APK niet vervangen.'
            exit 0 ;;
        *) printf 'Onbekende optie: %s\n' "$argument" >&2; exit 2 ;;
    esac
done
if "$init_new_key" && ! "$personal_build"; then
    printf '%s\n' '--init-new-key vereist --personal-build; een nieuwe sleutel kan de gepubliceerde APK niet bijwerken.' >&2
    exit 2
fi
if "$init_new_key"; then
    python3 prepare_signing.py --init-new-key
else
    python3 prepare_signing.py
fi
./gradlew testDebugUnitTest lintRelease assembleRelease --no-daemon --console=plain
if "$personal_build"; then
    python3 publish_apk.py --personal-build
else
    python3 publish_apk.py
fi
