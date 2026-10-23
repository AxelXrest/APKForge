# Contributing

APKForge is a Python/Qt Linux application. Keep changes focused, describe the user-visible
behavior, and retain upstream attribution when adapting code or translations.

## Development

Use Python 3.10 or newer on Linux:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME= python -m unittest discover -s tests -v
python -m compileall -q apkforge
```

Tests use temporary settings and mock external commands. They should not require
network access, a phone, or downloaded Android tools. Add regression coverage for
behavior changes. Run the optional real-tool checks described in the README when
changing tool compatibility; document any checks you could not run.

See [architecture](docs/architecture.md) for module responsibilities. Keep Qt UI
work on the main thread and external workflows asynchronous. Pass commands as
argument lists, preserve cancellation and fail-fast behavior, and keep passwords
out of saved settings and logs.

## Issues and pull requests

Include Python/PySide6 versions, Linux distribution, tool versions, reproduction
steps, and expected/actual behavior. Remove passwords, signing keys, personal
paths, device identifiers, and private APK contents from logs and screenshots.
Report APKForge integration bugs here; report bugs reproduced directly in an
external tool to its upstream project, with a link when relevant.

Before submitting, run the tests and build both distribution formats:

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

Do not commit virtual environments, IDE state, generated distributions, downloaded
tools, APKs, or signing credentials. Update documentation and
[third-party notices](THIRD_PARTY_NOTICES.md) when behavior or provenance changes.

When changing visible controls, regenerate the real UI captures using
[screenshot instructions](docs/screenshots.md#updating-the-screenshots).

For installable Linux releases, follow the [native packaging guide](docs/native-packaging.md).
