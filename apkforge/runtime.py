"""Commands and subprocess environments for source and frozen Linux builds."""
import os
import sys


def module_command(module, *arguments, persistent=False):
    if getattr(sys, 'frozen', False):
        executable = os.environ.get('APPIMAGE', sys.executable) if persistent else sys.executable
        return [executable, '--internal', module, *map(str, arguments)]
    return [sys.executable, '-m', module, *map(str, arguments)]


def external_environment():
    """Do not expose PyInstaller's bundled libraries to system Android/Java tools."""
    environment = os.environ.copy()
    if getattr(sys, 'frozen', False):
        if 'LD_LIBRARY_PATH_ORIG' in environment:
            environment['LD_LIBRARY_PATH'] = environment['LD_LIBRARY_PATH_ORIG']
        else:
            environment.pop('LD_LIBRARY_PATH', None)
        for key in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'):
            environment.pop(key, None)
    return environment


def open_url(url):
    if not getattr(sys, 'frozen', False):
        from PySide6.QtGui import QDesktopServices
        return QDesktopServices.openUrl(url)
    import subprocess
    try:
        subprocess.Popen(['xdg-open', url.toString()], env=external_environment(), start_new_session=True)
        return True
    except OSError:
        return False
