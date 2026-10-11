#!/usr/bin/env python3
"""Create a local release key once; never print or include it in the shared package."""
from pathlib import Path
import os
import secrets
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent
private = root / '.signing'
private.mkdir(exist_ok=True, mode=0o700)
os.chmod(private, 0o700)
properties = private / 'signing.properties'
key = private / 'plexport-release.jks'
if properties.exists() and key.exists():
    raise SystemExit(0)
if properties.exists() or key.exists():
    raise SystemExit('Ondertekening is onvolledig. Herstel je .signing-back-up voordat je verder bouwt.')

java_home = os.environ.get('JAVA_HOME')
keytool = str(Path(java_home) / 'bin/keytool') if java_home else shutil.which('keytool')
if not keytool:
    raise SystemExit('JDK 17 of nieuwer is nodig; stel JAVA_HOME in.')
password = secrets.token_hex(32)
with tempfile.NamedTemporaryFile(mode='w', prefix='plexport-signing-') as temporary:
    temporary.write(password + '\n')
    temporary.flush()
    subprocess.run([
        keytool, '-genkeypair', '-keystore', str(key), '-storetype', 'JKS',
        '-storepass:file', temporary.name, '-keypass:file', temporary.name,
        '-alias', 'plexport', '-keyalg', 'RSA', '-keysize', '3072', '-validity', '10000',
        '-dname', 'CN=PlexPort Local, OU=Personal NAS App, O=PlexPort', '-noprompt',
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.chmod(key, 0o600)
with os.fdopen(os.open(properties, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
    output.write('storeFile=.signing/plexport-release.jks\n')
    output.write(f'storePassword={password}\nkeyAlias=plexport\nkeyPassword={password}\n')
print('Lokale ondertekening aangemaakt. Bewaar de map android/.signing voor toekomstige updates.')
