#!/bin/zsh
cd "${0:A:h}"
if command -v python3 >/dev/null 2>&1; then
  python3 -m plexport --open
else
  print "PlexPort vereist Python 3.11 of nieuwer. Installeer Python via https://www.python.org/downloads/ en start opnieuw."
  read "reply?Druk op Enter om te sluiten."
fi
