#!/bin/bash
# Builds dist/beat50-<version>.dmg with beat50.app, a link to Applications and first-open notes.
# Signed with the Developer ID certificate in the keychain and notarized with the notarytool profile "beat50"
# (README, "Signing and notarizing"), so macOS opens it without warnings. --unsigned skips both, for a local test build.
set -euo pipefail
cd "$(dirname "$0")/.."
unsigned=0
[[ "${1:-}" == "--unsigned" ]] && unsigned=1
version=$(.venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
dmg="dist/beat50-$version.dmg"

if (( ! unsigned )); then
  # BEAT50_SIGN_ID picks the certificate when the keychain has more than one.
  if [[ -z "${BEAT50_SIGN_ID:-}" ]]; then
    ids=$(security find-identity -v -p codesigning | sed -n 's/.*"\(Developer ID Application: [^"]*\)".*/\1/p')
    if [[ $(grep -c . <<< "$ids") != 1 ]]; then
      echo "Need exactly one Developer ID Application certificate in the keychain, or BEAT50_SIGN_ID." >&2
      echo "For a local test build: $0 --unsigned" >&2
      exit 1
    fi
    BEAT50_SIGN_ID=$ids
  fi
  export BEAT50_SIGN_ID  # beat50.spec signs every binary and the app with it, with the hardened runtime
fi

rm -rf build dist
.venv/bin/pyinstaller --noconfirm --clean beat50.spec
staging=$(mktemp -d)
cp -R dist/beat50.app "$staging/"
ln -s /Applications "$staging/Applications"
cp packaging/FIRST-OPEN.txt "$staging/"
hdiutil create -volname "beat50 $version" -srcfolder "$staging" -ov -format UDZO "$dmg"
rm -rf "$staging"

if (( ! unsigned )); then
  codesign --sign "$BEAT50_SIGN_ID" --timestamp "$dmg"
  # notarytool exits 0 even when Apple rejects the upload: the status decides.
  result=$(xcrun notarytool submit "$dmg" --keychain-profile "${BEAT50_NOTARY_PROFILE:-beat50}" --wait --output-format json)
  status=$(.venv/bin/python -c 'import json, sys; print(json.loads(sys.argv[1])["status"])' "$result")
  if [[ "$status" != "Accepted" ]]; then
    id=$(.venv/bin/python -c 'import json, sys; print(json.loads(sys.argv[1])["id"])' "$result")
    echo "Notarization $status. Details: xcrun notarytool log $id --keychain-profile ${BEAT50_NOTARY_PROFILE:-beat50}" >&2
    exit 1
  fi
  xcrun stapler staple "$dmg"
  spctl --assess --type open --context context:primary-signature -v "$dmg"
  spctl --assess --type execute -v dist/beat50.app
fi
echo "$dmg"
