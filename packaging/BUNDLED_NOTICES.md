# Bundled native runtime

APKForge is maintained by AxelXrest. Its original source uses MIT; adapted
translations retain the upstream Unlicense dedication. See the accompanying
LICENSE and THIRD_PARTY_NOTICES.md.

Native builds include CPython, PySide6, Shiboken6 and Qt shared libraries.
Qt and Qt for Python are copyright The Qt Company Ltd. and contributors and are
used under LGPL-3.0. License texts and upstream third-party attributions are in
licenses/Qt. Python's license and PyInstaller's bootloader exception are included
in this directory. BUILD-VERSIONS.txt records the installed build versions.

The release also includes the unmodified Qt 6.8.3 and PySide6 6.8.3 source archives
used for license/attribution collection. These are upstream source, not APKForge's
source. See the release's APKForge source distribution for application/build code.
The build environment may contribute other shared libraries; their distribution
notices are copied into licenses/Qt/system where available.

Qt is dynamically linked. You may inspect, debug and replace the bundled libraries
with interface-compatible modified versions. For a .deb installation they are
under /opt/apkforge/_internal; for the portable archive under apkforge/_internal.
For an AppImage, run it with --appimage-extract and modify the extracted
squashfs-root/usr/lib/apkforge/_internal directory, then run squashfs-root/AppRun.
Keep dependent library versions and Qt plugins compatible. No signing lock or
installation restriction is applied to modified bundles.

Upstream source locations:
- https://code.qt.io/cgit/qt/qtbase.git/tag/?h=v6.8.3
- https://code.qt.io/cgit/qt/qtsvg.git/tag/?h=v6.8.3
- https://code.qt.io/cgit/qt/qtwayland.git/tag/?h=v6.8.3
- https://code.qt.io/cgit/qt/qttranslations.git/tag/?h=v6.8.3
- https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.8.3
- https://www.python.org/downloads/source/

Java, Apktool, APKEditor, Smali and Android SDK tools are not bundled.
