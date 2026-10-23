# Native Linux releases

[Back to README](../README.md)

Native releases bundle CPython, PySide6/Qt and APKForge into a PyInstaller
one-directory payload. The same payload is used for three x86_64 packages:

| File | Installation / use |
| --- | --- |
| `apkforge_VERSION_amd64.deb` | Install with `sudo apt install ./apkforge_VERSION_amd64.deb`; opens from the application menu or `apkforge`. |
| `APKForge-VERSION-x86_64.AppImage` | Make executable and run; no root or Python installation required. |
| `APKForge-VERSION-linux-x86_64.tar.gz` | Extract, preserve symlinks, then run `apkforge/apkforge`; no FUSE required. |

Official builds target Ubuntu 22.04 x86_64 (glibc 2.35) and newer compatible Linux
desktops. A local build inherits its host's glibc requirement. This is not support
for ARM, musl/Alpine, or every Linux distribution. Qt still uses the host's display,
graphics, font and desktop libraries. The Debian package declares those system
dependencies; an AppImage is not a complete operating-system container.

Java, Apktool, APKEditor, Smali and Android SDK tools are **not bundled**. Use the
first online launch to install missing tools, or transfer compatible tool
installations before running with `APKFORGE_OFFLINE=1`. Native packages themselves
do not need pip, a virtual environment, or a separately installed Python/Qt.

## Build locally

Use a clean Linux x86_64 environment, preferably Ubuntu 22.04, Python 3.12, and
`binutils`. Install the desktop/XCB libraries listed in
[the native workflow](../.github/workflows/native.yml). Build inputs need network
access; assembly and the built-in smoke tests use local files after preparation.

```bash
python3.12 -m venv .venv-native
. .venv-native/bin/activate
python -m pip install -r packaging/requirements.txt
python packaging/prepare.py
python packaging/build.py \
  --notices build/native/notices \
  --appimagetool build/native/appimagetool-x86_64.AppImage \
  --appimage-runtime build/native/runtime-x86_64
```

Packages and upstream source archives appear in `dist/`. To build just a Debian
package and portable archive, use `--formats deb portable` and omit the two
AppImage tool arguments. `--skip-freeze` reuses an existing payload; only use it
when application code and build dependencies have not changed.

`prepare.py` downloads appimagetool 1.9.1 and a specific AppImage runtime with pinned
SHA-256 checksums. The runtime is hosted under upstream's rolling `continuous`
release: if it changes, the build fails closed. Update the URL/checksum together
after reviewing the upstream release. It also collects license and attribution
files from upstream Qt/PySide6 6.8.3 source archives, retaining those source archives
as release assets. Update the source version, requirement pins and bundled notices
together when updating Qt. Do not distribute incomplete or mismatched notices.

The PyInstaller spec removes unused PDF, QML and virtual keyboard libraries and
plugins. It retains the Widgets interface, image support and desktop platform
plugins. Onedir libraries remain replaceable; the bundled notices explain how to
inspect or substitute compatible Qt libraries, including after AppImage extraction.

## Validation

The build invokes the frozen executable's `--self-test`. It uses temporary settings
and checks GUI construction, translated resources, a bundled file-operation helper,
and an external system subprocess without Android tools or downloads.

```bash
QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME= APKFORGE_OFFLINE=1 \
  build/native/payload/apkforge/apkforge --self-test
```

CI also validates Debian metadata, extracts and tests the `.deb` payload, tests the
portable archive, and runs the AppImage with `--appimage-extract-and-run` to avoid
requiring FUSE on the runner. It does not replace a real desktop installation test,
file association checks, Android tool integration tests, or device testing.

## GitHub releases

The **Native Linux packages** workflow can be run manually from Actions to build
and download test artifacts without creating a release. Tagged releases run the
normal CI suite and native build before creating the release draft. The draft
contains `.deb`, `.AppImage`, portable archive, Python wheel/sdist, upstream Qt
source archives, and `SHA256SUMS`. Review and publish the draft from GitHub.

For a release, update `apkforge/__init__.py`, commit and push the project, then push
a matching tag (for example `v0.2.0`). Keep downloaded tools and build output out
of Git. Uploading a new tag is enough; no local native build is required.
