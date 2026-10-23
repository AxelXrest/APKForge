# APKForge Linux

A Linux desktop app for working with Android APKs, maintained by **AxelXrest**.
Decode an APK, edit the project, rebuild it, then align and sign the result from
one window. Python and Qt handle the interface; established Android tools do the
APK work. No Wine or server required.

The workflow is inspired by [AndnixSH/APKToolGUI](https://github.com/AndnixSH/APKToolGUI).
This is an independent Linux project; upstream authors and translators are credited
in [third-party notices](THIRD_PARTY_NOTICES.md).

![APKForge Main tab with decode, build, align, sign and split-package merge actions](docs/screenshots/main.png)

[Get started](#quick-start) · [All screenshots](docs/screenshots.md) ·
[User guide](docs/user-guide.md) · [Offline setup](#offline-use) · [Releases](#releases)

## What it does

| Tab | Available workflows |
| --- | --- |
| [Main](docs/screenshots.md#main) | Decode, build, align, sign and merge, with shortcuts to project files and output folders. |
| [APK Info](docs/screenshots.md#apk-info) | Package/version/SDK details, permissions, architectures, bitmap icons, AAPT dumps and certificate verification. |
| [Decode](docs/screenshots.md#decode) | Apktool or APKEditor; APK/XAPK/APKS/APKM/ZIP input; split merge, source/resource options, frameworks and optional project fixes. |
| [Build](docs/screenshots.md#build) | Detect the project format, configure rebuild options, then optionally align and sign. |
| [Sign](docs/screenshots.md#sign) | Development key, your own keystore, or key/certificate pair; v1–v4 schemes and signature verification. |
| [Zip align](docs/screenshots.md#zip-align) | Align or check APKs, select native-library page alignment, and optionally sign the output. |
| [Framework](docs/screenshots.md#framework) | Install, tag and clean frameworks in an app-managed cache or a custom directory. |
| [Baksmali](docs/screenshots.md#baksmali) | Disassemble DEX/ODEX/OAT/APK files and assemble smali back into DEX. |
| [ADB](docs/screenshots.md#adb) | Select an authorized device and install APKs, with replacement, installer and ABI options. |

Drag and drop files, preview commands before running them, follow live output, and
stop an active workflow. Paths and options are remembered; passwords are not saved.
Dark, light and system themes are available. English and eight upstream
translations are included, with English fallback where translations are incomplete.

| Decode options | Signing options |
| --- | --- |
| ![Decode tab showing engine, resource, source, framework and thread options](docs/screenshots/decode.png) | ![Sign tab showing signing identity and signature scheme controls](docs/screenshots/sign.png) |

The [screenshot gallery](docs/screenshots.md) covers every tab, both settings panels
and the light theme. The [user guide](docs/user-guide.md) lists the detailed flags
and current limitations. Screenshots show the actual interface with empty inputs;
they do not represent completed APK operations.

## Install a Linux package

Download an x86_64 package from [GitHub Releases](https://github.com/AxelXrest/APKForge/releases).
The release workflow builds these formats; publish the generated draft to make
them available to users.

**Debian / Ubuntu:**

```bash
sudo apt install ./apkforge_0.2.0_amd64.deb
apkforge
```

**AppImage:**

```bash
chmod +x APKForge-0.2.0-x86_64.AppImage
./APKForge-0.2.0-x86_64.AppImage
```

If FUSE is unavailable, run the AppImage with `--appimage-extract-and-run`, or use
the portable `APKForge-0.2.0-linux-x86_64.tar.gz` archive and run its
`apkforge/apkforge` executable. Replace the example version with your download.

Native packages include Python and the Qt GUI runtime. They target Linux x86_64
with glibc 2.35+ and compatible desktop libraries; Debian/Ubuntu packages install
system dependencies through apt. Java and Android tools are installed separately.
See [native packaging](docs/native-packaging.md) for builds, compatibility and tests.

## Requirements for source installs

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

For running directly from source:

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

After installing a native package (or Python dependencies for a source install)
and the tools needed for your workflows,
decoding, rebuilding, signing, alignment, inspection and USB ADB work locally.
Store links, tool downloads and updates require internet access.

To skip automatic Python installation and tool downloads explicitly:

```bash
APKFORGE_OFFLINE=1 ./run.sh
# Debian package:
APKFORGE_OFFLINE=1 apkforge
# AppImage:
APKFORGE_OFFLINE=1 ./APKForge-0.2.0-x86_64.AppImage
```

This mode still discovers local tools and reports missing ones. Workflows requiring
a missing tool cannot run. It does not block network access for external tools or
links you open. Keep `.venv` and your configured tool installation on the machine
for subsequent offline launches; neither belongs in Git. A freshly cleaned
checkout needs dependencies installed again.

For a native offline installation, transfer the `.deb`, AppImage or portable
archive and the required external tools. Prepare any missing system libraries
ahead of time; `apt install` may otherwise need network access.

For a Python source/package installation on a disconnected machine, prepare a
wheelhouse on a connected
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

Pushing a tag matching the package version, such as `v0.2.0`, runs CI and the
native build, then creates a **draft GitHub release** containing:

- `.deb`, AppImage and a portable Linux archive (x86_64).
- Python wheel and source distribution.
- Upstream Qt/PySide6 source archives and SHA-256 checksums.

Review the draft and publish it from GitHub. See the
[release checklist](docs/architecture.md#release-checks) and
[native build guide](docs/native-packaging.md). You can also run **Native Linux
packages** manually in Actions to download test builds before tagging a release.
There is no automatic PyPI publication. Verify downloaded assets with
`sha256sum -c SHA256SUMS` from the directory containing all release assets.

## Documentation

- [Screenshots of every tab and settings panel](docs/screenshots.md)
- [User guide and feature coverage](docs/user-guide.md)
- [Native packages and build instructions](docs/native-packaging.md)
- [Project layout, architecture and release checks](docs/architecture.md)
- [Contributing and development setup](CONTRIBUTING.md)
- [Security reports](SECURITY.md)
- [Third-party notices and credits](THIRD_PARTY_NOTICES.md)

## Validation

```bash
QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME= .venv/bin/python -m unittest discover -s tests -v
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
  QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME= .venv/bin/python tests/integration/smoke.py
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

APKForge is maintained by **AxelXrest**. Original code is [MIT licensed](LICENSE). The UI workflow and adapted
translation resources credit AndnixSH/APKToolGUI and its contributors, with original
project lineage to INF1NUM/APKToolGUI. The translation resources retain their
upstream Unlicense dedication. External tools and PySide6/Qt use separate licenses;
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for authors and source links.
