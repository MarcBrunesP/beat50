# beatcrate.spec — PyInstaller: beatcrate.app, a regular Mac app with its own window.
import tomllib
from pathlib import Path

version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]

a = Analysis(["packaging/beatcrate_app.py"], pathex=["."],
             datas=[("beatcrate/app/static", "beatcrate/app/static")])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="beatcrate", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="beatcrate")
app = BUNDLE(coll, name="beatcrate.app", icon="assets/beatcrate.icns", bundle_identifier="com.beatcrate.app",
             version=version,
             info_plist={"CFBundleShortVersionString": version, "CFBundleVersion": version,
                         "NSHighResolutionCapable": True,
                         # Without these, the window would always send English Accept-Language.
                         "CFBundleLocalizations": ["en", "es"], "CFBundleDevelopmentRegion": "en"})
