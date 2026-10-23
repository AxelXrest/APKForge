# User guide

[Back to README](../README.md)

## Feature coverage

| Tab | Features |
| --- | --- |
| Main | Decompile, compile, align, sign, merge; shortcuts to output folders, AndroidManifest.xml, apktool.yml and launcher activity smali; file/folder drag and drop. |
| APK Info | App/package/version, SDKs, architecture, locales, densities, screens, permissions and launcher activity; AAPT dumps; signature verification/certificates; bitmap icon preview/export; app store/search links. |
| Decode | Apktool or APKEditor; APK/XAPK/APKS/APKM/ZIP input; split merge before decoding; source/resource skipping; force overwrite; keep broken resources; match original; debug info; main DEX; API level; threads; framework path/tag; additional arguments; optional project fixes; optional metadata parsing. |
| Build | Auto-detect Apktool/APKEditor projects; force rebuild; copy original manifest/META-INF; custom aapt/aapt2; framework; no-crunch; network security config; API level/threads; additional arguments; chained alignment and signing; separate unsigned APK with original signature metadata. |
| Sign | Keystore/alias or PKCS #8 key + X.509 certificate; separate key password; Auto/Enabled/Disabled for schemes v1–v4; optional idsig cleanup; explicit in-place signing; install after signing; signature verification; development keystore creation. |
| Zip align | Alignment bytes; check-only; verbose; Zopfli; force overwrite; 4/16/64 KiB native library alignment; sign after alignment; split-package merge and additional APKEditor arguments. |
| Framework | Install/tag frameworks; custom cache; clear before decoding; manual cleanup; open framework folder. Uses a separate app-managed cache by default. |
| Baksmali | DEX/ODEX/OAT/APK → smali and smali → DEX; output paths, API, threads and additional arguments. |
| ADB | Refresh/select ready devices; display offline/unauthorized devices; install/replace APK; Play Store installer attribution; ABI override; stop ADB server. |

### Quality of life

- `/path/MyApp.apk` automatically decodes to `/path/MyApp/`. Custom output paths are retained when changing inputs.
- Build, align, sign, merge and DEX output names are suggested automatically beside their input.
- Successful decompiles fill the build project field. Completed APKs fill the signing, alignment, inspection and installation fields.
- Preview commands before running; live logs, copy/save/clear, timestamps and persistent status; keyboard shortcuts.
- APK Info uses labeled, selectable fields with an icon, six store links, and separate locales/permissions lists. It expands to the full window height; Show log restores command output, and Copy details exports the metadata.
- Workflows run asynchronously and stop after a failure. Stop cancels the active process group and all remaining stages.
- Tool/version diagnostics adapt framework cleanup and legacy flags to Apktool 2/3.
- Every workflow is validated before it starts, including signing credentials and device selection.
- Paths and options are remembered; passwords stay in memory and child-process environment variables, never configuration or command logs.
- Project fixes keep `.apkforge.bak` copies. Unsigned mode creates a separate APK and preserves original signature metadata; modified contents do not have a valid original signature.
- Dark, light and system themes; completion sound; optional clear log and open-output-on-success.
- English plus upstream German, Portuguese, Hungarian, Russian, Chinese, Japanese, Turkish and Vietnamese translation coverage. New Linux-specific labels and incomplete upstream translations fall back to English. Restart to change language.
- Temporary files live in a unique app-owned directory; Clear temp only removes this instance's temporary files.

### Differences from Windows APKToolGUI

Linux desktop integration uses an Open With entry instead of Windows Explorer registry
menus. Files open in the desktop's configured editor/file manager. UTF-8 paths and Qt
DPI scaling are native. Removed tool flags are disabled for newer Apktool versions.
The app uses Android SDK `apksigner`, supporting both keystores and key/certificate
pairs. Signing defaults to a persistent development key created automatically at
`~/.config/apkforge/signing/development.jks` (alias `androiddebugkey`, password
`android`). This is a development identity, not the original APK author’s signature.
Select Keystore or Private key + certificate in Sign to use your own identity.
Signing after build/alignment remains an explicit option.

Tool downloads default to `$XDG_DATA_HOME/apkforge/tools/`, or
`~/.local/share/apkforge/tools/` when `XDG_DATA_HOME` is unset. Choose a different
folder in **Settings → Open settings → Tool paths → Tool installation directory**.
The selection is saved and used for future installations and updates. Existing
tools remain usable at their current paths; changing the folder does not move them.

**Settings → Install missing tools** repeats startup detection and installs only
missing tools. **Settings → Update tools to latest stable** explicitly fetches the
latest releases for all tools, including available tools, into the selected folder
and selects those managed copies. Original system/custom files are never overwritten.
Tools distributed together (Java/keytool and Android Build Tools) share a download,
but installing a missing tool preserves the configured paths of available tools.

Downloads use GitHub releases, Google’s Android repository and Eclipse Adoptium.
Published checksums are verified before installation. Network failures are logged
and retain existing tools; installation of missing tools needs internet access.
Java downloads use the latest LTS release.
APKForge does not update the Windows application. It does not currently bundle native distribution packages
or an in-app text editor. XML adaptive icons without a bitmap fallback cannot be
exported as a bitmap.

Settings: `~/.config/apkforge/settings.json`; default frameworks:
`~/.config/apkforge/frameworks/`. Signing runs after alignment. Device installation
requires a connected, authorized device selected in ADB.

