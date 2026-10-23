# Third-party notices and credits

## APKForge

Original APKForge Python code is licensed under [MIT](LICENSE), copyright
2026 APKForge contributors. This license does not relicense external dependencies
or the upstream-derived translation data.

## APKToolGUI workflow and translations

The UI structure and workflows are based on
[AndnixSH/APKToolGUI](https://github.com/AndnixSH/APKToolGUI), maintained by AndnixSH
and its contributors, with project lineage to
[INF1NUM/APKToolGUI](https://github.com/INF1NUM/APKToolGUI).
APKForge is an independent Linux implementation and does not imply endorsement.

`apkforge/translations.json` was adapted from
`APKToolGUI/Languages/Language.*.resx` resources retrieved on 2026-10-22,
according to the existing project provenance record. Credits for the translations
belong to their upstream contributors. New Linux controls and incomplete
translations fall back to English. The precise imported upstream commit was not
recorded; future translation updates should record the commit and modified files.

Upstream publishes these resources under
[The Unlicense](https://github.com/AndnixSH/APKToolGUI/blob/master/LICENSE), a public
domain dedication. This dedication remains applicable to the adapted data.

## Runtime dependency

[PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) is provided by The Qt
Company and contributors. It is installed separately by pip and is not part of
APKForge's MIT-licensed source. See Qt's
[licensing information](https://www.qt.io/licensing/) and
[third-party notices](https://doc.qt.io/qtforpython-6/licenses.html).
Qt packages include their own library binaries and notices. APKForge's source
wheel does not bundle those dependency wheels.

## External command-line tools

These projects provide APKForge's underlying Android capabilities. Their
executables and JARs are not included in this source tree or APKForge wheel;
users configure existing tools or download them from upstream. Names and marks
belong to their respective owners. Refer to the license and notices shipped with
the exact downloaded version, including any bundled dependencies.

| Component | Authors / upstream | Role and licensing source |
| --- | --- | --- |
| Apktool | [iBotPeaches/Apktool](https://github.com/iBotPeaches/Apktool) and contributors | Decode/rebuild; see upstream license and distribution notices. |
| APKEditor | [REAndroid/APKEditor](https://github.com/REAndroid/APKEditor) and contributors | Decode/build/merge; [Apache-2.0](https://github.com/REAndroid/APKEditor/blob/master/LICENSE). |
| Smali / Baksmali | [JesusFreke](https://github.com/JesusFreke/smali), [Google and contributors](https://github.com/google/smali) | DEX assembly/disassembly; see upstream licenses. JAR releases are fetched from [baksmali/smali](https://github.com/baksmali/smali). |
| Android SDK Build Tools / Platform Tools | [Google / Android contributors](https://developer.android.com/tools) | AAPT, zipalign, apksigner, ADB; see the SDK package licenses and notices. |
| Eclipse Temurin / OpenJDK | [Eclipse Adoptium](https://adoptium.net/) and [OpenJDK contributors](https://openjdk.org/) | Java/keytool; see the JDK's legal directory and distribution license. |

Downloads are obtained from GitHub releases, Google's Android repository, and
Eclipse Adoptium. Published provider checksums are verified when available.
Repackaging any of these dependencies requires preserving that distribution's
applicable notices and terms separately from APKForge's license.
