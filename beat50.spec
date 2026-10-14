# beat50.spec — PyInstaller: beat50.app, a regular Mac app with its own window.
import tomllib
from pathlib import Path

version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]

a = Analysis(["packaging/beat50_app.py"], pathex=["."],
             datas=[("beat50/app/static", "beat50/app/static")])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="beat50", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="beat50")
# The bundle id keeps the name before 3.0 (beatcrate): macOS keeps the Beatport session and the language
# cookie under it, so changing it would sign everyone out.
app = BUNDLE(coll, name="beat50.app", icon="assets/beat50.icns", bundle_identifier="com.beatcrate.app",
             version=version,
             info_plist={"CFBundleShortVersionString": version, "CFBundleVersion": version,
                         "NSHighResolutionCapable": True,
                         # Without these, the window would always send English Accept-Language.
                         "CFBundleLocalizations": ["en", "es"], "CFBundleDevelopmentRegion": "en"})
