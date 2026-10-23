# APKForge Linux

A native Linux desktop application for decoding, rebuilding, inspecting, aligning
and signing Android APKs. Built with Python and Qt, inspired by
[AndnixSH/APKToolGUI](https://github.com/AndnixSH/APKToolGUI). Runs locally without
Wine or a server. This is an independent project, not an official upstream release.

## Features

- Nine workflow tabs: Main, APK Info, Decode, Build, Sign, Zip align, Framework,
  Baksmali and ADB.
- Apktool/APKEditor projects, split-package merging, APK metadata and bitmap icons.
- Chained build → align → sign → install with validation, live logs and cancellation.
- Custom tool paths, automatic discovery, installation of missing tools and explicit updates.
- Drag and drop, desktop Open With integration, themes and nine interface languages
  with English fallback for incomplete translations.

See the [user guide](docs/user-guide.md) for the full feature matrix, signing
behavior, settings locations and limitations.

## Requirements

- Linux, Python **3.10+**, and PySide6 **6.7–6.x** (installed by the launcher).
- A graphical desktop and Qt runtime libraries. Debian/Ubuntu may require
  `python3-venv`, `libegl1`, `libopengl0`, and `libxcb-cursor0`; package names vary
  across distributions.
- Internet access for first-use Python dependency installation and missing tools.
  Configured tools are reused, so later launches can work offline.
- Automatic Android native tool downloads require **Linux x86_64**. On other
  architectures, configure compatible native tools manually.

Java, Apktool, APKEditor, Smali/Baksmali, and Android SDK tools are discovered on
PATH, in `JAVA_HOME`, Android SDK locations and local JARs. Only missing tools are
downloaded at startup. Downloaded tools retain their own licenses.

## Quick start

From a downloaded or cloned source checkout:

```bash
./run.sh
# Open an APK or decoded project:
./run.sh /path/to/application.apk
```

The launcher creates `.venv`, installs dependencies when needed and starts the app.
For a manual installation:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
apkforge
```

`python -m apkforge.app` is also supported. In the application, use
**Settings → Open settings → Tool paths** to configure tools and Java VM arguments.
**Settings → Install missing tools** repeats discovery; **Update tools to latest
stable** explicitly downloads updates. **File → Install desktop / Open With entry**
adds a launcher without changing default file associations.

## Offline use

After installing Python dependencies and the tools needed for your workflows,
decoding, rebuilding, signing, alignment, inspection and USB ADB work locally.
Store links, tool downloads and updates require internet access.

To skip automatic Python installation and tool downloads explicitly:

```bash
APKFORGE_OFFLINE=1 ./run.sh
```

This mode still discovers local tools and reports missing ones. Workflows requiring
a missing tool cannot run. It does not block network access for external tools or
links you open. Keep `.venv` and your configured tool installation on the machine
for subsequent offline launches; neither belongs in Git. A freshly cleaned
checkout needs dependencies installed again.

For installation on a disconnected machine, prepare a wheelhouse on a connected
Linux machine with the same architecture and Python version. Build the APKForge
wheel (see CONTRIBUTING), then download its dependencies:

```bash
python -m pip download --only-binary=:all: --dest wheelhouse dist/*.whl
```

Transfer the wheelhouse, the matching APKForge wheel, and the required Java/Android
tools, preserving their distribution licenses and directory layouts. On the offline
machine, with Python, venv support and native Qt libraries already installed:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --no-index --find-links=/path/to/wheelhouse /path/to/apkforge_linux-VERSION-py3-none-any.whl
APKFORGE_OFFLINE=1 apkforge
```

Replace `VERSION` with the downloaded version. Configure the transferred tool paths
in Settings. Wheelhouses are platform-specific; native Linux libraries must also be
installed ahead of time.

## Releases

Pushing a tag matching the package version, such as `v0.2.0`, runs CI and creates a
**draft GitHub release** with a wheel, source distribution and `SHA256SUMS`.
Maintainers review the draft and publish it from GitHub. See the
[release checklist](docs/architecture.md#release-checks).

These are Python packages, not standalone executables: they require Python,
PySide6/Qt and external Android tools. The release workflow does not bundle those
tools, build an AppImage/DEB, or publish to PyPI. Verify downloaded assets with
`sha256sum -c SHA256SUMS` from the directory containing all release assets.

## Documentation

- [User guide and feature coverage](docs/user-guide.md)
- [Project layout, architecture and release checks](docs/architecture.md)
- [Contributing and development setup](CONTRIBUTING.md)
- [Security reports](SECURITY.md)
- [Third-party notices and credits](THIRD_PARTY_NOTICES.md)

## Validation

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q apkforge
bash -n run.sh
```

GitHub Actions runs the offline tests on Python 3.10 and 3.14, builds source and
wheel distributions, checks metadata, and imports the installed wheel outside the
checkout. Real desktop behavior and device installation require manual checks.

The optional integration script creates a small APK and temporary configuration.
It exercises info/icons, signing, decode/rebuild, unsigned metadata, alignment,
split merge, frameworks, and Smali roundtrips against real tools. It currently
requires Debian-style tooling: `apktool`, `aapt`, `apksigner`, `zipalign`, Java,
`/usr/share/java/android-apktool/apktool.jar` containing
`prebuilt/android-framework.jar`, and a reference APKToolGUI `Tools` directory
containing its additional JARs and test certificate:

```bash
APKFORGE_REFERENCE_TOOLS=/path/to/APKToolGUI/Tools \
  QT_QPA_PLATFORM=offscreen .venv/bin/python tests/integration/smoke.py
```

## Troubleshooting

- **Virtual environment creation fails:** install your distribution's Python venv
  support, then run the launcher again.
- **Qt cannot load a platform plugin:** check the desktop session and native Qt/XCB
  libraries. `QT_QPA_PLATFORM=offscreen` is for automated checks, not interactive use.
- **Tool installation fails:** check network access and the log; configure existing
  executables or JARs in Tool paths. Available configured tools remain usable.
- **ADB device is unauthorized/offline:** authorize debugging on the device, check
  USB permissions, and refresh the device list.
- **A rebuilt APK will not update an installed app:** the signing identity must
  match. APKForge's automatic development key is not the original author's key.

## License and credits

APKForge's original code is [MIT licensed](LICENSE). The UI workflow and adapted
translation resources credit AndnixSH/APKToolGUI and its contributors, with original
project lineage to INF1NUM/APKToolGUI. The translation resources retain their
upstream Unlicense dedication. External tools and PySide6/Qt use separate licenses;
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for authors and source links.
