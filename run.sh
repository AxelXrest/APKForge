#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
. .venv/bin/activate
if ! python -c 'from PySide6.QtCore import QProcess; assert hasattr(QProcess.UnixProcessFlag, "CreateNewSession")' >/dev/null 2>&1; then
    if [[ "${APKFORGE_OFFLINE:-0}" == "1" ]]; then
        echo 'Offline mode: Python dependencies are missing. Run ./run.sh once online or install from a prepared wheelhouse (see README).' >&2
        exit 1
    fi
    python -m pip install -e .
fi
exec python -m apkforge.app "$@"
