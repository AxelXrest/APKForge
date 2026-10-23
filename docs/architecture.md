# Project layout and architecture

The importable application stays in `apkforge/`; tests and maintainer documentation
live outside the package. A `src/` migration is unnecessary for this small project
and would change the existing source-checkout launcher.

| Path | Responsibility |
| --- | --- |
| `apkforge/app.py` | Main window, tabs, settings dialog and workflow orchestration. |
| `apkforge/core.py` | Settings, validation, tool resolution and command construction. |
| `apkforge/jobs.py` | Asynchronous Qt process runner, cancellation and output capture. |
| `apkforge/tasks.py` | Project fixes and archive transformations executed as subprocess tasks. |
| `apkforge/tools.py` | Tool discovery, upstream metadata, downloads and extraction. |
| `apkforge/apkinfo.py` | APK metadata panel and parsing. |
| `apkforge/i18n.py`, `translations.json` | Upstream-derived translations with English fallback. |
| `tests/test_*.py` | Offline unit and Qt workflow tests. |
| `tests/integration/smoke.py` | Optional real-tool integration smoke test. |
| `.github/` | CI and issue/pull request templates. |
| `pyproject.toml`, `MANIFEST.in` | Dependency, package and source-distribution metadata. |
| `packaging/` | Native executable entry point, PyInstaller spec, package builders, desktop assets and notices. |
| `apkforge/runtime.py` | Source/frozen helper commands and clean environments for system tools. |
| `run.sh` | Source-checkout launcher and first-use dependency setup. |

## Execution and resource use

`core` constructs argument lists; `app` schedules `Job` objects through `Runner`.
The runner uses `QProcess` rather than blocking the event loop, stops remaining
stages after failure, and kills the active process group on cancellation. Probe
commands have a timeout. Process capture retains the last two million characters;
the visible log retains 15,000 blocks. Large tool downloads are copied in fixed
size chunks to a temporary file, verified, and atomically moved into place.

Settings and tool installations live outside the checkout, as described in the
README. Tests isolate settings in temporary directories. Passwords are held in
memory and passed through child-process environment variables.

## Release checks

1. Update the version in `apkforge/__init__.py` (packaging reads it dynamically).
2. Run the offline suite and relevant real-tool smoke tests.
3. Build an sdist and wheel, check metadata, and inspect their contents for
   translations, licenses, and accidental local files.
4. Install the wheel in a clean environment and test the `apkforge` entry point
   on a Linux desktop. CI checks packaged imports headlessly.
5. Commit changes and push an annotated `v<version>` tag matching the package
   version. `.github/workflows/release.yml` waits for CI, verifies that version,
   and waits for `.github/workflows/native.yml` before creating a draft with
   native packages, wheel, sdist, upstream source archives and SHA-256 checksums.
6. Review the draft, add user-visible changes and known limitations, and publish
   it in GitHub. Tag creation alone does not publish a public release. Do not
   move a release tag; fix issues in a new version.

Release automation uses the repository's built-in GitHub token with write access
only in the release job. GitHub Actions must be enabled. It does not publish to
PyPI. Native packages bundle Python and Qt; Java and Android tools remain separate. See the
README for preparing an offline installation.

CI covers Python 3.10 and 3.14 on Ubuntu; it does not establish compatibility with
every Linux distribution or replace visual desktop and physical-device testing.

See [native packaging](native-packaging.md) for the Ubuntu 22.04 / Python 3.12
build baseline and the bundled runtime checks.
