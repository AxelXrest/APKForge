#!/usr/bin/env python3
"""Capture the real Qt interface without downloading tools or changing user settings.

QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME= python scripts/screenshots.py
Requires the project's PySide6 dependency. No APK or external tools are needed.
"""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QSplitter
from apkforge import core
from apkforge.app import SettingsDialog, Window


def main():
    destination = Path(__file__).resolve().parents[1] / 'docs' / 'screenshots'
    destination.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle('Fusion')
    with tempfile.TemporaryDirectory(prefix='apkforge-screenshots-') as directory:
        original_config = core.CONFIG
        core.CONFIG = Path(directory) / 'settings.json'
        window = None
        try:
            window = Window(probe=False)
            window.resize(1200, 1000)
            window.show()
            for index, name in enumerate(('main', 'apk-info', 'decode', 'build', 'sign',
                                          'zip-align', 'framework', 'baksmali', 'adb')):
                window.tabs.setCurrentIndex(index)
                window.findChild(QSplitter).setSizes([820, 130])
                app.processEvents()
                if not window.grab().save(str(destination / f'{name}.png')):
                    raise RuntimeError(f'Could not save {name}')
            dialog = SettingsDialog(window.settings, window)
            dialog.resize(900, 720)
            dialog.show()
            app.processEvents()
            from PySide6.QtWidgets import QTabWidget
            for index, name in enumerate(('settings-tools', 'settings-general')):
                dialog.findChild(QTabWidget).setCurrentIndex(index)
                app.processEvents()
                if not dialog.grab().save(str(destination / f'{name}.png')):
                    raise RuntimeError(f'Could not save {name}')
            dialog.close()
            window.tabs.setCurrentIndex(0)
            window.settings.theme = 'Light'
            window.apply_theme()
            app.processEvents()
            if not window.grab().save(str(destination / 'main-light.png')):
                raise RuntimeError('Could not save light theme')
        finally:
            if window is not None:
                window.close()
            core.CONFIG = original_config
    print(f'Saved 12 application screenshots in {destination}')


if __name__ == '__main__':
    main()
