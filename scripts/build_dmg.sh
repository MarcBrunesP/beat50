#!/bin/bash
# Builds dist/beatcrate-<version>.dmg with beatcrate.app, a link to Applications and first-open notes.
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(.venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
rm -rf build dist
.venv/bin/pyinstaller --noconfirm --clean beatcrate.spec
staging=$(mktemp -d)
cp -R dist/beatcrate.app "$staging/"
ln -s /Applications "$staging/Applications"
cp packaging/FIRST-OPEN.txt "$staging/"
hdiutil create -volname "beatcrate $version" -srcfolder "$staging" -ov -format UDZO "dist/beatcrate-$version.dmg"
rm -rf "$staging"
echo "dist/beatcrate-$version.dmg"
