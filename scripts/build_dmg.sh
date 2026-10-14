#!/bin/bash
# Builds dist/beat50-<version>.dmg with beat50.app, a link to Applications and first-open notes.
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(.venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
rm -rf build dist
.venv/bin/pyinstaller --noconfirm --clean beat50.spec
staging=$(mktemp -d)
cp -R dist/beat50.app "$staging/"
ln -s /Applications "$staging/Applications"
cp packaging/FIRST-OPEN.txt "$staging/"
hdiutil create -volname "beat50 $version" -srcfolder "$staging" -ov -format UDZO "dist/beat50-$version.dmg"
rm -rf "$staging"
echo "dist/beat50-$version.dmg"
